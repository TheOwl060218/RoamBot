import importlib
import json
from datetime import date

import httpx
import pytest


def comparison():
    return importlib.import_module("roambot.providers.assistant_model_comparison")


def completion(arguments, model):
    return httpx.Response(
        200,
        json={
            "model": model,
            "usage": {"total_tokens": 42},
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "type": "function",
                                "function": {
                                    "name": "submit_travel_intent",
                                    "arguments": json.dumps(arguments),
                                },
                            }
                        ],
                    },
                }
            ],
        },
    )


def test_full_protocol_comparison_is_six_single_calls_and_scores_semantics_separately(capsys):
    module = comparison()
    bodies = []

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        assert body["temperature"] == 0.2 and body["max_tokens"] == 2048
        assert "SceneryPreferenceParameters" in body["tools"][0]["function"]["parameters"]["$defs"]
        assert request.extensions["timeout"]["read"] == 8
        assert "response_format" not in body
        if body["model"] == "qwen-plus":
            assert body["enable_thinking"] is False
        else:
            assert "enable_thinking" not in body
        index = (len(bodies) - 1) // 2
        updates = (
            {"date_request": {"end_date": "2026-10-16"}},
            {"max_distance_km": 75},
            {
                "scenery_preference": {
                    "categories": ["museum"],
                    "description": "文化展馆",
                    "keywords": ["展馆"],
                }
            },
        )[index]
        if index == 0 and body["model"] == "qwen-turbo":
            updates = {"date_request": {"offset_days": 3}}
        reply = {"intent": "conditions", "updates": updates}
        if index == 1:
            reply["question"] = "这个城市是出发地还是目的地？"
        return completion(reply, body["model"])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = module.compare_models(
            client,
            base_url="https://fixture.invalid/v1",
            key="fake-secret",
            baseline="qwen-turbo",
            candidate="qwen-plus",
            today=date(2026, 10, 13),
        )
    assert len(bodies) == report["request_limit"] == 6
    for index in range(0, 6, 2):
        assert bodies[index]["messages"] == bodies[index + 1]["messages"]
        assert bodies[index]["tools"] == bodies[index + 1]["tools"]
    assert report["summary"]["qwen-turbo"]["passed"] == 2
    assert report["summary"]["qwen-plus"]["passed"] == 3
    assert report["results"][0]["status"] == "ok"
    assert report["results"][0]["semantic_errors"]
    assert report["results"][0]["model_calls"] == 1
    assert report["latency_metric"] == "complete_validated_parameters_not_first_token"
    assert "fake-secret" not in json.dumps(report) + capsys.readouterr().out


def test_timeout_has_no_silent_retry_or_wait_and_is_not_a_semantic_pass():
    module = comparison()
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("fake-secret", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = module.compare_models(
            client,
            base_url="https://fixture.invalid",
            key="fake-secret",
            baseline="qwen-turbo",
            candidate="qwen-plus",
            today=date(2026, 10, 13),
        )
    assert len(calls) == 6
    assert all(row["status"] == "timeout" and row["model_calls"] == 1 for row in report["results"])
    assert report["summary"]["qwen-plus"]["passed"] == 0
    assert report["summary"]["qwen-plus"]["median_ms"] is None


@pytest.mark.parametrize("status", [401, 403, 404, 429])
def test_routing_or_quota_failure_stops_bounded_probe(status):
    module = comparison()
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="fake-secret")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = module.compare_models(
            client,
            base_url="https://fixture.invalid",
            key="fake-secret",
            baseline="qwen-turbo",
            candidate="qwen-plus",
            today=date(2026, 10, 13),
        )
    assert len(calls) == 1
    assert report["results"][0]["status"] != "ok"
    assert "fake-secret" not in json.dumps(report)


def test_unknown_thinking_policy_is_rejected_before_network():
    module = comparison()
    with (
        httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("no network"))) as client,
        pytest.raises(ValueError),
    ):
        module.compare_models(
            client,
            base_url="https://fixture.invalid",
            key="fake-secret",
            baseline="qwen-turbo",
            candidate="unknown-reasoner",
            today=date(2026, 10, 13),
        )


def test_small_sample_latency_summary_keeps_slow_responses_visible(monkeypatch):
    module = comparison()
    times = iter([0, 1, 1, 7, 7, 9, 9, 12, 12, 13, 13, 17])
    monkeypatch.setattr(module, "perf_counter", lambda: next(times))
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        model = json.loads(request.content)["model"]
        updates = (
            {"date_request": {"end_date": "2026-10-16"}},
            {"max_distance_km": 75},
            {
                "scenery_preference": {
                    "categories": ["museum"],
                    "description": "文化展馆",
                    "keywords": ["展馆"],
                }
            },
        )[(count - 1) // 2]
        return completion(
            {"intent": "conditions", "updates": updates, "question": "请明确未定条件"}, model
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = module.compare_models(
            client,
            base_url="https://fixture.invalid",
            key="fake-key",
            baseline="qwen-turbo",
            candidate="qwen-plus",
            today=date(2026, 10, 13),
        )
    candidate = report["summary"]["qwen-plus"]
    assert candidate["median_ms"] == 4000 and candidate["max_ms"] == 6000
    assert candidate["over_5s"] == 1
    assert report["summary"]["qwen-turbo"]["median_ms"] == 1000


def test_deepseek_non_thinking_policy_does_not_alter_tool_or_call_count():
    module = comparison()
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        if body["model"] == "DeepSeek-V4-Flash":
            assert body["thinking"] == {"type": "disabled"}
            assert "enable_thinking" not in body
        return completion({"intent": "conditions"}, body["model"])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = module.compare_models(
            client,
            base_url="https://fixture.invalid",
            key="fake-key",
            baseline="qwen-turbo",
            candidate="DeepSeek-V4-Flash",
            today=date(2026, 10, 13),
        )
    assert len(calls) == 6
    assert report["summary"]["DeepSeek-V4-Flash"]["passed"] == 0


def test_saved_report_archives_previous_evidence_and_never_includes_key(tmp_path, monkeypatch):
    module = comparison()
    output = tmp_path / "comparison.json"
    output.write_text('"previous evidence"', encoding="utf-8")
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: completion(
                {"intent": "conditions"}, json.loads(request.content)["model"]
            )
        )
    )
    monkeypatch.setattr(module.httpx, "Client", lambda **_: client)
    result = module.run_model_comparison(
        "https://fixture.invalid", "fake-key", "qwen-turbo", "qwen-plus", output
    )
    assert result == 1, "completed requests alone do not imply semantic success"
    assert json.loads(output.read_text(encoding="utf-8"))["summary"]["qwen-plus"]["passed"] == 0
    archived = list(tmp_path.glob("comparison-*.json"))
    assert len(archived) == 1 and archived[0].read_text(encoding="utf-8") == '"previous evidence"'
    assert "fake-key" not in output.read_text(encoding="utf-8")
