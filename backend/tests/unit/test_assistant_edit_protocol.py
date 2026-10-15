"""Protocol invariants, independent of particular natural-language sentences."""

import pytest

from roambot.domain.assistant import AssistantModelReply
from roambot.providers.assistant import normalize_model_output


def reply(value):
    return AssistantModelReply.model_validate(normalize_model_output(value))


def test_unresolved_region_does_not_write_region_but_confirmed_distance_survives():
    result = reply(
        {
            "intent": "conditions",
            "edits": [
                {"field": "max_distance_km", "operation": "set", "value": 80},
                {"field": "destination_region_names", "operation": "unresolved"},
            ],
            "question": "这个城市是出发地还是目的地？",
        }
    )
    assert result.patch.model_dump(exclude_unset=True) == {"max_distance_km": 80}
    assert "destination_region_names" not in result.model_fields_set
    assert result.question


def test_date_clear_is_explicit_and_atomic():
    result = reply(
        {"intent": "conditions", "edits": [{"field": "date_request", "operation": "clear"}]}
    )
    assert result.patch.model_dump(exclude_unset=True) == {"start_date": None, "end_date": None}


def test_conversation_is_not_an_edit():
    result = reply({"intent": "conversation", "edits": []})
    assert not result.patch.model_fields_set
    with pytest.raises(ValueError):
        reply(
            {"intent": "conversation", "edits": [{"field": "date_request", "operation": "clear"}]}
        )


@pytest.mark.parametrize(
    "edits",
    [
        [{"field": "main_origin", "operation": "set", "value": None}],
        [{"field": "main_origin", "operation": "clear", "value": "甲地"}],
        [{"field": "destination_region_names", "operation": "unresolved", "value": ["甲市"]}],
        [
            {"field": "main_origin", "operation": "set", "value": "甲地"},
            {"field": "main_origin", "operation": "clear"},
        ],
        [{"field": "start_date", "operation": "clear"}],
    ],
)
def test_ambiguous_or_conflicting_edit_operations_are_rejected(edits):
    with pytest.raises(ValueError):
        reply({"intent": "conditions", "edits": edits, "question": "请确认"})


def test_explicit_end_date_is_transferred_without_arithmetic():
    result = reply(
        {
            "intent": "conditions",
            "edits": [
                {
                    "field": "date_request",
                    "operation": "set",
                    "value": {"start_date": "2026-10-15", "end_date": "2026-10-17"},
                }
            ],
        }
    )
    assert result.date_request.start_date.isoformat() == "2026-10-15"
    assert result.date_request.end_date.isoformat() == "2026-10-17"
