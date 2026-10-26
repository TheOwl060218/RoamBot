"""Pending semantic fragments survive independently of truncated chat history."""

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from roambot.domain.assistant import (
    AssistantModelReply,
    AssistantTurnRequest,
    merge_assistant_patch,
)
from roambot.security.assistant_context import AssistantContextSigner
from roambot.services.assistant import AssistantService

TODAY = date(2026, 10, 13)


def run_turn(reply, draft=None, state=None):
    class Provider:
        def turn(self, request, facts):
            return AssistantModelReply.model_validate(reply)

    service = AssistantService(
        Provider(),
        AssistantContextSigner(b"test", lambda: datetime.now(UTC)),
        today=lambda: TODAY,
        demo=False,
    )
    values = {"message": "semantic fragment", "revision": 0, "draft": draft or {}}
    if state is not None:
        values["conversation_state"] = state
    return service.turn(AssistantTurnRequest.model_validate(values))


def test_duration_is_saved_without_guessing_an_anchor():
    response = run_turn({"intent": "conditions", "date_request": {"duration_days": 3}})
    assert response.patch.model_dump(exclude_unset=True) == {}
    state = getattr(response, "conversation_state", None)
    assert state is not None, "unconfirmed duration must be retained outside chat history"
    assert state.pending_date_request.duration_days == 3


def test_pending_duration_survives_unrelated_turns_and_no_history():
    first = run_turn({"intent": "conditions", "date_request": {"duration_days": 3}})
    state = getattr(first, "conversation_state", None)
    assert state is not None
    second = run_turn(
        {"intent": "conditions", "patch": {"main_origin": "合肥", "max_distance_km": 90}},
        state=state.model_dump(mode="json"),
    )
    draft = merge_assistant_patch(
        AssistantTurnRequest(message="x", revision=0, draft={}).draft, second.patch, TODAY
    )
    final = run_turn(
        {"intent": "conditions", "date_request": {"offset_days": 2}},
        draft=draft.model_dump(mode="json"),
        state=second.conversation_state.model_dump(mode="json"),
    )
    assert final.patch.start_date == date(2026, 10, 15)
    assert final.patch.end_date == date(2026, 10, 17)
    assert final.conversation_state.pending_date_request is None
    assert "main_origin" not in final.patch.model_fields_set


def test_new_duration_overrides_pending_duration():
    response = run_turn(
        {"intent": "conditions", "date_request": {"offset_days": 1, "duration_days": 1}},
        state={"pending_date_request": {"duration_days": 4}},
    )
    assert response.patch.start_date == response.patch.end_date == date(2026, 10, 14)
    assert response.conversation_state.pending_date_request is None


def test_end_before_start_is_retained_and_completed_later():
    first = run_turn({"intent": "conditions", "date_request": {"end_date": "2026-10-17"}})
    state = getattr(first, "conversation_state", None)
    assert state is not None
    final = run_turn(
        {"intent": "conditions", "date_request": {"offset_days": 2}},
        state=state.model_dump(mode="json"),
    )
    assert final.patch.start_date == date(2026, 10, 15)
    assert final.patch.end_date == date(2026, 10, 17)


def test_explicit_date_clear_discards_pending_fragment():
    response = run_turn(
        {"intent": "conditions", "patch": {"start_date": None, "end_date": None}},
        state={"pending_date_request": {"duration_days": 3}},
    )
    assert response.conversation_state.pending_date_request is None


def test_invalid_window_retains_intent_without_committing_invalid_dates():
    first = run_turn(
        {"intent": "conditions", "date_request": {"offset_days": 3, "duration_days": 5}}
    )
    state = getattr(first, "conversation_state", None)
    assert state is not None
    assert "start_date" not in first.patch.model_fields_set
    final = run_turn(
        {"intent": "conditions", "date_request": {"duration_days": 2}},
        state=state.model_dump(mode="json"),
    )
    assert final.patch.start_date == date(2026, 10, 16)
    assert final.patch.end_date == date(2026, 10, 17)


@pytest.mark.parametrize("duration", [0, 32, "3", True])
def test_client_pending_fragment_is_bounded_and_strict(duration):
    with pytest.raises(ValidationError):
        AssistantTurnRequest.model_validate(
            {
                "message": "x",
                "revision": 0,
                "draft": {},
                "conversation_state": {"pending_date_request": {"duration_days": duration}},
            }
        )


def test_model_cannot_write_conversation_state_directly():
    with pytest.raises(ValidationError):
        AssistantModelReply.model_validate(
            {
                "intent": "conditions",
                "conversation_state": {"pending_date_request": {"duration_days": 3}},
            }
        )


def test_empty_memory_marker_survives_sparse_http_serialization():
    response = run_turn({"intent": "conditions", "patch": {"main_origin": "合肥"}})
    # The assistant route excludes unset fields to keep its patch sparse.
    assert response.model_dump(exclude_unset=True)["conversation_state"] == {
        "pending_date_request": None
    }
