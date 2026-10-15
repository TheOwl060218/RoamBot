from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from roambot.domain.assistant import AssistantModelReply, AssistantTurnRequest
from roambot.providers.protocols import ProviderError
from roambot.security.assistant_context import AssistantContextSigner
from roambot.services.assistant import AssistantService

TODAY = date(2026, 10, 12)
COMPLETE = {
    "main_origin": "苏州",
    "start_date": "2026-10-13",
    "end_date": "2026-10-16",
    "scenery_types": ["lake"],
    "max_distance_km": 100,
}


def turn(reply, message, draft=None):
    class Provider:
        def turn(self, request, facts):
            return AssistantModelReply.model_validate(reply)

    service = AssistantService(
        Provider(),
        AssistantContextSigner(b"test", lambda: datetime.now(UTC)),
        today=lambda: TODAY,
        demo=False,
    )
    return service.turn(
        AssistantTurnRequest(
            message=message, revision=0, draft=draft if draft is not None else COMPLETE
        )
    )


def test_unrelated_patch_does_not_erase_pending_clarification():
    response = turn(
        {
            "intent": "conditions",
            "patch": {"max_distance_km": 80},
            "question": "南京是另一位同行的出发地，还是目的地？",
        },
        "80公里内，南京也考虑一下",
    )
    assert response.patch.max_distance_km == 80
    assert response.question == "南京是另一位同行的出发地，还是目的地？"


def test_successful_reply_is_not_augmented_by_raw_phrase_regex():
    response = turn(
        {"intent": "conditions", "patch": {}, "question": "是否要改变原来的出行日期？"},
        "不是明天出发玩四天，是后天出发玩两天",
    )
    assert not response.patch.model_fields_set
    assert response.question


@pytest.mark.parametrize(
    "message,date_request,start,end",
    [
        ("明天动身，待上四天", {"offset_days": 1, "duration_days": 4}, "2026-10-13", "2026-10-16"),
        (
            "不是明天，是后天，住两天",
            {"offset_days": 2, "duration_days": 2},
            "2026-10-14",
            "2026-10-15",
        ),
        ("不玩四天了，只留一天", {"duration_days": 1}, "2026-10-13", "2026-10-13"),
        ("出发日往后挪一天，其他不变", {"start_date": "2026-10-14"}, "2026-10-14", "2026-10-17"),
        ("16号回来", {"end_date": "2026-10-16"}, "2026-10-13", "2026-10-16"),
    ],
)
def test_semantic_date_intent_is_calculated_without_reading_wording(
    message, date_request, start, end
):
    response = turn({"intent": "conditions", "date_request": date_request}, message)
    assert response.patch.start_date.isoformat() == start
    assert response.patch.end_date.isoformat() == end
    assert "main_origin" not in response.patch.model_fields_set


def test_invalid_date_keeps_other_patch_and_specific_question():
    response = turn(
        {
            "intent": "conditions",
            "patch": {"max_distance_km": 80},
            "date_request": {"offset_days": 3, "duration_days": 5},
        },
        "80公里，大后天起玩五天",
    )
    assert response.patch.max_distance_km == 80
    assert "start_date" not in response.patch.model_fields_set
    assert "2026-10-18" in response.question


def test_duration_without_start_asks_instead_of_guessing_today():
    response = turn(
        {"intent": "conditions", "date_request": {"duration_days": 2}},
        "住两天",
        {"main_origin": "苏州"},
    )
    assert "start_date" not in response.patch.model_fields_set
    assert response.question


def test_unsupported_intent_is_a_valid_conversation_not_an_answer_failure():
    response = turn(
        {"intent": "unsupported", "unsupported_preferences": ["实时人流"]}, "能看实时人流吗"
    )
    assert response.source == "live"
    assert response.unsupported_preferences == ["实时人流"]
    assert not response.patch.model_fields_set


def test_capability_intent_without_a_label_still_reports_the_boundary():
    response = turn({"intent": "unsupported"}, "这是能力咨询")
    assert response.unsupported_preferences
    assert "尚未接入" in response.reply
    assert not response.patch.model_fields_set


def test_pure_capability_reply_cannot_edit_saved_conditions():
    with pytest.raises(ValidationError):
        AssistantModelReply.model_validate(
            {"intent": "unsupported", "patch": {"main_origin": None}}
        )


def test_region_names_resolve_locally_without_requiring_model_adcodes():
    response = turn(
        {"intent": "conditions", "destination_region_names": ["上海", "杭州"]}, "上海杭州都可以"
    )
    assert response.patch.destination_regions == ["310000", "330100"]


def test_unknown_region_preserves_other_valid_changes_and_asks():
    response = turn(
        {
            "intent": "conditions",
            "patch": {"max_distance_km": 80},
            "destination_region_names": ["未知的地方"],
        },
        "80公里，去未知的地方",
    )
    assert response.patch.max_distance_km == 80
    assert "destination_regions" not in response.patch.model_fields_set
    assert response.question


def test_free_preference_is_not_rejected_for_missing_six_category_mapping():
    draft = {**COMPLETE, "scenery_types": []}
    response = turn(
        {
            "intent": "conditions",
            "patch": {"scenery_query": "适合发呆的小众地方", "scenery_keywords": ["观景"]},
        },
        "找个能放空的地方",
        draft,
    )
    assert response.patch.scenery_query == "适合发呆的小众地方"
    assert response.question is None


def test_repeated_semantic_failure_does_not_guess_from_negated_text():
    class Provider:
        def turn(self, request, facts):
            raise ProviderError("bad_response", "invalid response")

    service = AssistantService(
        Provider(),
        AssistantContextSigner(b"test", lambda: datetime.now(UTC)),
        today=lambda: TODAY,
        demo=False,
    )
    with pytest.raises(ProviderError):
        service.turn(
            AssistantTurnRequest(
                message="不是明天出发，是后天，玩两天",
                revision=0,
                draft=COMPLETE,
            )
        )


def test_expired_saved_dates_do_not_block_independent_condition_edit():
    response = turn(
        {"intent": "conditions", "patch": {"max_distance_km": 80}},
        "最多80公里",
        {**COMPLETE, "start_date": "2026-10-10", "end_date": "2026-10-11"},
    )
    assert response.patch.model_dump(exclude_unset=True) == {"max_distance_km": 80}
    assert response.question


def test_invalid_new_date_with_stale_saved_dates_keeps_independent_edits():
    response = turn(
        {
            "intent": "conditions",
            "patch": {"max_distance_km": 80},
            "date_request": {"offset_days": 20},
        },
        "20天后出发，最多80公里",
        {**COMPLETE, "start_date": "2026-10-10", "end_date": "2026-10-11"},
    )
    assert response.patch.model_dump(exclude_unset=True) == {"max_distance_km": 80}
    assert "2026-11-01" in response.question
