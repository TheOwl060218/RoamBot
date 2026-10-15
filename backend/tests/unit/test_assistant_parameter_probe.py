import json
from datetime import date

import httpx
import pytest

from roambot.providers import assistant_diagnostics


def probe(client, **options):
    run = getattr(assistant_diagnostics, "probe_assistant_parameters", None)
    assert callable(run), "the approved bounded parameter probe is not implemented"
    return run(
        client,
        base_url="https://fixture.invalid/v1",
        key='fake-"secret',
        model="unchanged-model",
        today=date(2026, 10, 13),
        **options,
    )


def result(arguments, name="submit_travel_intent"):
    return httpx.Response(
        200,
        json={
            "model": "unchanged-model",
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "type": "function",
                                "id": "synthetic-call",
                                "function": {
                                    "name": name,
                                    "arguments": json.dumps(arguments, ensure_ascii=False),
                                },
                            }
                        ],
                    },
                }
            ],
        },
    )


def test_parameter_probe_has_exactly_three_calls_and_separate_semantic_verdicts():
    sent, snapshots = [], []

    def handle(request):
        sent.append(json.loads(request.content))
        replies = [
            {
                "intent": "conditions",
                "updates": {},
                "clear_fields": ["scenery_types", "scenery_query", "scenery_keywords"],
            },
            {
                "intent": "conditions",
                "updates": {"destination_region_names": ["苏州"]},
                "clear_fields": [],
            },
            {
                "intent": "conditions",
                "updates": {"date_request": {"offset_days": 1, "duration_days": 4}},
                "clear_fields": [],
            },
        ]
        return result(replies[len(sent) - 1])

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        report = probe(client, checkpoint=lambda r: snapshots.append(len(r["results"])))
    assert len(sent) == 3 and snapshots == [1, 2, 3]
    assert all(r["status"] == "ok" and r["semantic_errors"] == [] for r in report["results"])
    assert all(
        b["model"] == "unchanged-model"
        and b["tool_choice"] == {"type": "function", "function": {"name": "submit_travel_intent"}}
        for b in sent
    )
    assert report["results"][0]["input"]["draft"]["main_origin"] == "广州"


def test_valid_parameters_with_wrong_role_are_not_counted_as_semantic_success():
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: result(
                {"intent": "conditions", "updates": {"main_origin": "苏州"}, "clear_fields": []}
            )
        )
    ) as client:
        report = probe(client)
    assert report["results"][1]["status"] == "ok"
    assert report["results"][1]["semantic_errors"]


@pytest.mark.parametrize("mode", ["unknown_function", "ignored", "multiple"])
def test_probe_rejects_unrequested_or_missing_function_calls(mode):
    def handle(request):
        if mode == "ignored":
            return httpx.Response(
                200, json={"choices": [{"message": {"content": "ordinary text"}}]}
            )
        response = result(
            {"intent": "conditions", "updates": {}, "clear_fields": []},
            name="unrequested_action" if mode == "unknown_function" else "submit_travel_intent",
        )
        if mode == "multiple":
            payload = response.json()
            payload["choices"][0]["message"]["tool_calls"] *= 2
            return httpx.Response(200, json=payload)
        return response

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        report = probe(client)
    assert all(row["status"] != "ok" for row in report["results"])


def test_capability_rejection_stops_without_retry_or_catalog_query():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(400, text='fake-"secret private upstream body')

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        report = probe(client)
    assert len(calls) == 1
    assert report["results"][0]["status"] == "http_error"
    assert "private upstream body" not in json.dumps(report)


def test_probe_redacts_generated_arguments_and_model_metadata(capsys):
    def handle(request):
        payload = result(
            {"intent": "conditions", "updates": {"main_origin": 'fake-"secret'}, "clear_fields": []}
        ).json()
        payload["model"] = 'fake-"secret'
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        report = probe(client)
    assert "fake-" not in json.dumps(report, ensure_ascii=False) + capsys.readouterr().out
