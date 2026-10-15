import json
from datetime import date

import httpx
import pytest

from roambot.config import Settings
from roambot.domain.assistant import AssistantTurnRequest
from roambot.providers.assistant import OpenAICompatibleAssistantProvider, normalize_model_output
from roambot.providers.http import ProviderHttpClient
from roambot.providers.protocols import ProviderError


def native_completion(value):
    raw = value if isinstance(value, str) else json.dumps(value)
    return httpx.Response(
        200,
        json={
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
                                    "arguments": raw,
                                },
                            }
                        ],
                    },
                }
            ]
        },
    )


@pytest.mark.parametrize(
    "content",
    [
        {"patch": {"duration_days": 2}, "date_request": {"duration_days": 4}},
        {"patch": {"destination_regions": ["杭州"]}, "destination_region_names": ["上海"]},
    ],
)
def test_conflicting_protocol_representations_are_rejected(content):
    with pytest.raises(ValueError):
        normalize_model_output(content)


def test_normalization_preserves_unknown_fields_for_strict_validation_and_does_not_mutate():
    content = {"intent": "conditions", "patch": {"duration_days": 2, "unrecognized": "x"}}
    normalized = normalize_model_output(content)
    assert content["patch"]["duration_days"] == 2
    assert normalized["patch"] == {"unrecognized": "x"}
    assert normalized["date_request"] == {"duration_days": 2}


def test_semantic_region_names_in_patch_are_relocated():
    value = {
        "intent": "conditions",
        "patch": {"main_origin": "无锡", "destination_region_names": ["苏州"]},
    }
    normalized = normalize_model_output(value)
    assert normalized["patch"] == {"main_origin": "无锡"}
    assert normalized["destination_region_names"] == ["苏州"]


@pytest.mark.parametrize(
    "content,expected",
    [
        ({"intent": "conditions", "patch": {"duration_days": 1}}, {"duration_days": 1}),
        (
            {"intent": "conditions", "patch": {"offset_days": 2, "duration_days": 2}},
            {"offset_days": 2, "duration_days": 2},
        ),
    ],
)
def test_native_temporal_values_are_transferred_not_discarded(content, expected):
    def handle(request):
        return native_completion({"intent": "conditions", "updates": {"date_request": expected}})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        provider = OpenAICompatibleAssistantProvider(
            ProviderHttpClient(client, provider="llm", base_url="https://fixture.invalid"),
            "fake-key",
            "fixture-model",
            today=lambda: date(2026, 10, 12),
        )
        reply = provider.turn(
            AssistantTurnRequest(message="改变出行时长", revision=0, draft={}), None
        )
    assert reply.date_request.model_dump(exclude_unset=True) == expected
    assert not reply.patch.model_fields_set


def test_native_region_names_are_transferred_to_semantic_names():
    def handle(request):
        return native_completion(
            {"intent": "conditions", "updates": {"destination_region_names": ["上海", "杭州"]}}
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        provider = OpenAICompatibleAssistantProvider(
            ProviderHttpClient(client, provider="llm", base_url="https://fixture.invalid"),
            "fake-key",
            "fixture-model",
            today=lambda: date(2026, 10, 12),
        )
        reply = provider.turn(
            AssistantTurnRequest(message="改变目的地", revision=0, draft={}), None
        )
    assert reply.destination_region_names == ["上海", "杭州"]
    assert "destination_regions" not in reply.patch.model_fields_set


def test_history_uses_chat_roles_and_current_utterance_not_nested_transcript():
    sent = []

    def handle(request):
        sent.append(json.loads(request.content))
        return native_completion(
            {
                "intent": "conditions",
                "updates": {"date_request": {"offset_days": 1, "duration_days": 4}},
            }
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        provider = OpenAICompatibleAssistantProvider(
            ProviderHttpClient(client, provider="llm", base_url="https://fixture.invalid"),
            "fake-key",
            "fixture-model",
            today=lambda: date(2026, 10, 12),
        )
        reply = provider.turn(
            AssistantTurnRequest(
                message="明天动身，待四天",
                revision=0,
                draft={"main_origin": "苏州"},
                history=[
                    {"role": "user", "content": "苏州"},
                    {"role": "assistant", "content": "是出发地还是目的地？"},
                    {"role": "user", "content": "出发地"},
                ],
            ),
            None,
        )
    assert reply.date_request.duration_days == 4
    assert sent[0]["messages"][-1] == {"role": "user", "content": "明天动身，待四天"}
    assert any(
        message == {"role": "assistant", "content": "是出发地还是目的地？"}
        for message in sent[0]["messages"]
    )


@pytest.mark.parametrize("model", ["fixture-flash", "fixture-strong"])
def test_model_is_configuration_not_literal(model):
    sent = []

    def handle(request):
        sent.append(request)
        return native_completion({"intent": "conditions", "updates": {"main_origin": "苏州站"}})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        provider = OpenAICompatibleAssistantProvider(
            ProviderHttpClient(
                client, provider="llm", base_url="https://fixture.invalid/v1", timeout=15
            ),
            "fixture-key",
            model,
            today=lambda: date(2026, 10, 10),
        )
        reply = provider.turn(
            AssistantTurnRequest(message="从苏州站出发", revision=0, draft={}), None
        )
    assert reply.patch.main_origin == "苏州站"
    assert len(sent) == 1
    body = json.loads(sent[0].content)
    assert body["model"] == model
    assert "response_format" not in body
    assert body["tool_choice"]["function"]["name"] == "submit_travel_intent"
    assert body["temperature"] == 0.2
    assert body["max_tokens"] == 2048
    assert "2026-10-10" in body["messages"][0]["content"]
    assert sent[0].extensions["timeout"]["read"] == 15
    assert Settings().provider_timeout_seconds == 5
    assert Settings().assistant_timeout_seconds == 7


@pytest.mark.parametrize(
    "content",
    [
        "",
        "{",
        '{"intent":"conditions","tools":[]}',
        '{"intent":"conditions","patch":{"city":"苏州"}}',
    ],
)
def test_invalid_or_empty_model_output_is_safe(content):
    calls = []

    def handle(request):
        calls.append(request)
        return native_completion(content)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        provider = OpenAICompatibleAssistantProvider(
            ProviderHttpClient(client, provider="llm", base_url="https://fixture.invalid"),
            "fixture-key",
            "fixture-model",
            today=lambda: date(2026, 10, 10),
        )
        with pytest.raises(ProviderError, match="invalid assistant response"):
            provider.turn(AssistantTurnRequest(message="hello", revision=0, draft={}), None)
    assert len(calls) == 1


@pytest.mark.parametrize("failure", ["rate", "timeout", "tools", "truncated"])
def test_one_call_failure_never_retries_or_leaks(failure):
    calls = []

    def handle(request):
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("private-content", request=request)
        if failure == "rate":
            return httpx.Response(429, text="private-content")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "length" if failure == "truncated" else "stop",
                        "message": {
                            "content": '{"intent":"conditions"}',
                            "tool_calls": [{}] if failure == "tools" else [],
                        },
                    }
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        provider = OpenAICompatibleAssistantProvider(
            ProviderHttpClient(client, provider="llm", base_url="https://fixture.invalid"),
            "fixture-key",
            "fixture-model",
            today=lambda: date(2026, 10, 10),
        )
        with pytest.raises(ProviderError) as exc:
            provider.turn(
                AssistantTurnRequest(message="private-message", revision=0, draft={}), None
            )
    assert "private" not in str(exc.value)
    assert len(calls) == 1
