from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from roambot.domain.assistant import (
    AssistantDraft,
    AssistantModelReply,
    AssistantPatch,
    AssistantTurnRequest,
    merge_assistant_patch,
    required_question,
)

TODAY = date(2026, 10, 10)


def test_freeform_scenery_contract_normalizes_and_limits_keywords():
    draft = AssistantDraft(
        scenery_query=" 安静的水边 ", scenery_keywords=["湖泊", " 湖泊 ", "湿地"]
    )
    assert draft.scenery_query == "安静的水边"
    assert draft.scenery_keywords == ["湖泊", "湿地"]
    for keywords in (["https://example.com"], ["湖\n泊"], ["x" * 25], ["a", "b", "c", "d", "e"]):
        with pytest.raises(ValidationError):
            AssistantPatch(scenery_keywords=keywords)


def test_freeform_region_query_does_not_require_six_type_selection():
    draft = AssistantDraft(
        main_origin="苏州站", start_date=TODAY, end_date=TODAY, destination_regions=["310000"]
    )
    assert required_question(draft, TODAY) is None


def test_fallback_extracts_combined_input_without_positive_exclusion():
    from roambot.domain.semantic_preferences import parse_fallback_conditions

    patch = parse_fallback_conditions(
        "苏州站出发，这周末想找安静的水边，100公里内，不要商业街", TODAY
    )
    assert patch.main_origin == "苏州站"
    assert patch.start_date == TODAY
    assert patch.end_date == TODAY + timedelta(days=1)
    assert patch.max_distance_km == 100
    assert patch.scenery_types
    assert "商业街" not in patch.scenery_keywords
    assert "安静" in patch.scenery_query


def test_partial_draft_and_atomic_patch():
    draft = AssistantDraft(main_origin=" 苏州站 ", companion_origins=["上海站"])
    assert draft.main_origin == "苏州站"
    merged = merge_assistant_patch(draft, AssistantPatch(main_origin=None), TODAY)
    assert merged.main_origin is None
    assert merged.companion_origins == ["上海站"]
    assert required_question(merged, TODAY) == "从哪里出发？"
    with pytest.raises(ValueError):
        merge_assistant_patch(draft, AssistantPatch(start_date=TODAY), TODAY)
    with pytest.raises(ValidationError):
        AssistantDraft(companion_origins=["a", "b", "c"])


@pytest.mark.parametrize(
    "payload",
    [
        {"coordinate": {"latitude": 31, "longitude": 120}},
        {"tools": []},
        {"scenery_types": ["shopping"]},
        {"main_origin": " "},
        {"weights": {"weather": 30, "distance": 30, "fairness": 0, "popularity": 30}},
    ],
)
def test_reject_unknown_and_coordinates(payload):
    with pytest.raises(ValidationError):
        AssistantPatch(**payload)


def test_limits_and_china_midnight():
    history = [{"role": "user", "content": "x" * 1000}] * 6
    request = AssistantTurnRequest(message="x" * 2000, revision=0, draft={}, history=history)
    assert request.revision == 0
    assert len(request.history) == 6
    for update in ({"message": "x" * 2001}, {"history": history + history[:1]}, {"revision": -1}):
        with pytest.raises(ValidationError):
            AssistantTurnRequest(**(request.model_dump() | update))
    good = merge_assistant_patch(
        AssistantDraft(),
        AssistantPatch(start_date=TODAY, end_date=TODAY + timedelta(days=6)),
        TODAY,
    )
    assert good.end_date == date(2026, 10, 16)
    with pytest.raises(ValueError):
        merge_assistant_patch(good, AssistantPatch(), TODAY + timedelta(days=1))
    with pytest.raises(ValueError):
        merge_assistant_patch(
            AssistantDraft(),
            AssistantPatch(start_date=TODAY, end_date=TODAY + timedelta(days=7)),
            TODAY,
        )
    assert required_question(AssistantDraft(), TODAY) == "从哪里出发？"


def test_weight_fairness_depends_on_companions_and_answer_is_structured():
    patch = AssistantPatch(weights={"weather": 40, "distance": 30, "fairness": 0, "popularity": 30})
    with pytest.raises(ValueError):
        merge_assistant_patch(AssistantDraft(companion_origins=["上海站"]), patch, TODAY)
    with pytest.raises(ValidationError):
        AssistantModelReply(
            intent="answer", answer_plan={"candidate_ids": ["a"], "topic": "invented"}
        )
    with pytest.raises(ValidationError):
        AssistantModelReply(intent="conditions", tool_calls=[])


def test_companion_change_rebalances_existing_weights_but_explicit_invalid_fairness_rejected():
    draft = AssistantDraft(weights={"weather": 40, "distance": 30, "fairness": 0, "popularity": 30})
    merged = merge_assistant_patch(draft, AssistantPatch(companion_origins=["上海站"]), TODAY)
    assert merged.weights.fairness == 20
    assert sum(merged.weights.model_dump().values()) == 100
    with pytest.raises(ValueError):
        patch = AssistantPatch(companion_origins=["上海站"], weights=draft.weights)
        merge_assistant_patch(draft, patch, TODAY)
