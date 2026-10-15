import json
from datetime import date

import httpx

from roambot.providers.assistant_diagnostics import compare_assistant_protocols


def test_date_role_comparison_is_three_native_calls_with_same_model_and_decode(capsys):
    bodies = []

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        assert body["model"] == "unchanged-model" and body["temperature"] == 0.2
        assert "response_format" not in body
        tool = body["tools"][0]
        schema = tool["function"]["parameters"]
        if len(bodies) == 1:
            assert set(schema["properties"]) == {"intent", "updates", "question"}
            assert set(schema["properties"]["updates"]["properties"]) == {"date_request"}
            assert set(schema["$defs"]) == {"AssistantDateRequest"}
            assert bodies[-1]["messages"][-1]["content"] == "10月16日回来，出发那天还没决定"
        else:
            assert "SceneryPreferenceParameters" in schema["$defs"]
        assert body["tool_choice"]["function"]["name"] == tool["function"]["name"]
        return httpx.Response(
            200,
            json={
                "model": "unchanged-model",
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
                                        "arguments": json.dumps(
                                            {
                                                "intent": "conditions",
                                                "updates": {
                                                    "date_request": {"end_date": "2026-10-16"}
                                                },
                                            }
                                        ),
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = compare_assistant_protocols(
            client,
            base_url="https://fixture.invalid/v1",
            key="fake-secret",
            model="unchanged-model",
            today=date(2026, 10, 13),
            date_roles=True,
        )
        assert client.event_hooks["response"] == []
    assert len(bodies) == report["request_limit"] == 3
    assert [row["arm"] for row in report["results"]] == [
        "minimal_date_native",
        "production_protocol",
        "production_protocol",
    ]
    assert bodies[0]["messages"][-1] == bodies[1]["messages"][-1]
    assert report["results"][0]["validated_reply"]["date_request"] == {"end_date": "2026-10-16"}
    assert "fake-secret" not in json.dumps(report) + capsys.readouterr().out


def test_diagnostic_reuses_production_protocol_and_stops_after_six_calls(capsys):
    bodies = []
    checkpoints = []

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        if len(bodies) % 2:
            content = {"destination_region_names": ["苏州"]}
        else:
            content = {
                "intent": "conditions",
                "edits": [
                    {
                        "field": "destination_region_names",
                        "operation": "set",
                        "value": ["苏州"],
                    }
                ],
            }
        native_message = {
            "content": None,
            "tool_calls": [
                {
                    "type": "function",
                    "function": {
                        "name": "submit_travel_intent",
                        "arguments": json.dumps(
                            {
                                "intent": "conditions",
                                "updates": {"destination_region_names": ["苏州"]},
                            }
                        ),
                    },
                }
            ],
        }
        return httpx.Response(
            200,
            json={
                "model": "reported-model",
                "usage": {"total_tokens": 77, "ignored": "secret"},
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": native_message
                        if "tools" in body
                        else {
                            "content": json.dumps(content, ensure_ascii=False),
                        },
                    }
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = compare_assistant_protocols(
            client,
            base_url="https://fixture.invalid/v1",
            key="fake-secret",
            model="fixture",
            today=date(2026, 10, 13),
            checkpoint=lambda value: checkpoints.append(len(value["results"])),
        )
        assert client.event_hooks["response"] == []
    assert len(bodies) == 6 and checkpoints == [1, 2, 3, 4, 5, 6]
    assert bodies[1]["messages"][-1] == {"role": "user", "content": "我想去苏州"}
    assert bodies[1]["messages"][0]["content"].startswith("你帮助用户选择出游地点")
    assert report["results"][1]["resolved_patch"] == {"destination_regions": ["320500"]}
    assert "tools" in bodies[1] and "response_format" not in bodies[1]
    assert report["results"][1]["function_name"] == "submit_travel_intent"
    assert report["results"][0]["returned_model"] == "reported-model"
    assert report["results"][0]["usage"] == {"total_tokens": 77}
    assert "fake-secret" not in json.dumps(report) + capsys.readouterr().out


def test_generated_content_and_validated_values_cannot_echo_key(capsys):
    key = 'fake-"secret'
    content = json.dumps({"intent": "conditions", "patch": {"main_origin": key}})

    def handler(request):
        body = json.loads(request.content)
        message = {"content": content}
        if "tools" in body:
            message = {
                "content": None,
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "submit_travel_intent",
                            "arguments": json.dumps(
                                {
                                    "intent": "conditions",
                                    "updates": {"main_origin": key},
                                }
                            ),
                        },
                    }
                ],
            }
        return httpx.Response(
            200,
            json={
                "model": key,
                "choices": [{"message": message}],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = compare_assistant_protocols(
            client,
            base_url="https://fixture.invalid",
            key=key,
            model="fixture",
            today=date(2026, 10, 13),
        )
    # The raw content is itself JSON-escaped. Escaped secrets must also be redacted.
    assert key not in json.dumps(report, ensure_ascii=False)
    assert report["results"][1]["validated_reply"]["patch"]["main_origin"] == "[redacted]"
    assert "fake-" not in report["results"][1]["arguments"]
    assert "fake-" not in capsys.readouterr().out


def test_rate_limit_preserves_partial_report_without_retry():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, json={"error": "fake-secret"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = compare_assistant_protocols(
            client,
            base_url="https://fixture.invalid",
            key="fake-secret",
            model="fixture",
            today=date(2026, 10, 13),
        )
    assert len(calls) == 1
    assert report["results"][0]["status"] == "rate_limited"
    assert "fake-secret" not in json.dumps(report)


def test_malformed_production_output_is_captured_without_masking_failure():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"intent":"unexpected"}'}}],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = compare_assistant_protocols(
            client,
            base_url="https://fixture.invalid",
            key="fake-secret",
            model="fixture",
            today=date(2026, 10, 13),
        )
    assert all(
        row["status"] == "bad_response"
        for row in report["results"]
        if row["arm"] == "production_protocol"
    )
    assert report["results"][1]["content"] == '{"intent":"unexpected"}'
