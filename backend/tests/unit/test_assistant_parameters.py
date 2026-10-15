"""Complete parameter contract, independent of particular user sentences."""

import importlib
import importlib.util
from copy import deepcopy

import pytest


def contract():
    name = "roambot.providers.assistant_parameters"
    assert importlib.util.find_spec(name), "native parameter contract is not implemented"
    return importlib.import_module(name)


def compile_reply(value):
    return contract().compile_assistant_parameters(value)


def test_omitted_empty_operations_are_noop():
    result = compile_reply(
        {"intent": "conditions", "updates": {"destination_region_names": ["苏州"]}}
    )
    assert result.destination_region_names == ["苏州"]
    assert result.patch.model_dump(exclude_unset=True) == {}


@pytest.mark.parametrize(
    "field,value",
    [
        ("mode", "place_evaluation"),
        ("main_origin", "常州"),
        ("companion_origins", ["南京", "上海"]),
        ("max_distance_km", 80),
        ("scenery_match_mode", "any"),
        ("target_place", "金鸡湖"),
        ("weights", {"weather": 40, "distance": 30, "popularity": 30, "fairness": 0}),
    ],
)
def test_all_public_nonsemantic_fields_compile(field, value):
    result = compile_reply({"intent": "conditions", "updates": {field: value}})
    assert result.patch.model_dump(mode="json", exclude_unset=True) == {field: value}


def test_date_fragments_are_not_computed_in_contract():
    result = compile_reply(
        {
            "intent": "conditions",
            "updates": {"date_request": {"offset_days": 1, "duration_days": 4}},
        }
    )
    assert result.date_request.model_dump(exclude_unset=True) == {
        "offset_days": 1,
        "duration_days": 4,
    }
    assert not result.patch.model_fields_set


def test_date_clear_is_atomic():
    result = compile_reply({"intent": "conditions", "updates": {"date_request": None}})
    assert result.patch.model_dump(exclude_unset=True) == {"start_date": None, "end_date": None}


def test_scenery_clear_has_no_other_changes():
    fields = ["scenery_query", "scenery_types", "scenery_keywords"]
    result = compile_reply({"intent": "conditions", "updates": {"scenery_preference": None}})
    assert result.patch.model_dump(exclude_unset=True) == dict.fromkeys(fields)


def test_region_clear_uses_semantic_empty_collection():
    result = compile_reply({"intent": "conditions", "updates": {"destination_region_names": None}})
    assert result.destination_region_names == []
    assert not result.patch.model_fields_set


def test_mixed_unresolved_and_explicit_edit():
    result = compile_reply(
        {
            "intent": "conditions",
            "updates": {"max_distance_km": 80},
            "question": "这个城市是出发地还是目的地？",
        }
    )
    assert result.patch.model_dump(exclude_unset=True) == {"max_distance_km": 80}
    assert result.question and "destination_region_names" not in result.model_fields_set


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"intent": "invalid"},
        {"intent": "conditions", "unknown": "private"},
        {"intent": "conditions", "updates": None},
        {"intent": "conditions", "clear_fields": None},
        {"intent": "conditions", "updates": {"main_origin": " "}},
        {"intent": "conditions", "updates": {"max_distance_km": "80"}},
        {"intent": "conditions", "updates": {"max_distance_km": True}},
        {"intent": "conditions", "updates": {"max_distance_km": 501}},
        {"intent": "conditions", "updates": {"scenery_query": ""}},
        {"intent": "conditions", "updates": {"scenery_query": "x" * 121}},
        {"intent": "conditions", "updates": {"scenery_keywords": ["x" * 25]}},
        {"intent": "conditions", "updates": {"companion_origins": ["甲", "乙", "丙"]}},
        {"intent": "conditions", "updates": {"start_date": "2026-10-14"}},
        {"intent": "conditions", "updates": {"destination_regions": ["320500"]}},
        {"intent": "conditions", "updates": {"date_request": {"offset_days": "1"}}},
        {
            "intent": "conditions",
            "updates": {"date_request": {"start_date": "2026-10-14", "offset_days": 1}},
        },
        {"intent": "conditions", "clear_fields": ["main_origin", "main_origin"]},
        {"intent": "conditions", "updates": {"main_origin": "甲"}, "clear_fields": ["main_origin"]},
        {"intent": "conditions", "unresolved_fields": ["main_origin"]},
        {
            "intent": "conditions",
            "unresolved_fields": ["main_origin"],
            "clear_fields": ["main_origin"],
            "question": "?",
        },
        {
            "intent": "conditions",
            "updates": {"main_origin": "甲"},
            "unresolved_fields": ["main_origin"],
            "question": "?",
        },
        {"intent": "conditions", "clear_fields": ["unknown"]},
        {"intent": "conditions", "updates": {}, "question": "https://private.invalid"},
        {"intent": "answer"},
        {"intent": "conditions", "answer_plan": {"candidate_ids": ["a"], "topic": "weather"}},
    ],
)
def test_invalid_shapes_values_and_conflicts_reject(value):
    module = contract()
    with pytest.raises(ValueError):
        module.compile_assistant_parameters(value)


@pytest.mark.parametrize("intent", ["answer", "unsupported", "conversation"])
def test_nonediting_intent_cannot_change_conditions(intent):
    value = {"intent": intent, "updates": {"main_origin": "甲"}}
    if intent == "answer":
        value["answer_plan"] = {"candidate_ids": ["a"], "topic": "weather"}
    module = contract()
    with pytest.raises(ValueError):
        module.compile_assistant_parameters(value)


def test_conversation_remains_a_distinct_noedit_intent():
    result = compile_reply({"intent": "conversation"})
    assert result.intent == "conversation" and not result.patch.model_fields_set


def test_answer_is_only_a_bounded_plan():
    result = compile_reply(
        {"intent": "answer", "answer_plan": {"candidate_ids": ["a"], "topic": "weather"}}
    )
    assert result.answer_plan.candidate_ids == ["a"]
    assert not result.patch.model_fields_set


def test_schema_has_full_fields_only_intent_required_and_single_nullable_edits():
    module = contract()
    tool = module.assistant_parameter_tool()
    assert tool["function"]["name"] == "submit_travel_intent"
    schema = tool["function"]["parameters"]
    assert schema["required"] == ["intent"] and schema["additionalProperties"] is False
    properties = schema["$defs"]["AssistantParameterUpdates"]["properties"]
    assert set(properties) == {
        "mode",
        "main_origin",
        "companion_origins",
        "date_request",
        "max_distance_km",
        "scenery_preference",
        "scenery_match_mode",
        "destination_region_names",
        "target_place",
        "weights",
    }
    preference = schema["$defs"]["SceneryPreferenceParameters"]
    assert set(preference["required"]) == {"categories", "description", "keywords"}
    assert preference["properties"]["description"]["maxLength"] == 120
    assert preference["properties"]["keywords"]["items"]["maxLength"] == 24
    assert "clear_fields" not in schema["properties"]
    for name, field in properties.items():
        assert "null" in str(field), f"{name} has no explicit cancellation representation"
        if "enum" in field:
            assert None in field["enum"], f"{name} enum excludes declared cancellation"
    assert "null" not in str(schema["$defs"]["AssistantDateRequest"])


@pytest.mark.parametrize(
    "updates",
    [
        {"date_request": {"offset_days": 1, "end_date": None}},
        {"date_request": {"start_date": 1791936000}},
        {"date_request": {"start_date": "20261014"}},
        {"weights": {"weather": True, "distance": 49, "popularity": 50, "fairness": 0}},
        {"weights": {"weather": "40", "distance": 30, "popularity": 30, "fairness": 0}},
    ],
)
def test_native_parameters_do_not_coerce_invalid_nested_scalar_types(updates):
    with pytest.raises(ValueError):
        compile_reply({"intent": "conditions", "updates": updates})


@pytest.mark.parametrize(
    "extra", [{"question": " "}, {"quick_replies": [""]}, {"unsupported_preferences": [" "]}]
)
def test_blank_model_text_is_not_a_valid_clarification_or_label(extra):
    with pytest.raises(ValueError):
        compile_reply({"intent": "conditions", **extra})


def test_native_date_schema_describes_each_distinct_temporal_quantity():
    schema = contract().assistant_parameter_tool()["function"]["parameters"]
    fields = schema["$defs"]["AssistantDateRequest"]["properties"]
    for name in ("offset_days", "duration_days", "start_date", "end_date"):
        assert fields[name].get("description"), f"{name} has no field-level semantic description"
    assert "今天" in fields["offset_days"]["description"]
    assert "时长" in fields["duration_days"]["description"]
    assert "YYYY-MM-DD" in fields["start_date"]["description"]
    assert "YYYY-MM-DD" in fields["end_date"]["description"]
    assert fields["offset_days"]["minimum"] == -366
    assert fields["duration_days"]["minimum"] == 1
    assert fields["duration_days"]["maximum"] == 31


def test_native_contract_does_not_advertise_or_accept_redundant_uncertainty_list():
    schema = contract().assistant_parameter_tool()["function"]["parameters"]
    assert "unresolved_fields" not in schema["properties"]
    with pytest.raises(ValueError):
        compile_reply(
            {
                "intent": "conditions",
                "unresolved_fields": ["main_origin"],
                "question": "从哪里出发？",
            }
        )


@pytest.mark.parametrize(
    "field,empty",
    [
        ("destination_region_names", []),
        ("companion_origins", []),
        ("scenery_types", []),
        ("scenery_keywords", []),
        ("scenery_query", ""),
        ("main_origin", ""),
    ],
)
def test_redundant_legacy_clear_protocol_is_not_a_fallback(field, empty):
    value = {
        "intent": "conditions",
        "updates": {field: empty, "max_distance_km": 90},
        "clear_fields": [field],
    }
    untouched = deepcopy(value)
    with pytest.raises(ValueError):
        compile_reply(value)
    assert value == untouched, "validation must not mutate the raw argument evidence"


@pytest.mark.parametrize(
    "field,value",
    [
        ("scenery_query", "室内展览"),
        ("scenery_query", " "),
        ("destination_region_names", ["泉州"]),
        ("main_origin", None),
        ("max_distance_km", 0),
        ("date_request", {}),
        ("date_request", {"offset_days": 1}),
        ("weights", {}),
        ("unknown", []),
        ("max_distance_km", []),
    ],
)
def test_clear_never_overrides_a_different_or_wrongly_typed_value(field, value):
    with pytest.raises(ValueError):
        compile_reply({"intent": "conditions", "updates": {field: value}, "clear_fields": [field]})


def test_equivalent_clear_does_not_bypass_nonediting_intent_or_duplicate_validation():
    for intent in ("unsupported", "conversation"):
        with pytest.raises(ValueError):
            compile_reply(
                {
                    "intent": intent,
                    "updates": {"scenery_query": ""},
                    "clear_fields": ["scenery_query"],
                }
            )
    with pytest.raises(ValueError):
        compile_reply(
            {
                "intent": "conditions",
                "updates": {"scenery_keywords": []},
                "clear_fields": ["scenery_keywords", "scenery_keywords"],
            }
        )


def test_update_schema_distinguishes_cancellation_from_unknown_role():
    schema = contract().assistant_parameter_tool()["function"]["parameters"]
    description = schema["properties"]["updates"]["description"]
    assert "未确定" in description and "已确认" in description
    assert "追问" in schema["properties"]["question"]["description"]


@pytest.mark.parametrize("field", sorted(contract().UPDATE_FIELDS))
def test_every_supported_field_has_one_explicit_cancellation_form(field):
    value = {"intent": "conditions", "updates": {field: None}}
    untouched = deepcopy(value)
    result = compile_reply(value)
    assert value == untouched
    if field == "date_request":
        assert result.patch.model_dump(exclude_unset=True) == {"start_date": None, "end_date": None}
    elif field == "destination_region_names":
        assert result.destination_region_names == [] and not result.patch.model_fields_set
    elif field == "scenery_preference":
        assert result.patch.model_dump(exclude_unset=True) == {
            "scenery_types": None,
            "scenery_query": None,
            "scenery_keywords": None,
        }
    else:
        assert result.patch.model_dump(exclude_unset=True) == {field: None}


def test_cancel_replace_preserve_are_distinct_without_parallel_operations():
    result = compile_reply(
        {
            "intent": "conditions",
            "updates": {"scenery_preference": None, "main_origin": "合肥", "max_distance_km": 90},
        }
    )
    assert result.patch.model_dump(exclude_unset=True) == {
        "scenery_query": None,
        "scenery_types": None,
        "scenery_keywords": None,
        "main_origin": "合肥",
        "max_distance_km": 90,
    }
    assert "companion_origins" not in result.patch.model_fields_set


@pytest.mark.parametrize("intent", ["conversation", "unsupported"])
def test_null_edit_is_not_allowed_in_nonediting_intents(intent):
    with pytest.raises(ValueError):
        compile_reply({"intent": intent, "updates": {"main_origin": None}})


def test_scenery_schema_explains_all_backend_categories_and_filter_effect():
    from roambot.domain.scenery_rules import TYPE_TERMS

    schema = contract().assistant_parameter_tool()["function"]["parameters"]
    vocabulary = schema["$defs"]["SceneryType"]
    description = vocabulary.get("description", "")
    for category in vocabulary["enum"]:
        assert category in description
        assert any(term in description for term in TYPE_TERMS[category])
    updates = schema["$defs"]["AssistantParameterUpdates"]["properties"]
    categories = schema["$defs"]["SceneryPreferenceParameters"]["properties"]["categories"]
    assert "筛选" in categories["description"]
    assert "全部" in categories["description"]
    assert "替换" in updates["scenery_preference"]["description"]


def test_preference_replacement_always_compiles_all_three_public_filters():
    value = {
        "intent": "conditions",
        "updates": {
            "scenery_preference": {
                "categories": ["sea"],
                "description": "海边，不去山里",
                "keywords": ["海滨"],
            }
        },
    }
    untouched = deepcopy(value)
    result = compile_reply(value)
    assert value == untouched
    assert result.patch.model_dump(mode="json", exclude_unset=True) == {
        "scenery_types": ["sea"],
        "scenery_query": "海边，不去山里",
        "scenery_keywords": ["海滨"],
    }


@pytest.mark.parametrize("missing", ["categories", "description", "keywords"])
def test_incomplete_preference_cannot_silently_keep_a_hidden_filter(missing):
    preference = {"categories": ["lake"], "description": "湖边", "keywords": ["湖泊"]}
    del preference[missing]
    with pytest.raises(ValueError):
        compile_reply({"intent": "conditions", "updates": {"scenery_preference": preference}})


@pytest.mark.parametrize("field", ["categories", "description", "keywords"])
def test_explicit_partial_preference_clear_preserves_other_components(field):
    preference = {"categories": ["lake"], "description": "湖边", "keywords": ["湖泊"]}
    preference[field] = None
    result = compile_reply({"intent": "conditions", "updates": {"scenery_preference": preference}})
    assert result.patch.model_dump(mode="json", exclude_unset=True) == {
        "scenery_types": preference["categories"],
        "scenery_query": preference["description"],
        "scenery_keywords": preference["keywords"],
    }


@pytest.mark.parametrize(
    "preference",
    [
        {"categories": ["shopping"], "description": "商场", "keywords": ["商场"]},
        {"categories": ["lake"], "description": "", "keywords": ["湖泊"]},
        {"categories": ["lake"], "description": "x" * 121, "keywords": ["湖泊"]},
        {"categories": ["lake"], "description": "湖边", "keywords": ["x" * 25]},
        {"categories": ["lake"], "description": "https://private.invalid", "keywords": []},
        {"categories": ["lake"], "description": "湖边", "keywords": ["一", "二", "三", "四", "五"]},
    ],
)
def test_grouped_preference_keeps_original_types_bounds_and_plain_text_rules(preference):
    with pytest.raises(ValueError):
        compile_reply({"intent": "conditions", "updates": {"scenery_preference": preference}})
