import json
from datetime import UTC, date, datetime

import httpx
import pytest

from roambot.domain.assistant import AssistantTurnRequest
from roambot.providers.assistant import AssistantFormatError, OpenAICompatibleAssistantProvider
from roambot.providers.http import ProviderHttpClient
from roambot.providers.protocols import ProviderError
from roambot.security.assistant_context import AssistantContextSigner
from roambot.services.assistant import AssistantService


def service(client):
    provider = OpenAICompatibleAssistantProvider(
        ProviderHttpClient(client, provider="llm", base_url="https://fixture.invalid"),
        "fake-key",
        "unchanged-model",
        today=lambda: date(2026, 10, 13),
    )
    return AssistantService(
        provider,
        AssistantContextSigner(b"test", lambda: datetime.now(UTC)),
        today=lambda: date(2026, 10, 13),
        demo=False,
    )


def completion(content):
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
                                    "arguments": content,
                                },
                            }
                        ],
                    },
                }
            ]
        },
    )


def test_nullable_cancellation_needs_one_request_and_clears_all_preference_filters():
    calls = []

    def handle(request):
        calls.append(request)
        return completion(
            json.dumps(
                {
                    "intent": "conditions",
                    "updates": {"scenery_preference": None},
                }
            )
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = service(client).turn(
            AssistantTurnRequest(
                message="清除偏好",
                revision=3,
                draft={
                    "main_origin": "武汉",
                    "companion_origins": ["长沙"],
                    "start_date": "2026-10-14",
                    "end_date": "2026-10-16",
                    "max_distance_km": 160,
                    "destination_regions": ["420100"],
                    "scenery_types": ["park"],
                    "scenery_query": "开阔的绿地",
                    "scenery_keywords": ["公园"],
                },
            )
        )
    assert len(calls) == 1, "valid cancellation should not need a format-repair request"
    assert result.patch.model_dump(exclude_unset=True) == {
        "scenery_query": None,
        "scenery_types": None,
        "scenery_keywords": None,
    }
    assert result.revision == 3 and result.source == "live"


def test_nullable_region_cancellation_keeps_unrelated_explicit_distance_update():
    calls = []

    def handle(request):
        calls.append(request)
        return completion(
            json.dumps(
                {
                    "intent": "conditions",
                    "updates": {"destination_region_names": None, "max_distance_km": 70},
                }
            )
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = service(client).turn(
            AssistantTurnRequest(
                message="不限制目的地城市，距离七十公里",
                revision=0,
                draft={"main_origin": "南昌", "destination_regions": ["360100"]},
            )
        )
    assert len(calls) == 1
    assert result.patch.model_dump(exclude_unset=True) == {
        "destination_regions": [],
        "max_distance_km": 70,
    }


def test_format_retry_contains_failed_output_without_logging_it(caplog):
    invalid = '{"intent":"conditions","updates":{"duration_days":3},"PRIVATE_SENTINEL":true}'
    count = 0

    def handle(request):
        nonlocal count
        count += 1
        body = json.loads(request.content)
        if count == 1:
            return completion(invalid)
        has_feedback = any(
            m["role"] == "assistant" and m["content"] == invalid for m in body["messages"]
        )
        return completion(
            json.dumps(
                {
                    "intent": "conditions",
                    "updates": {"date_request": {"duration_days": 3 if has_feedback else 1}},
                }
            )
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        response = service(client).turn(
            AssistantTurnRequest(message="待三天", revision=0, draft={})
        )
    assert response.conversation_state.pending_date_request.duration_days == 3
    assert count == 2
    assert "PRIVATE_SENTINEL" not in caplog.text and "fake-key" not in caplog.text


def test_failed_repair_is_bounded_and_never_guesses_conditions(caplog):
    count = 0

    def handle(request):
        nonlocal count
        count += 1
        return completion('{"intent":"conditions","UNKNOWN_PRIVATE_FIELD":true}')

    with (
        httpx.Client(transport=httpx.MockTransport(handle)) as client,
        pytest.raises(ProviderError),
    ):
        service(client).turn(AssistantTurnRequest(message="不是从这里走", revision=0, draft={}))
    assert count == 2
    assert "UNKNOWN_PRIVATE_FIELD" not in caplog.text


def test_valid_reply_has_no_extra_repair_call():
    count = 0

    def handle(request):
        nonlocal count
        count += 1
        return completion('{"intent":"conditions","updates":{"main_origin":"合肥"}}')

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        response = service(client).turn(
            AssistantTurnRequest(message="合肥出发", revision=0, draft={})
        )
    assert response.patch.main_origin == "合肥"
    assert count == 1


@pytest.mark.parametrize(
    "query,shape,reason",
    [
        ("", "empty_string", "preference_length"),
        ("  ", "blank_string", "preference_length"),
        ("PRIVATE_QUERY|TEXT", "string", "preference_plain_text"),
        ("P" * 121, "string", "preference_length"),
    ],
)
def test_validation_feedback_reports_safe_shape_and_constraint_not_contents(
    query, shape, reason, caplog
):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: completion(
                json.dumps(
                    {
                        "intent": "conditions",
                        "updates": {
                            "scenery_preference": {
                                "categories": None,
                                "description": query,
                                "keywords": None,
                            }
                        },
                    }
                )
            )
        )
    ) as client:
        provider = OpenAICompatibleAssistantProvider(
            ProviderHttpClient(client, provider="llm", base_url="https://fixture.invalid"),
            "fake-key",
            "unchanged-model",
            today=lambda: date(2026, 10, 13),
        )
        with pytest.raises(AssistantFormatError) as failure:
            provider.turn(AssistantTurnRequest(message="修改偏好", revision=0, draft={}), None)
    feedback = json.loads(failure.value.problem)
    assert feedback[0]["value_shape"] == shape
    assert feedback[0]["constraint"] == reason
    assert "PRIVATE_QUERY" not in caplog.text
    assert "P" * 121 not in caplog.text


def test_keyword_feedback_uses_keyword_limit_not_the_query_limit():
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: completion(
                json.dumps(
                    {
                        "intent": "conditions",
                        "updates": {
                            "scenery_preference": {
                                "categories": None,
                                "description": None,
                                "keywords": ["K" * 25],
                            }
                        },
                    }
                )
            )
        )
    ) as client:
        provider = OpenAICompatibleAssistantProvider(
            ProviderHttpClient(client, provider="llm", base_url="https://fixture.invalid"),
            "fake-key",
            "unchanged-model",
            today=lambda: date(2026, 10, 13),
        )
        with pytest.raises(AssistantFormatError) as failure:
            provider.turn(AssistantTurnRequest(message="修改偏好", revision=0, draft={}), None)
    assert json.loads(failure.value.problem)[0]["text_limit"] == 24


@pytest.mark.parametrize(
    "arguments,reason",
    [
        ({"intent": "conditions", "question": None}, "null_parameter"),
        ({"intent": "conditions", "updates": []}, "updates_object_required"),
        (
            {"intent": "conditions", "updates": {"date_request": {"end_date": None}}},
            "null_date",
        ),
        ({"intent": "conversation", "updates": {"main_origin": "PRIVATE_PLACE"}}, "intent_edit"),
    ],
)
def test_root_parameter_failure_has_safe_specific_feedback(arguments, reason, caplog):
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: completion(json.dumps(arguments)))
    ) as client:
        provider = OpenAICompatibleAssistantProvider(
            ProviderHttpClient(client, provider="llm", base_url="https://fixture.invalid"),
            "fake-key",
            "unchanged-model",
            today=lambda: date(2026, 10, 13),
        )
        with pytest.raises(AssistantFormatError) as failure:
            provider.turn(AssistantTurnRequest(message="修改偏好", revision=0, draft={}), None)
    assert json.loads(failure.value.problem)[0]["constraint"] == reason
    assert "PRIVATE_PLACE" not in caplog.text and "fake-key" not in caplog.text
