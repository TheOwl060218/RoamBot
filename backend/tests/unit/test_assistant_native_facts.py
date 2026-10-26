"""Native parameters must preserve the real signed-facts boundary."""

import json
from datetime import UTC, datetime, timedelta, timezone

import httpx
import pytest

from roambot.domain.assistant import AssistantTurnRequest
from roambot.domain.models import RecommendationRequest
from roambot.providers.assistant import OpenAICompatibleAssistantProvider
from roambot.providers.http import ProviderHttpClient
from roambot.providers.mock import MockProviderBundle
from roambot.providers.protocols import ProviderError
from roambot.security.assistant_context import AssistantContextSigner
from roambot.services.assistant import AssistantService
from roambot.services.recommendations import RecommendationService

TODAY = datetime.now(timezone(timedelta(hours=8))).date()


def signed_recommendation():
    bundle = MockProviderBundle.default()
    recommendation = RecommendationService(
        bundle.geocoder,
        bundle.places,
        bundle.distance,
        bundle.weather,
        bundle.explanations,
        "demo",
        lambda: datetime.now(UTC),
    ).recommend(
        RecommendationRequest(
            city="苏州",
            main_origin="苏州站",
            max_distance_km=100,
            start_date=TODAY,
            end_date=TODAY,
            scenery_types=["lake", "old_town", "park"],
        )
    )
    signer = AssistantContextSigner(b"synthetic-signing-key", lambda: datetime.now(UTC))
    return signer, signer.issue(recommendation)


@pytest.mark.parametrize("topic", ["weather", "journey", "rating", "fairness", "overview"])
def test_native_answer_uses_signed_data_not_response_free_text(topic):
    signer, context = signed_recommendation()
    candidates = signer.verify(context).candidates
    chosen = next(item for item in candidates if item.destination.rating == 4.8)

    def handle(request):
        messages = json.loads(request.content)["messages"]
        facts = json.loads(messages[-2]["content"])
        assert facts["focused_destination_id"] == chosen.candidate_id
        assert facts["facts"]["candidates"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": "PRIVATE_INVENTED_FACT",
                            "tool_calls": [
                                {
                                    "type": "function",
                                    "function": {
                                        "name": "submit_travel_intent",
                                        "arguments": json.dumps(
                                            {
                                                "intent": "answer",
                                                "answer_plan": {
                                                    "candidate_ids": [chosen.candidate_id],
                                                    "topic": topic,
                                                },
                                            }
                                        ),
                                    },
                                }
                            ],
                        },
                    }
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        adapter = OpenAICompatibleAssistantProvider(
            ProviderHttpClient(client, provider="llm", base_url="https://fixture.invalid"),
            "fake-key",
            "unchanged-model",
            lambda: TODAY,
        )
        result = AssistantService(adapter, signer, lambda: TODAY, demo=False).turn(
            AssistantTurnRequest(
                message="解读这个景点",
                revision=0,
                draft={},
                assistant_context=context,
                focused_destination_id=chosen.candidate_id,
            )
        )
    assert chosen.destination.name in result.reply
    assert "PRIVATE_INVENTED_FACT" not in result.reply
    assert not result.patch.model_fields_set
    if topic == "rating":
        assert "4.8/5" in result.reply
    if topic == "journey":
        assert "主出发地" in result.reply and "苏州站" not in result.reply


def test_native_answer_to_other_known_candidate_still_rejects_focus_violation():
    signer, context = signed_recommendation()
    candidates = signer.verify(context).candidates
    chosen, other = candidates[:2]
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "type": "function",
                                    "function": {
                                        "name": "submit_travel_intent",
                                        "arguments": json.dumps(
                                            {
                                                "intent": "answer",
                                                "answer_plan": {
                                                    "candidate_ids": [other.candidate_id],
                                                    "topic": "rating",
                                                },
                                            }
                                        ),
                                    },
                                }
                            ]
                        }
                    }
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        adapter = OpenAICompatibleAssistantProvider(
            ProviderHttpClient(client, provider="llm", base_url="https://fixture.invalid"),
            "fake-key",
            "unchanged-model",
            lambda: TODAY,
        )
        with pytest.raises(ProviderError):
            AssistantService(adapter, signer, lambda: TODAY, demo=False).turn(
                AssistantTurnRequest(
                    message="解读",
                    revision=0,
                    draft={},
                    assistant_context=context,
                    focused_destination_id=chosen.candidate_id,
                )
            )
    assert len(calls) == 2
