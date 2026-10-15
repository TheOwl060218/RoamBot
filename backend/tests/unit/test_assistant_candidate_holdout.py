import importlib
import json
from datetime import date

import httpx
import pytest


def module():
    return importlib.import_module("roambot.providers.assistant_candidate_holdout")


def reply(arguments):
    return httpx.Response(
        200,
        json={
            "model": "qwen3.7-plus",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "tool_calls": [
                            {
                                "type": "function",
                                "function": {
                                    "name": "submit_travel_intent",
                                    "arguments": json.dumps(arguments),
                                },
                            }
                        ]
                    },
                }
            ],
        },
    )


def test_candidate_holdout_uses_real_service_pending_memory_without_history():
    subject = module()
    bodies = []

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        assert body["model"] == "qwen3.7-plus"
        assert body["enable_thinking"] is False
        assert request.extensions["timeout"]["read"] == 8
        if len(bodies) == 1:
            return reply(
                {"intent": "conditions", "updates": {"date_request": {"end_date": "2026-10-16"}}}
            )
        # Second turn must use the actual previous service memory, not expected values.
        assert "2026-10-16" in json.dumps(body["messages"], ensure_ascii=False)
        assert sum(m["role"] == "user" for m in body["messages"]) == 1
        return reply({"intent": "conditions", "updates": {"date_request": {"offset_days": 1}}})

    scenarios = [
        {
            "name": "pending",
            "draft": {},
            "history_limit": 0,
            "turns": [
                {
                    "message": "返程先定",
                    "expected": {},
                    "allowed_changes": [],
                    "expected_pending": {"end_date": "2026-10-16"},
                    "question": True,
                },
                {
                    "message": "补充启程日",
                    "expected": {"start_date": "2026-10-14", "end_date": "2026-10-16"},
                    "allowed_changes": ["start_date", "end_date"],
                    "expected_pending": None,
                },
            ],
        }
    ]
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = subject.candidate_holdout(
            client,
            base_url="https://fixture.invalid/v1",
            key="fake-secret",
            model="qwen3.7-plus",
            today=date(2026, 10, 13),
            scenarios=scenarios,
        )
    assert report["summary"]["passed"] == 2
    assert report["model_calls"] == 2
    assert report["website_model_changed"] is False
    assert "fake-secret" not in json.dumps(report)


def test_candidate_holdout_counts_bounded_format_repair_and_rejects_unrequested_edit():
    subject = module()
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return reply({"intent": "conditions", "updates": None})
        return reply(
            {"intent": "conditions", "updates": {"max_distance_km": 70, "main_origin": "别的城市"}}
        )

    scenarios = [
        {
            "name": "scope",
            "draft": {"main_origin": "广州"},
            "turns": [
                {
                    "message": "只修改范围",
                    "expected": {"max_distance_km": 70},
                    "allowed_changes": ["max_distance_km"],
                }
            ],
        }
    ]
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = subject.candidate_holdout(
            client,
            base_url="https://fixture.invalid/v1",
            key="fake-secret",
            model="qwen3.7-plus",
            today=date(2026, 10, 13),
            scenarios=scenarios,
        )
    assert report["summary"]["passed"] == 0
    assert "unrequested_main_origin" in report["results"][0]["errors"]
    assert report["results"][0]["model_calls"] == 2
    assert report["model_calls"] == 2
    assert len(report["results"][0]["parameter_attempts"]) == 2
    assert (
        json.loads(report["results"][0]["parameter_attempts"][0]["synthetic_arguments"])["updates"]
        is None
    )
    assert (
        json.loads(report["results"][0]["parameter_attempts"][1]["synthetic_arguments"])["updates"][
            "main_origin"
        ]
        == "别的城市"
    )


def test_focus_captures_two_turns_not_repeated_full_acceptance():
    subject = module()
    calls = []
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: calls.append(request) or reply({"intent": "conditions"})
        )
    ) as client:
        report = subject.candidate_holdout(
            client,
            base_url="https://fixture.invalid/v1",
            key="fake-secret",
            model="qwen3.7-plus",
            today=date(2026, 10, 13),
            focus=True,
        )
    assert report["summary"]["planned"] == 2
    assert report["request_limit"] == 4
    assert len(calls) == 2
    assert all(row["scenario"] == "holdout_destination_scope" for row in report["results"])


@pytest.mark.parametrize("status", [401, 403, 404, 429])
def test_candidate_routing_or_quota_failure_stops_without_retry_or_false_acceptance(status):
    subject = module()
    calls = []
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: calls.append(request) or httpx.Response(status, text="fake-secret")
        )
    ) as client:
        report = subject.candidate_holdout(
            client,
            base_url="https://fixture.invalid/v1",
            key="fake-secret",
            model="qwen3.7-plus",
            today=date(2026, 10, 13),
        )
    assert len(calls) == 1
    assert report["summary"]["planned"] == 15
    assert report["summary"]["passed"] == 0
    assert report["stopped_reason"]
    assert "fake-secret" not in json.dumps(report)


def test_candidate_fifteen_failed_turns_never_exceed_thirty_calls():
    subject = module()
    calls = []
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: (
                calls.append(request) or reply({"intent": "conditions", "updates": None})
            )
        )
    ) as client:
        report = subject.candidate_holdout(
            client,
            base_url="https://fixture.invalid/v1",
            key="fake-secret",
            model="qwen3.7-plus",
            today=date(2026, 10, 13),
        )
    assert len(calls) == report["model_calls"] == report["request_limit"] == 30
    assert report["summary"]["tested"] == 15
    assert report["summary"]["passed"] == 0
    assert all(row["status"] == 503 and row["model_calls"] == 2 for row in report["results"])


def test_candidate_rejects_oversized_suite_before_network():
    subject = module()
    with (
        httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("no network"))) as client,
        pytest.raises(ValueError, match="fifteen"),
    ):
        subject.candidate_holdout(
            client,
            base_url="https://fixture.invalid/v1",
            key="fake-secret",
            model="qwen3.7-plus",
            today=date(2026, 10, 13),
            scenarios=[{"draft": {}, "turns": [{}] * 16}],
        )
