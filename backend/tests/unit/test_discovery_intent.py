"""Quoted temporal fragments retain roles and cross calendar boundaries."""

from datetime import date

import pytest

from roambot.domain.discovery import ModelRetrievalPlan, RetrievalPlan, SearchContext, TemporalIntent
from roambot.services.discovery_intent import compile_intent, temporal_updates


def test_relative_start_retains_existing_duration_across_month_boundary():
    previous = SearchContext(start_date=date(2026, 10, 17), end_date=date(2026, 10, 18))
    actual = temporal_updates(TemporalIntent(quote="更正时间", request={"offset_days": 1}),
        previous, "更正时间", date(2026, 10, 30))
    assert (actual["start_date"], actual["end_date"]) == (date(2026, 10, 31), date(2026, 11, 1))


def test_duration_change_keeps_start_but_unanchored_or_conflicting_dates_do_not_execute():
    previous = SearchContext(start_date=date(2026, 10, 17), end_date=date(2026, 10, 17))
    intent = TemporalIntent(quote="两天", request={"duration_days": 2})
    assert temporal_updates(intent, previous, "两天", date(2026, 10, 16))["end_date"] == date(2026, 10, 18)
    with pytest.raises(ValueError, match="起点"):
        temporal_updates(intent, SearchContext(), "两天", date(2026, 10, 16))
    with pytest.raises(ValueError, match="原文"):
        temporal_updates(intent, previous, "没有时间原话", date(2026, 10, 16))


def test_native_coverage_is_explicit_and_collection_compiles_without_an_extra_model_call():
    required = set(ModelRetrievalPlan.model_json_schema()["required"])
    assert {"temporal", "collection_intent", "activity_relation"} <= required
    plan = ModelRetrievalPlan(context={}, goal="本轮活动", temporal=None,
        collection_intent={"quote": "不同活动", "importance": "required"}, activity_relation=None)
    compiled = compile_intent(plan)
    assert len(compiled.requirements) == 1
    assert compiled.requirements[0].scope == "collection"
    assert compiled.requirements[0].quote == "不同活动"
    assert not plan.requirements, "Compiling must not mutate shared planning input"


def test_native_context_can_carry_transport_provenance_without_relaxing_public_context():
    plan = ModelRetrievalPlan(context={"travel_mode": "bicycling", "travel_mode_quote": "骑车"},
        goal="本次活动", temporal=None, activity_relation=None, collection_intent=None)
    compiled = compile_intent(plan, "骑车")
    assert compiled.travel_mode_quote == "骑车"
    with pytest.raises(ValueError):
        SearchContext(start_date=date(2026, 10, 17))


def test_optional_collection_intent_does_not_become_required_during_compilation():
    plan = ModelRetrievalPlan(context={}, goal="本次活动", temporal=None, activity_relation=None,
        collection_intent={"quote": "希望多些选择", "importance": "preferred"})
    assert compile_intent(plan).requirements[0].importance == "preferred"


def option(quote, query):
    return {"quote": quote, "experience": quote, "map_query": query, "web_query": query + " 介绍"}


def test_required_alternatives_compile_independent_queries_not_only_a_combined_venue():
    plan = ModelRetrievalPlan(context={}, goal="甲或乙", temporal=None, collection_intent=None,
        activity_relation={"operator": "any", "importance": "required", "quote": "甲或乙",
                           "options": [option("甲", "甲场所"), option("乙", "乙场所")]},
        directions=[{"experience": "甲和乙", "map_query": "甲乙复合场所", "web_query": "甲乙"}])
    compiled = compile_intent(plan, "甲或乙")
    assert [d.map_query for d in compiled.directions] == ["甲场所", "乙场所"]
    assert compiled.requirement_groups[0].requirements == [1, 2]
    assert all(r.importance == "required" for r in compiled.requirements)
    assert plan.directions[0].map_query == "甲乙复合场所", "Do not mutate the original model response"


def test_optional_activity_choices_preserve_core_goal_and_do_not_become_hard_gates():
    plan = ModelRetrievalPlan(context={}, goal="休息，有甲或乙更好", temporal=None, collection_intent=None,
        requirements=[{"text": "休息", "quote": "休息", "role": "goal"}],
        activity_relation={"operator": "any", "importance": "preferred", "quote": "甲或乙",
                           "options": [option("甲", "甲场所"), option("乙", "乙场所")]},
        directions=[{"experience": "休息", "map_query": "休息场所", "web_query": "休息场所"}])
    compiled = compile_intent(plan, "休息，有甲或乙更好")
    assert [r.importance for r in compiled.requirements] == ["required", "preferred", "preferred"]
    assert not compiled.requirement_groups
    assert compiled.directions[0].map_query == "休息场所"


def test_all_keeps_shared_venue_retrieval_and_unknown_branch_quote_is_rejected():
    plan = RetrievalPlan(context={}, goal="甲且乙", activity_relation={
        "operator": "all", "quote": "甲且乙", "options": [option("甲", "甲场所"), option("乙", "乙场所")]},
        directions=[{"experience": "甲乙共同活动", "map_query": "共同场所", "web_query": "共同场所"}])
    compiled = compile_intent(plan, "甲且乙")
    assert [d.map_query for d in compiled.directions] == ["共同场所"]
    assert compiled.requirement_groups[0].operator == "all"
    plan.activity_relation.options[1].quote = "未要求的活动"
    with pytest.raises(ValueError, match="真实活动原话"):
        compile_intent(plan, "甲且乙")


def test_four_options_are_not_silently_cut_to_the_previous_three_direction_limit():
    quotes = ["甲", "乙", "丙", "丁"]
    original = "或".join(quotes)
    plan = RetrievalPlan(context={}, goal=original,
        requirements=[{"text": "必要属性", "quote": "必要属性", "role": "condition"}],
        activity_relation={"operator": "any", "quote": original,
                           "options": [option(q, q + "场所") for q in quotes]})
    compiled = compile_intent(plan, "必要属性，" + original)
    assert [d.map_query for d in compiled.directions] == [q + "场所" for q in quotes]
    assert compiled.requirement_groups[0].requirements == [2, 3, 4, 5]
    assert compiled.requirements[0].importance == "required"
