import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from test_discovery_commands import source_job
from test_history import register

from roambot.api.routes.commands import get_business_planner
from roambot.api.routes.discovery import get_discovery_factory
from roambot.domain.discovery import Finish
from roambot.services.discovery import DiscoveryRun


def archive(client, csrf):
    key = source_job(client, csrf)
    source = client.get("/api/v1/discovery/jobs/" + key).json()
    assert source["history_id"]
    return key, source["history_id"]


def test_private_dialogue_survives_history_restore_and_reaches_followup_not_public_share(
    auth_api_fixture,
):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "archive_dialogue_owner")
    headers = {"X-CSRF-Token": csrf}
    conversation = [
        {"role": "user", "content": "想找能坐着读书的地方，不要太吵"},
        {"role": "assistant", "content": "已找到这些去处。"},
        {"role": "user", "content": "再近一点"},
    ]
    request = "本次想找可以坐着读书的地方，不要太吵，距离更近"
    title = "附近安静的阅读空间"
    scope = {"kind": "nearby", "region": None}
    key = source_job(
        client,
        csrf,
        message="再近一点",
        conversation=conversation,
        search_request=request,
        display_title=title,
        search_scope=scope,
    )
    snapshot = client.get("/api/v1/discovery/jobs/" + key).json()
    history_id = snapshot["history_id"]
    history = client.get("/api/v1/history/" + history_id).json()["history"]
    assert history["request"]["conversation"][:3] == conversation
    assert history["request"]["search_request"] == request
    assert history["result"]["display_title"] == title
    assert history["result"]["search_scope"] == scope
    client.app.state.discovery_jobs.jobs.pop(key)
    restored = client.post("/api/v1/discovery/history/" + history_id + "/restore", headers=headers)
    assert restored.status_code == 200
    assert restored.json()["conversation"] == snapshot["conversation"]
    assert restored.json()["search_request"] == request
    assert restored.json()["display_title"] == title
    assert restored.json()["search_scope"] == scope
    seen = []

    def factory(body, previous):
        assert previous["search_request"] == request
        assert previous["display_title"] == title
        assert previous["search_scope"] == scope
        seen.extend(previous["conversation"])
        return DiscoveryRun(
            body,
            None,
            None,
            None,
            lambda _: ("finish", Finish(reply="仅检查已恢复的上下文。")),
            previous,
        )

    client.app.dependency_overrides[get_discovery_factory] = lambda: factory
    followup = client.post(
        "/api/v1/discovery/jobs",
        headers=headers,
        json={"message": "换到杭州", "previous_id": restored.json()["id"]},
    )
    assert followup.status_code == 200
    assert seen == snapshot["conversation"]
    shared = client.post("/api/v1/history/" + history_id + "/share", headers=headers).json()[
        "share"
    ]
    public = client.get("/api/v1/public/shares/" + shared["url"].split("/")[-1]).json()["snapshot"]
    assert "conversation" not in public
    assert "search_request" not in public
    assert "display_title" not in public
    assert request not in json.dumps(public, ensure_ascii=False)
    assert conversation[0]["content"] not in json.dumps(public, ensure_ascii=False)


def test_discovery_archive_is_immutable_owned_optional_and_restores_without_provider(
    auth_api_fixture,
):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "archive_owner")
    key, history_id = archive(client, csrf)
    original = client.get("/api/v1/history/" + history_id).json()["history"]
    assert original["mode"] == "discovery"
    assert original["result"]["schema_version"] == "discovery-v1"
    assert original["request"]["context"]["start_date"] is None
    assert original["request"]["context"]["origin"] is None
    assert len(original["result"]["cards"]) == 2
    assert not any(
        word in json.dumps(original["result"])
        for word in ('"score"', "scenery_tags", "group_accessibility")
    )
    client.app.state.discovery_jobs.jobs[key][2].cards[0]["reason"] = "未写入历史的新内容"
    assert client.get("/api/v1/history/" + history_id).json()["history"] == original
    # Simulate in-memory job loss; stored cards remain usable, without any model/map call.
    client.app.state.discovery_jobs.jobs.pop(key)
    restored = client.post(
        "/api/v1/discovery/history/" + history_id + "/restore", headers={"X-CSRF-Token": csrf}
    )
    assert restored.status_code == 200
    assert restored.json()["cards"] == original["result"]["cards"]
    assert (
        client.post(
            "/api/v1/discovery/history/" + history_id + "/restore", headers={"X-CSRF-Token": csrf}
        ).json()["id"]
        == restored.json()["id"]
    )
    with TestClient(client.app) as other:
        other_csrf = register(other, "archive_other")
        assert other.get("/api/v1/history/" + history_id).status_code == 404
        assert (
            other.post(
                "/api/v1/discovery/history/" + history_id + "/restore",
                headers={"X-CSRF-Token": other_csrf},
            ).status_code
            == 404
        )


def test_shared_discovery_and_plan_keep_real_facts_without_scores_and_reuse_vote_lifecycle(
    auth_api_fixture,
):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "discovery_lifecycle")
    headers = {"X-CSRF-Token": csrf}
    key, history_id = archive(client, csrf)
    shared = client.post("/api/v1/history/" + history_id + "/share", headers=headers)
    assert shared.status_code == 201
    share = shared.json()["share"]
    public_path = "/api/v1/public/shares/" + share["url"].split("/")[-1]
    with TestClient(client.app) as public:
        snapshot = public.get(public_path).json()["snapshot"]
        assert snapshot["mode"] == "discovery" and snapshot["start_date"] is None
        assert len(snapshot["cards"]) == 2
        raw = json.dumps(snapshot)
        for word in ("coordinate", "route", "origin", "score", "scenery_tags", "facts"):
            assert word not in raw
    ids = [c["place"]["id"] for c in client.get("/api/v1/discovery/jobs/" + key).json()["cards"]]
    tomorrow = (datetime.now(timezone(timedelta(hours=8))).date() + timedelta(days=1)).isoformat()
    missing = client.post(
        "/api/v1/plans", headers=headers, json={"history_id": history_id, "candidate_ids": ids}
    )
    assert missing.status_code == 422 and missing.json()["error"]["code"] == "plan_dates_required"
    created = client.post(
        "/api/v1/plans",
        headers=headers,
        json={
            "history_id": history_id,
            "candidate_ids": ids,
            "name": "周末出游",
            "expected_count": 2,
            "start_date": tomorrow,
            "end_date": tomorrow,
        },
    )
    assert created.status_code == 201, created.text
    plan = created.json()["plan"]
    assert plan["start_date"] == tomorrow and plan["expected_count"] == 2
    assert all(c["snapshot"]["schema_version"] == "discovery-v1" for c in plan["candidates"])
    assert all(
        "score" not in c["snapshot"] and "group_accessibility" not in c["snapshot"]
        for c in plan["candidates"]
    )
    path = "/api/v1/plans/" + plan["id"]
    checked = client.post(path + "/weather-checks", headers=headers)
    assert checked.status_code == 200, checked.text
    for candidate in checked.json()["plan"]["candidates"]:
        assert candidate["latest_weather"]["status"] == "success"
        assert candidate["latest_weather"]["daily_suitability"] == []
        assert candidate["latest_weather"]["risk"] is None
    link = client.post(path + "/invite/rotate", headers=headers).json()["url"]
    invite_path = "/api/v1/public/plans/" + link.split("/")[-1]
    with TestClient(client.app) as guest:
        joined = guest.post(invite_path + "/join", json={"nickname": "同行者"})
        assert joined.status_code == 200
        vote = {"preferred_id": ids[0], "acceptable_ids": ids}
        assert (
            guest.put(
                invite_path + "/vote",
                headers={"X-Plan-CSRF": joined.json()["anonymous_csrf"]},
                json=vote,
            ).status_code
            == 200
        )
        assert client.put(path + "/vote", headers=headers, json=vote).status_code == 200
        assert client.put(path + "/voting-close", headers=headers).status_code == 200
        decided = client.put(path + "/decision", headers=headers, json={"candidate_id": ids[0]})
        assert decided.status_code == 200 and decided.json()["plan"]["status"] == "decided"
        assert guest.get(invite_path).json()["plan"]["final_candidate_id"] == ids[0]
    assert client.delete("/api/v1/shares/" + share["id"], headers=headers).status_code == 204
    assert client.get(public_path).status_code == 404
    # Original archive never acquired a synthetic score, plan date or new weather.
    original = client.get("/api/v1/history/" + history_id).json()["history"]
    assert original["request"]["context"]["start_date"] is None
    assert all(c["weather"] is None for c in original["result"]["cards"])


def test_date_clarification_then_create_and_invite_is_one_authorized_business_sequence(
    auth_api_fixture,
):
    client, _, _ = auth_api_fixture()
    csrf = register(client, "discovery_chat_plan")
    key, history_id = archive(client, csrf)
    context = {
        "page": "/explore",
        "discovery_job_id": key,
        "selected_ids": ["amap:verified1", "amap:verified2"],
    }
    client.app.dependency_overrides[get_business_planner] = lambda: (
        lambda body, context: {
            "actions": [{"tool": "create_plan_from_selection", "arguments": {"name": "聊天计划"}}]
        }
    )
    first = client.post(
        "/api/v1/assistant/commands/proposals",
        headers={"X-CSRF-Token": csrf},
        json={"request_id": str(uuid4()), "message": "用这两个发起聊天计划", "context": context},
    )
    assert first.status_code == 200 and first.json()["question"] == "计划安排哪天？"
    assert first.json()["actions"] == []
    assert client.get("/api/v1/plans").json()["plans"] == []
    tomorrow = (datetime.now(timezone(timedelta(hours=8))).date() + timedelta(days=1)).isoformat()
    client.app.dependency_overrides[get_business_planner] = lambda: (
        lambda body, context: {
            "actions": [
                {
                    "tool": "create_plan_from_selection",
                    "arguments": {
                        "name": "聊天计划",
                        "start_date": tomorrow,
                        "end_date": tomorrow,
                        "date_quote": "明天",
                        "expected_count": 2,
                    },
                },
                {"tool": "rotate_invite", "arguments": {}},
            ]
        }
    )
    planned = client.post(
        "/api/v1/assistant/commands/proposals",
        headers={"X-CSRF-Token": csrf},
        json={
            "request_id": str(uuid4()),
            "message": "明天，两个人，顺便生成邀请",
            "context": context,
        },
    )
    assert planned.status_code == 200 and planned.json()["requires_confirmation"]
    result = client.post(
        "/api/v1/assistant/commands/execute",
        headers={"X-CSRF-Token": csrf},
        json={
            "request_id": planned.json()["request_id"],
            "proposal": planned.json()["proposal"],
            "confirmed": True,
        },
    )
    assert result.json()["status"] == "completed", result.text
    assert [s["tool"] for s in result.json()["steps"]] == [
        "create_plan_from_selection",
        "rotate_invite",
    ]
    assert client.get("/api/v1/plans").json()["plans"][0]["name"] == "聊天计划"
    assert len(client.get("/api/v1/history").json()["histories"]) == 1
