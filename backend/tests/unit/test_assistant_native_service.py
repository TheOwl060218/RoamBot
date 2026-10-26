from datetime import UTC, date, datetime

import pytest

from roambot.domain.assistant import AssistantModelReply, AssistantPatch, AssistantTurnRequest
from roambot.providers.assistant_parameters import compile_assistant_parameters
from roambot.providers.protocols import ProviderError
from roambot.security.assistant_context import AssistantContextSigner
from roambot.services.assistant import AssistantService

TODAY = date(2026, 10, 13)


class ParameterProvider:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    def turn(self, request, facts):
        self.calls += 1
        return compile_assistant_parameters(self.value)


def service(provider):
    return AssistantService(
        provider,
        AssistantContextSigner(b"test", lambda: datetime.now(UTC)),
        lambda: TODAY,
        demo=False,
    )


def test_temporal_place_is_not_silently_rewritten():
    result = AssistantPatch(main_origin="明天", target_place="周末", companion_origins=["明天"])
    assert result.model_dump(exclude_unset=True) == {
        "main_origin": "明天",
        "target_place": "周末",
        "companion_origins": ["明天"],
    }
    with pytest.raises(ValueError):
        AssistantPatch(main_origin=" ")


def test_conversation_preserves_pending_and_does_not_force_filling_conditions():
    result = service(ParameterProvider({"intent": "conversation"})).turn(
        AssistantTurnRequest(
            message="谢谢",
            revision=0,
            draft={},
            conversation_state={"pending_date_request": {"duration_days": 3}},
        )
    )
    assert not result.patch.model_fields_set
    assert result.question is None
    assert result.conversation_state.pending_date_request.duration_days == 3


@pytest.mark.parametrize("wording", ["以后再聊", "明天再聊"])
def test_legacy_direct_date_error_is_not_accepted_by_user_wording(wording):
    class LegacyProvider:
        calls = 0

        def turn(self, request, facts):
            self.calls += 1
            return AssistantModelReply(
                intent="conditions",
                patch={
                    "start_date": "2026-11-02",
                    "end_date": "2026-11-03",
                },
            )

    provider = LegacyProvider()
    with pytest.raises(ProviderError):
        service(provider).turn(AssistantTurnRequest(message=wording, revision=0, draft={}))
    assert provider.calls == 2


@pytest.mark.parametrize("wording", ["换一下", "下月去"])
def test_native_invalid_date_is_explained_independent_of_user_wording(wording):
    provider = ParameterProvider(
        {
            "intent": "conditions",
            "updates": {
                "date_request": {"start_date": "2026-11-02", "duration_days": 2},
                "main_origin": "福州",
            },
        }
    )
    result = service(provider).turn(AssistantTurnRequest(message=wording, revision=0, draft={}))
    assert result.patch.model_dump(exclude_unset=True) == {"main_origin": "福州"}
    assert result.question and "2026-11-02" in result.question
    assert result.conversation_state.pending_date_request.duration_days == 2
    assert provider.calls == 1


def test_mixed_edit_keeps_model_clarification():
    result = service(
        ParameterProvider(
            {
                "intent": "conditions",
                "updates": {"max_distance_km": 80},
                "question": "这个城市是出发地还是目的地？",
            }
        )
    ).turn(AssistantTurnRequest(message="含糊的地点和明确的距离", revision=0, draft={}))
    assert result.patch.model_dump(exclude_unset=True) == {"max_distance_km": 80}
    assert result.question == "这个城市是出发地还是目的地？"


def test_clear_pending_dates_is_atomic_and_keeps_other_fields():
    result = service(
        ParameterProvider({"intent": "conditions", "updates": {"date_request": None}})
    ).turn(
        AssistantTurnRequest(
            message="取消日期",
            revision=0,
            draft={"main_origin": "泉州"},
            conversation_state={"pending_date_request": {"duration_days": 4}},
        )
    )
    assert result.patch.model_dump(exclude_unset=True) == {"start_date": None, "end_date": None}
    assert result.conversation_state.pending_date_request is None


def test_pure_unsupported_preserves_state_and_reports_boundary():
    result = service(ParameterProvider({"intent": "unsupported"})).turn(
        AssistantTurnRequest(
            message="未接入功能咨询",
            revision=0,
            draft={"main_origin": "杭州"},
            conversation_state={"pending_date_request": {"duration_days": 3}},
        )
    )
    assert not result.patch.model_fields_set and result.question is None
    assert result.unsupported_preferences
    assert result.conversation_state.pending_date_request.duration_days == 3


def test_unverified_answer_plan_does_not_edit_or_render_invented_facts():
    provider = ParameterProvider(
        {
            "intent": "answer",
            "answer_plan": {
                "candidate_ids": ["untrusted"],
                "topic": "weather",
            },
        }
    )
    with pytest.raises(ProviderError):
        service(provider).turn(AssistantTurnRequest(message="天气", revision=0, draft={}))
    assert provider.calls == 2
