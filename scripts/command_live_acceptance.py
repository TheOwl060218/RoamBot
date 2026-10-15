"""Explicit opt-in: real configured model; isolated DB and Mock map/weather only.

Read ephemeral model configuration and vault unlock material from stdin. Never
write it or provider responses to reports. No production requests or deployment.
"""

import json
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from itertools import count
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

import httpx
from fastapi.testclient import TestClient
from roambot.api.dependencies import get_provider_bundle
from roambot.config import Settings
from roambot.main import create_app
from roambot.providers.assistant import OpenAICompatibleAssistantProvider
from roambot.providers.http import ProviderHttpClient
from roambot.security.vault import CredentialVault
from roambot.services.assistant_limits import AssistantLimiter


def main():
    if sys.argv[1:] != ["--authorized-real-model"]:
        print("Real model acceptance requires explicit user authorization.")
        return 2
    config = json.load(sys.stdin)
    focused_cases = set(config.get("cases", []))
    vault = CredentialVault(ROOT.parents[1] / "data/local-live/credentials.vault")
    credentials = vault.unlock(config.pop("master"))
    key = credentials.pop("llm_api_key")
    credentials.clear()
    report = {
        "model": config["model"],
        "maps_weather": "mock",
        "database": "isolated",
        "cases": [],
    }
    today = datetime.now(timezone(timedelta(hours=8))).date()
    with (
        httpx.Client(trust_env=False) as http,
        TemporaryDirectory(prefix="commands-live-", dir=ROOT / "test-results") as data,
    ):
        provider = OpenAICompatibleAssistantProvider(
            ProviderHttpClient(
                http, provider="llm", base_url=config["base"], timeout=8, secrets=(key,)
            ),
            key,
            config["model"],
            lambda: today,
            enable_thinking=config.get("thinking", False),
        )
        app = create_app(
            Settings(provider_mode="mock", demo_mode=True, data_dir=Path(data))
        )
        ticks = count(0, 61)
        app.state.assistant_limiter = AssistantLimiter(clock=lambda: next(ticks))
        with TestClient(app) as client:
            runtime = app.state.provider_runtime
            app.dependency_overrides[get_provider_bundle] = lambda: replace(
                runtime.new_request_bundle(), assistant=provider
            )
            session = client.post(
                "/api/v1/auth/register",
                json={"username": "live_" + uuid4().hex[:10], "password": uuid4().hex},
            ).json()
            headers = {"X-CSRF-Token": session["csrf_token"]}
            start = str(today + timedelta(days=1))
            query = {
                "main_origin": "苏州站",
                "city": "苏州",
                "companion_origins": [],
                "max_distance_km": 500,
                "start_date": start,
                "end_date": start,
                "scenery_types": [
                    "lake",
                    "park",
                    "museum",
                    "mountain",
                    "sea",
                    "old_town",
                ],
                "scenery_match_mode": "any",
            }
            response = client.post(
                "/api/v1/recommendations", json=query, headers=headers
            )
            assert response.status_code == 200
            result = response.json()
            ids = [i["destination"]["provider_id"] for i in result["items"]]
            context = {
                "page": "/recommend",
                "history_id": result["history_id"],
                "selected_ids": ids[:2],
                "visible_places": [
                    {
                        "id": i["destination"]["provider_id"],
                        "name": i["destination"]["name"],
                    }
                    for i in result["items"]
                ],
            }

            def command(label, message, required, current, check=None, clarify=False):
                if focused_cases and label not in focused_cases:
                    return None
                began = perf_counter()
                case = {"case": label, "message": message, "required": required}
                try:
                    request_id = str(uuid4())
                    response = client.post(
                        "/api/v1/assistant/commands/proposals",
                        headers=headers,
                        json={
                            "request_id": request_id,
                            "message": message,
                            "context": current,
                        },
                    )
                    case["proposal_status"] = response.status_code
                    if response.status_code != 200:
                        case["error_code"] = (
                            response.json().get("error", {}).get("code")
                        )
                        raise AssertionError("proposal rejected")
                    proposal = response.json()
                    case["actions"] = proposal["actions"]
                    case["tools"] = [a["tool"] for a in proposal["actions"]]
                    assert "copy_link" not in case["tools"], (
                        "unrequested clipboard action"
                    )
                    if clarify:
                        assert proposal["question"] and not proposal["actions"]
                        case["passed"] = True
                        return None
                    assert set(required) <= set(case["tools"]), "required task missing"
                    response = client.post(
                        "/api/v1/assistant/commands/execute",
                        headers=headers,
                        json={
                            "request_id": request_id,
                            "proposal": proposal["proposal"],
                            "confirmed": True,
                        },
                    )
                    assert response.status_code == 200
                    executed = response.json()
                    case["execution_status"] = executed["status"]
                    if executed.get("error"):
                        case["execution_error"] = executed["error"]["code"]
                    assert executed["status"] == "completed", executed.get(
                        "error", {}
                    ).get("code", "incomplete")
                    if check:
                        check(executed)
                    case["passed"] = True
                    return executed
                except (AssertionError, KeyError, ValueError, httpx.HTTPError) as exc:
                    case["passed"] = False
                    case["failure"] = type(exc).__name__
                    return None
                finally:
                    case["seconds"] = round(perf_counter() - began, 2)
                    report["cases"].append(case)
                    print(json.dumps(case, ensure_ascii=False), flush=True)

            def favorite_check(_):
                favorites = client.get("/api/v1/favorites").json()["favorites"]
                assert (
                    len(favorites) == 1
                    and favorites[0]["place"]["provider_place_id"] == ids[1]
                )

            command(
                "favorite-binding",
                "帮我把第二个地点收藏起来",
                ["favorite_place"],
                context,
                favorite_check,
            )
            opened = command(
                "detail-map",
                "打开第一个地点的详情，再看它的位置",
                ["open_detail", "open_map"],
                context,
            )
            if opened:
                assert all(
                    s["result"]["effect"]["arguments"].get("id") == ids[0]
                    for s in opened["steps"]
                    if s["tool"] in {"open_detail", "open_map"}
                )
            created = command(
                "create-and-invite",
                "就用选中的这两个建一个两人同行计划，名称是周末出游，然后生成邀请链接",
                ["create_plan_from_selection", "rotate_invite"],
                context,
            )
            plans = client.get("/api/v1/plans").json()["plans"]
            if created and len(plans) == 1:
                assert (
                    plans[0]["name"] == "周末出游" and plans[0]["expected_count"] == 2
                )
                plan_id = plans[0]["id"]
                current = {"page": "/plans/" + plan_id, "plan_id": plan_id}

                def plan_check(field, value):
                    def check(_):
                        plan = client.get("/api/v1/plans/" + plan_id).json()["plan"]
                        assert plan[field] == value

                    return check

                command(
                    "rename-plan",
                    "把当前计划改名为湖边见，人数不要动",
                    ["update_plan"],
                    current,
                    plan_check("name", "湖边见"),
                )

                def vote_check(_):
                    plan = client.get("/api/v1/plans/" + plan_id).json()["plan"]
                    assert plan["me"]["preferred_id"] == plan["candidates"][1]["id"]
                    assert set(plan["me"]["acceptable_ids"]) == {
                        c["id"] for c in plan["candidates"]
                    }

                def weather_check(_):
                    plan = client.get("/api/v1/plans/" + plan_id).json()["plan"]
                    assert all(
                        c["latest_weather"]["status"] == "success"
                        for c in plan["candidates"]
                    )

                command(
                    "vote",
                    "我首选第二个候选，第一个和第二个都可以接受",
                    ["submit_vote"],
                    current,
                    vote_check,
                )
                command(
                    "weather",
                    "重新检查一下这个计划的天气",
                    ["check_plan_weather"],
                    current,
                    weather_check,
                )
                command(
                    "close-decide",
                    "结束投票，把第二个候选确定为目的地",
                    ["close_voting", "decide_plan"],
                    current,
                    plan_check("status", "decided"),
                )
                command(
                    "reopen-voting",
                    "重新开放投票",
                    ["reopen_voting"],
                    current,
                    plan_check("status", "voting"),
                )
            command(
                "history-share",
                "分享这条查询历史，生成只读链接",
                ["create_share"],
                context,
            )
            # Two distinct owned plans are needed for a genuinely ambiguous target.
            extra = client.post(
                "/api/v1/plans",
                headers=headers,
                json={
                    "history_id": result["history_id"],
                    "candidate_ids": ids[:2],
                    "name": "另一场出游",
                    "expected_count": 2,
                },
            )
            assert extra.status_code == 201
            command(
                "ambiguous-target", "把那个删了", [], {"page": "/plans"}, clarify=True
            )
            command(
                "clarification-followup",
                "第一个计划，名称改成春日出游",
                ["update_plan"],
                {
                    "page": "/plans",
                    "conversation": [
                        {"role": "user", "content": "给计划改名"},
                        {
                            "role": "assistant",
                            "content": "要改哪个计划，改成什么名称？",
                        },
                    ],
                },
            )

            def condition_check(executed):
                query_step = next(
                    s["result"]
                    for s in executed["steps"]
                    if s["tool"] == "run_recommendation"
                )
                assert query_step["query_request"]["scenery_types"] == ["lake"]
                assert query_step["query_request"]["main_origin"] == "苏州站"
                assert query_step["query_request"]["start_date"] == start
                assert query_step["query"]["items"]

            command(
                "conditions-to-query",
                "只想看湖景，其他条件不变，改好后开始推荐",
                ["update_search_conditions", "run_recommendation"],
                {
                    "page": "/recommend",
                    "assistant_turn": {
                        "message": "当前条件",
                        "revision": 0,
                        "draft": {
                            "mode": "recommendation",
                            "main_origin": "苏州站",
                            "companion_origins": [],
                            "start_date": start,
                            "end_date": start,
                            "max_distance_km": 500,
                            "scenery_types": ["park"],
                        },
                    },
                },
                condition_check,
            )
    report["passed"] = sum(c["passed"] for c in report["cases"])
    report["total"] = len(report["cases"])
    report_name = "commands-live-focus.json" if focused_cases else "commands-live.json"
    (ROOT / "test-results" / report_name).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"Real model cases: {report['passed']}/{report['total']}; maps/weather remain Mock."
    )
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
