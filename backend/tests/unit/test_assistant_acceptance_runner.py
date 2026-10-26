import importlib.util
import json
from pathlib import Path

import httpx


def runner():
    spec = importlib.util.spec_from_file_location(
        "assistant_acceptance_runner",
        Path(__file__).resolve().parents[3] / "scripts/assistant_acceptance.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_city_suffix_is_not_counted_as_a_semantic_failure():
    module = runner()
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "source": "live",
                    "patch": {"main_origin": "常州市"},
                    "reply": "ok",
                },
            )
        )
    ) as client:
        results = module.evaluate(
            client,
            "http://127.0.0.1",
            [
                {
                    "name": "city_alias",
                    "draft": {},
                    "turns": [{"message": "测试", "expected": {"main_origin": "常州"}}],
                }
            ],
        )
    assert results[0]["errors"] == []


def test_runner_rejects_new_category_with_stale_description_and_search_terms():
    module = runner()
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, json={"source": "live", "reply": "ok", "patch": {"scenery_types": ["museum"]}}
            )
        )
    ) as client:
        results = module.evaluate(
            client,
            "http://127.0.0.1",
            [
                {
                    "name": "stale_preference",
                    "draft": {
                        "scenery_types": ["park"],
                        "scenery_query": "绿地",
                        "scenery_keywords": ["公园"],
                    },
                    "turns": [
                        {
                            "message": "更换偏好",
                            "expected": {},
                            "required_types": ["museum"],
                            "required_patch_fields": [
                                "scenery_types",
                                "scenery_query",
                                "scenery_keywords",
                            ],
                            "forbidden_values": {
                                "scenery_query": ["绿地"],
                                "scenery_keywords": ["公园"],
                            },
                        }
                    ],
                }
            ],
        )
    assert "missing_patch_scenery_query" in results[0]["errors"]
    assert "missing_patch_scenery_keywords" in results[0]["errors"]
    assert "stale_scenery_query" in results[0]["errors"]
    assert "stale_scenery_keywords" in results[0]["errors"]


def test_runner_accepts_atomic_preference_without_overconstraining_wording():
    module = runner()
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "source": "live",
                    "reply": "ok",
                    "patch": {
                        "scenery_types": ["museum"],
                        "scenery_query": "文化展馆，不去公园",
                        "scenery_keywords": ["展馆"],
                    },
                },
            )
        )
    ) as client:
        results = module.evaluate(
            client,
            "http://127.0.0.1",
            [
                {
                    "name": "replacement",
                    "draft": {"scenery_query": "绿地", "scenery_keywords": ["公园"]},
                    "turns": [
                        {
                            "message": "更换偏好",
                            "expected": {},
                            "required_patch_fields": [
                                "scenery_types",
                                "scenery_query",
                                "scenery_keywords",
                            ],
                            "forbidden_values": {
                                "scenery_query": ["绿地"],
                                "scenery_keywords": ["公园"],
                            },
                        }
                    ],
                }
            ],
        )
    assert results[0]["errors"] == []


def test_independent_date_role_controls_require_end_fragment_not_inferred_start():
    from datetime import date

    module = runner()
    controls = module.date_role_cases(date(2026, 10, 13))
    assert len(controls) == 4
    for case in controls[:3]:
        turn = case["turns"][0]
        assert case["history_limit"] == 0 and case["draft"] == {}
        assert turn["allowed_changes"] == [] and turn["question"]
        assert set(turn["expected_pending"]) == {"end_date"}
    assert controls[-1]["turns"][0]["expected"] == {
        "start_date": "2026-10-16",
        "end_date": "2026-10-16",
    }


def test_city_and_its_station_remain_different_locations():
    module = runner()
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "source": "live",
                    "patch": {"main_origin": "苏州市"},
                    "reply": "ok",
                },
            )
        )
    ) as client:
        results = module.evaluate(
            client,
            "http://127.0.0.1",
            [
                {
                    "name": "station",
                    "draft": {},
                    "turns": [{"message": "测试", "expected": {"main_origin": "苏州站"}}],
                }
            ],
        )
    assert results[0]["errors"] == ["main_origin"]


def test_runner_detects_unrequested_changes_outside_allowed_fields():
    module = runner()
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "source": "live",
                    "reply": "ok",
                    "patch": {"max_distance_km": 80, "scenery_keywords": ["南京"]},
                },
            )
        )
    ) as client:
        results = module.evaluate(
            client,
            "http://127.0.0.1",
            [
                {
                    "name": "scope",
                    "draft": {"scenery_keywords": ["湖"]},
                    "turns": [
                        {
                            "message": "角色待定",
                            "expected": {"max_distance_km": 80},
                            "allowed_changes": ["max_distance_km"],
                        }
                    ],
                }
            ],
        )
    assert "unrequested_scenery_keywords" in results[0]["errors"]


def test_runner_carries_pending_semantics_without_history():
    module = runner()

    def handle(request):
        data = json.loads(request.content)
        if data["message"] == "first":
            return httpx.Response(
                200,
                json={
                    "source": "live",
                    "reply": "ask",
                    "conversation_state": {"pending_date_request": {"duration_days": 3}},
                },
            )
        remembered = data.get("conversation_state", {}).get("pending_date_request")
        return httpx.Response(
            200,
            json={
                "source": "live",
                "reply": "ok",
                "patch": {"max_distance_km": 80 if remembered and not data["history"] else 20},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        results = module.evaluate(
            client,
            "http://127.0.0.1",
            [
                {
                    "name": "memory",
                    "draft": {},
                    "history_limit": 0,
                    "turns": [
                        {"message": "first", "expected": {}},
                        {"message": "second", "expected": {"max_distance_km": 80}},
                    ],
                }
            ],
        )
    assert results[1]["errors"] == []


def test_runner_failed_turn_preserves_draft_and_pending_for_next_request():
    module = runner()
    calls = []

    def handle(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            return httpx.Response(
                200,
                json={
                    "source": "live",
                    "reply": "ask",
                    "conversation_state": {"pending_date_request": {"duration_days": 2}},
                },
            )
        if len(calls) == 2:
            return httpx.Response(503, json={"error": {"code": "assistant_unavailable"}})
        return httpx.Response(200, json={"source": "live", "reply": "ok", "patch": {}})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        results = module.evaluate(
            client,
            "http://127.0.0.1",
            [
                {
                    "name": "retain",
                    "draft": {"main_origin": "扬州"},
                    "turns": [
                        {"message": "one", "expected": {}},
                        {"message": "two", "expected": {}},
                        {"message": "three", "expected": {}},
                    ],
                }
            ],
        )
    assert results[1]["errors"] == ["http_status"]
    assert calls[2]["draft"] == {"main_origin": "扬州"}
    assert calls[2]["conversation_state"] == {"pending_date_request": {"duration_days": 2}}


def test_runner_does_not_call_demo_output_live_acceptance():
    module = runner()
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "source": "demo",
                    "patch": {"main_origin": "扬州"},
                    "reply": "ok",
                },
            )
        )
    ) as client:
        results = module.evaluate(
            client,
            "http://127.0.0.1",
            [
                {
                    "name": "demo",
                    "draft": {},
                    "turns": [{"message": "测试", "expected": {"main_origin": "扬州"}}],
                }
            ],
        )
    assert results[0]["errors"] == ["not_live"]


def test_native_smoke_is_six_turns_and_checks_all_unrelated_fields():
    module = runner()
    assert hasattr(module, "native_smoke_cases"), "bounded native smoke suite missing"
    from datetime import date

    scenarios = module.native_smoke_cases(date(2026, 10, 13))
    assert sum(len(item["turns"]) for item in scenarios) == 6
    assert all("allowed_changes" in turn for item in scenarios for turn in item["turns"])


def test_runner_detects_return_date_replaced_by_coincident_duration():
    module = runner()
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "source": "live",
                    "patch": {},
                    "reply": "ask",
                    "question": "哪天出发？",
                    "conversation_state": {"pending_date_request": {"duration_days": 3}},
                },
            )
        )
    ) as client:
        results = module.evaluate(
            client,
            "http://127.0.0.1",
            [
                {
                    "name": "return",
                    "draft": {},
                    "turns": [
                        {
                            "message": "返程先定",
                            "expected": {},
                            "allowed_changes": [],
                            "expected_pending": {"end_date": "2026-10-16"},
                        }
                    ],
                }
            ],
        )
    assert "pending_date_request" in results[0]["errors"]


def test_release_suite_checks_roles_companions_and_reverse_cancellation_independently():
    from datetime import date

    module = runner()
    scenarios = module.release_cases(date(2026, 10, 13))
    assert sum(len(case["turns"]) for case in scenarios) == 12
    assert all("allowed_changes" in turn for case in scenarios for turn in case["turns"])
    by_name = {case["name"]: case for case in scenarios}
    companion_turns = by_name["release_station_companions"]["turns"]
    assert companion_turns[0]["expected"]["companion_origins"] == ["南京南站", "杭州东站"]
    assert companion_turns[1]["expected"]["companion_origins"] == ["南京南站"]
    assert companion_turns[2]["expected"]["companion_origins"] == []
    assert by_name["release_reverse_cancellation"]["turns"][1]["expected"] == {
        "max_distance_km": None,
        "destination_regions": ["330800"],
    }
    pending = by_name["release_pending_return"]
    assert pending["history_limit"] == 0
    assert pending["turns"][0]["expected_pending"] == {"end_date": "2026-10-17"}
    assert pending["turns"][2]["expected"] == {"start_date": "2026-10-14", "end_date": "2026-10-17"}


def test_role_correction_cannot_pass_with_residual_inferred_destination():
    from datetime import date

    module = runner()
    scenario = next(
        case for case in module.cases(date(2026, 10, 13)) if case["name"] == "origin_then_dates"
    )
    patches = iter(
        [
            {"destination_regions": ["320500"]},
            {"main_origin": "苏州"},
            {"start_date": "2026-10-14", "end_date": "2026-10-17"},
        ]
    )
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "source": "live",
                    "patch": next(patches),
                    "question": "日期和风景还需要补充",
                    "reply": "测试",
                },
            )
        )
    ) as client:
        results = module.evaluate(client, "http://127.0.0.1", [scenario])
    assert "unexpected_destination_regions" in results[0]["errors"]
    assert "unexpected_destination_regions" in results[1]["errors"]
