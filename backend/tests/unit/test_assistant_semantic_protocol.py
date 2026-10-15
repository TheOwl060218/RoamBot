from datetime import date

import pytest

from roambot.domain.assistant import (
    AssistantModelReply,
    AssistantTurnRequest,
    merge_assistant_patch,
)
from roambot.providers.assistant_semantic_protocol import (
    normalize_semantic_output,
    semantic_messages,
)
from roambot.services.assistant_interpretation import interpret_reply


def test_semantic_operations_preserve_independent_confirmed_state():
    request = AssistantTurnRequest(
        message="任意话语",
        revision=7,
        draft={
            "main_origin": "绍兴",
            "companion_origins": ["杭州"],
            "destination_regions": ["330200"],
            "max_distance_km": 120,
            "start_date": "2026-10-14",
            "end_date": "2026-10-16",
        },
    )
    reply = AssistantModelReply.model_validate(
        normalize_semantic_output(
            {
                "intent": "conditions",
                "edits": [
                    {"field": "同行出发地", "operation": "set", "value": ["南京"]},
                    {"field": "目的地省市", "operation": "set", "value": ["嘉兴"]},
                ],
            }
        )
    )
    resolved = interpret_reply(reply, request.draft, date(2026, 10, 13))
    merged = merge_assistant_patch(request.draft, resolved.patch, date(2026, 10, 13))
    assert merged.main_origin == "绍兴" and merged.max_distance_km == 120
    assert (
        merged.start_date == request.draft.start_date and merged.end_date == request.draft.end_date
    )
    assert merged.companion_origins == ["南京"] and merged.destination_regions == ["330400"]


def test_semantic_dates_compile_without_guessing_from_user_sentence():
    request = AssistantTurnRequest(
        message="完全不含日期的测试文字", revision=0, draft={"main_origin": "常州"}
    )
    reply = AssistantModelReply.model_validate(
        normalize_semantic_output(
            {
                "intent": "conditions",
                "edits": [
                    {
                        "field": "出游日期",
                        "operation": "set",
                        "value": {"offset_days": 1, "duration_days": 4},
                    },
                ],
            }
        )
    )
    resolved = interpret_reply(reply, request.draft, date(2026, 10, 13))
    assert resolved.patch.model_dump(mode="json", exclude_unset=True) == {
        "start_date": "2026-10-14",
        "end_date": "2026-10-17",
    }


@pytest.mark.parametrize(
    "edits",
    [
        [{"field": "出发地", "operation": "set", "value": None}],
        [{"field": "目的地省市", "operation": "clear", "value": ["苏州"]}],
        [{"field": "未知条件", "operation": "set", "value": "x"}],
        [
            {"field": "出发地", "operation": "set", "value": "甲"},
            {"field": "出发地", "operation": "clear"},
        ],
    ],
)
def test_semantic_labels_do_not_relax_edit_validation(edits):
    with pytest.raises(ValueError):
        AssistantModelReply.model_validate(
            normalize_semantic_output({"intent": "conditions", "edits": edits})
        )


def test_model_state_uses_region_names_and_real_history_roles():
    request = AssistantTurnRequest(
        message="后天",
        revision=0,
        draft={"destination_regions": ["320500"]},
        history=[
            {"role": "user", "content": "苏州"},
            {"role": "assistant", "content": "哪里出发？"},
        ],
    )
    messages = semantic_messages(request, None, date(2026, 10, 13))
    assert "苏州市" in messages[-2]["content"] and "320500" not in messages[-2]["content"]
    assert [item["role"] for item in messages] == ["system", "user", "assistant", "system", "user"]
    assert messages[-1]["content"] == "后天"
