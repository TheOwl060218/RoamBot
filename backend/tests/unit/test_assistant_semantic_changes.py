from datetime import date

import pytest

from roambot.domain.assistant import AssistantDraft, AssistantModelReply
from roambot.providers.assistant_semantic_protocol import normalize_semantic_output
from roambot.services.assistant_interpretation import interpret_reply


def result(value):
    return AssistantModelReply.model_validate(normalize_semantic_output(value))


def test_changed_fields_and_deleted_fields_are_independent_and_atomic():
    reply = result(
        {
            "意图": "修改条件",
            "更新": {"同行出发地": ["南京"], "目的地省市": ["嘉兴"]},
            "删除": ["出游日期"],
        }
    )
    assert reply.patch.model_dump(exclude_unset=True) == {
        "companion_origins": ["南京"],
        "start_date": None,
        "end_date": None,
    }
    assert reply.destination_region_names == ["嘉兴"]


def test_bare_place_clarification_does_not_become_confirmed_city():
    reply = result(
        {"意图": "修改条件", "更新": {"距离上限": 80}, "追问": "这个地方是出发地还是目的地？"}
    )
    assert reply.patch.model_dump(exclude_unset=True) == {"max_distance_km": 80}
    assert reply.question


def test_explicit_update_collection_has_condition_intent_even_without_redundant_label():
    from roambot.providers.assistant import normalize_model_output

    reply = AssistantModelReply.model_validate(
        normalize_model_output(
            {
                "理解": "用户希望前往该市游玩",
                "更新": {"目的地省市": ["苏州"]},
            }
        )
    )
    assert reply.intent == "conditions"
    assert reply.destination_region_names == ["苏州"]
    assert not reply.patch.model_fields_set


def test_missing_intent_does_not_accept_arbitrary_unknown_fields():
    from roambot.providers.assistant import normalize_model_output

    with pytest.raises(ValueError):
        AssistantModelReply.model_validate(
            normalize_model_output(
                {
                    "更新": {"出发地": "苏州"},
                    "execute": "arbitrary",
                }
            )
        )


def test_relative_day_semantics_compute_duration_without_raw_sentence():
    reply = result(
        {
            "意图": "修改条件",
            "更新": {"出游日期": {"相对日期": "大后天", "游玩天数": 5}, "距离上限": 80},
        }
    )
    resolved = interpret_reply(reply, AssistantDraft(), date(2026, 10, 13))
    assert resolved.patch.model_dump(exclude_unset=True) == {"max_distance_km": 80}
    assert "2026-10-16至2026-10-20" in resolved.question


def test_chinese_explicit_return_date_is_retained_as_calendar_end():
    reply = result(
        {
            "意图": "修改条件",
            "更新": {"出游日期": {"出发日期": "2026-10-15", "返程日期": "2026-10-17"}},
        }
    )
    resolved = interpret_reply(reply, AssistantDraft(), date(2026, 10, 13))
    assert resolved.patch.model_dump(mode="json", exclude_unset=True) == {
        "start_date": "2026-10-15",
        "end_date": "2026-10-17",
    }


def test_conversation_cannot_silently_modify_state():
    assert not result({"意图": "聊天", "更新": {}, "删除": []}).patch.model_fields_set
    with pytest.raises(ValueError):
        result({"意图": "聊天", "更新": {"出发地": "南京"}})


@pytest.mark.parametrize(
    "value",
    [
        {"意图": "修改条件", "更新": {"出发地": None}},
        {"意图": "修改条件", "更新": {"任意字段": "x"}},
        {"意图": "修改条件", "更新": {"出游日期": {"相对日期": "未知时间"}}},
        {"意图": "修改条件", "更新": {"出游日期": {"相对日期": "后天", "出发日期": "2026-10-14"}}},
        {"意图": "修改条件", "更新": {"出游日期": {"游玩天数": True}}},
    ],
)
def test_semantic_change_contract_rejects_conflicts_unknowns_and_invalid_values(value):
    with pytest.raises(ValueError):
        result(value)


def test_known_english_date_contract_inside_chinese_updates_is_not_lost():
    reply = result(
        {
            "意图": "conditions",
            "更新": {
                "出游日期": {"offset_days": 1, "duration_days": 4},
            },
            "追问": [],
        }
    )
    assert reply.date_request.offset_days == 1 and reply.date_request.duration_days == 4
    assert reply.question is None


def test_one_question_array_preserves_clarification_while_many_questions_reject():
    reply = result({"更新": {}, "追问": ["这个地方是出发地还是目的地？"]})
    assert reply.question == "这个地方是出发地还是目的地？"
    with pytest.raises(ValueError):
        result({"更新": {}, "追问": ["问题一", "问题二"]})


def test_consistent_protocol_envelope_does_not_discard_valid_edit():
    reply = result(
        {
            "理解": "确认出发地",
            "更新": {"出发地": "无锡"},
            "删除": [],
            "追问": "",
            "协议": {
                "意图": "修改条件",
                "理解": "确认出发地",
                "更新": {"出发地": "无锡"},
                "删除": [],
                "追问": "",
            },
        }
    )
    assert reply.patch.model_dump(exclude_unset=True) == {"main_origin": "无锡"}
    assert reply.question is None


def test_conflicting_protocol_envelope_cannot_choose_an_edit_silently():
    with pytest.raises(ValueError):
        result({"更新": {"出发地": "无锡"}, "协议": {"更新": {"出发地": "南京"}}})
    with pytest.raises(ValueError):
        result({"协议": {"更新": {"出发地": "无锡"}, "execute": "arbitrary"}})


def test_capability_only_reply_does_not_require_empty_update_metadata():
    from roambot.providers.assistant import normalize_model_output

    reply = AssistantModelReply.model_validate(
        normalize_model_output(
            {
                "理解": "未接入人流数据",
                "无法筛选": ["实时人流"],
            }
        )
    )
    assert reply.intent == "unsupported" and reply.unsupported_preferences == ["实时人流"]
    assert not reply.patch.model_fields_set


def test_clarification_only_reply_preserves_question_without_making_edits():
    from roambot.providers.assistant import normalize_model_output

    reply = AssistantModelReply.model_validate(
        normalize_model_output(
            {
                "追问": "这个地点是哪一种出发或目的地角色？",
            }
        )
    )
    assert reply.question and not reply.patch.model_fields_set


def test_replacement_new_value_takes_precedence_over_removing_old_value():
    reply = result({"更新": {"风景类别": ["lake"], "风景描述": "水边"}, "删除": ["风景类别"]})
    assert reply.patch.model_dump(exclude_unset=True) == {
        "scenery_types": ["lake"],
        "scenery_query": "水边",
    }


def test_known_date_part_in_update_collection_is_moved_into_temporal_object():
    reply = result({"更新": {"出游日期": {"出发日期": "2026-10-15"}, "游玩天数": 2}})
    resolved = interpret_reply(reply, AssistantDraft(), date(2026, 10, 13))
    assert resolved.patch.model_dump(mode="json", exclude_unset=True) == {
        "start_date": "2026-10-15",
        "end_date": "2026-10-16",
    }


def test_date_parts_in_two_locations_must_not_disagree():
    with pytest.raises(ValueError):
        result({"更新": {"出游日期": {"游玩天数": 2}, "游玩天数": 4}})
