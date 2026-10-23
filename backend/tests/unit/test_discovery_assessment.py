"""Program rules apply to model observations, including optional failures."""

import copy

import pytest

from roambot.domain.discovery_assessment import NativeBatchAssessment
from roambot.services.discovery_assessment import decide_assessment


def inputs():
    return (
        {
            "user_request": {
                "criteria": [
                    {"index": 1, "text": "核心活动", "role": "goal", "importance": "required"},
                    {
                        "index": 2,
                        "text": "可取舍偏好",
                        "role": "condition",
                        "importance": "preferred",
                    },
                    {"index": 3, "text": "必要设施", "role": "condition", "importance": "required"},
                ]
            }
        },
        [
            {
                "place": {"id": "real"},
                "reason": "未经核实的额外服务描述，但原有核心活动本身有来源依据。",
                "experience": "原活动",
                "sources": [
                    {
                        "id": "p",
                        "kind": "web_page",
                        "place_id": "real",
                        "excerpt": "必要设施实际介绍",
                    },
                    {"id": "r", "kind": "measure_routes", "place_id": "real"},
                ],
            }
        ],
        {
            "assessments": [
                {
                    "place_id": "real",
                    "entity_matches": True,
                    "broad_intent_matches": False,
                    "grounded_reason": "实际资料记载的服务与本次核心活动一致，"
                    "必要设施也有依据，可安排体验。",
                    "experience": "休闲小聚",
                    "evidence_ids": ["p"],
                    "note": "文案有待更正",
                    "checks": [
                        {
                            "requirement": 1,
                            "state": "supported",
                            "evidence_ids": ["p"],
                            "note": "核心活动有据",
                        },
                        {"requirement": 2, "state": "unknown", "note": "仅偏好未证实"},
                        {
                            "requirement": 3,
                            "state": "supported",
                            "evidence_ids": ["p"],
                            "note": "必要设施有据",
                        },
                    ],
                }
            ],
        },
    )


def decide(value, context, cards):
    return decide_assessment(NativeBatchAssessment.model_validate(value), context, cards)


def test_model_view_separates_measurements_from_venue_evidence_without_losing_facts():
    from roambot.providers.discovery_review import compact_facts

    _, cards, _ = inputs()
    cards[0]["route"] = {"distance_km": 2.4, "mode": "walking", "estimated": False}
    cards[0]["weather"] = [{"date": "2026-10-17", "condition": "晴"}]
    cards[0]["sources"].append(
        {"id": "w", "kind": "check_weather", "place_id": "real"})
    original = copy.deepcopy(cards)
    view, references = compact_facts(cards)

    assert references == {"s1": "p"}
    assert [source["kind"] for source in view[0]["sources"]] == ["web_page"]
    assert view[0]["route"] == cards[0]["route"]
    assert view[0]["weather"] == cards[0]["weather"]
    assert cards == original


def test_native_view_keeps_choice_logic_and_independent_limits_without_mutating_authority():
    from roambot.providers.discovery_review import observation_context

    context, _, _ = inputs()
    context["user_request"]["criteria"][1].update(role="goal", importance="required")
    context["user_request"]["criteria"].append(
        {"index": 4, "text": "整组要求", "scope": "collection", "importance": "required"})
    context["user_request"]["requirement_groups"] = [
        {"quote": "任选活动", "operator": "any", "requirements": [1, 2]}]
    before = copy.deepcopy(context)
    visible = observation_context(context)
    assert visible["acceptance_policy"] == {"all_of": [3], "any_of": [[1, 2]]}
    criteria = visible["user_request"]["criteria"]
    assert [c["index"] for c in criteria] == [1, 2, 3]
    assert all("importance" not in c and c["choice_group"] == 1 for c in criteria[:2])
    assert criteria[2]["importance"] == "required"
    assert context == before


def test_fact_value_alias_still_requires_the_literal_actual_source():
    from roambot.domain.discovery_assessment import AnchoredFact

    context, cards, value = inputs()
    observation = value["assessments"][0]
    observation["anchored_facts"] = [{"evidence_id": "p", "value": "必要设施实际介绍"}]
    assert decide(value, context, cards).approved_ids == ["real"]
    observation["anchored_facts"][0]["value"] = "未在来源出现的设施"
    with pytest.raises(ValueError, match="事实摘录"):
        decide(value, context, cards)
    with pytest.raises(ValueError, match="不一致"):
        AnchoredFact.model_validate({"evidence_id": "p", "value": "甲", "quote": "乙"})


@pytest.mark.parametrize("alignment", ["inconclusive", "conflicting", "venue_only"])
def test_name_cannot_repair_uncertain_registration_but_real_service_evidence_can(alignment):
    context, cards, value = inputs()
    context["user_request"]["criteria"] = context["user_request"]["criteria"][:1]
    item = value["assessments"][0]
    item["checks"] = item["checks"][:1]
    item["checks"][0]["registration_alignment"] = alignment
    cards[0]["sources"][0].update(kind="map_record", field="name_and_type")

    result = decide(value, context, cards)
    assert result.approved_ids == []
    assert [n.requirement for n in result.evidence_needs] == [1]

    # Independent service evidence may resolve a stale or broad registration.
    cards[0]["sources"][0].update(kind="web_page")
    assert decide(value, context, cards).approved_ids == ["real"]


def test_live_schema_requires_independent_registration_observation():
    from roambot.domain.discovery_assessment import LiveBatchAssessment

    _, _, value = inputs()
    value["assessments"][0]["entity_scope"] = "place"
    with pytest.raises(ValueError, match="registration_alignment"):
        LiveBatchAssessment.model_validate(value)
    for check in value["assessments"][0]["checks"]:
        check["registration_alignment"] = "aligned"
        check["activity"] = None
    assert LiveBatchAssessment.model_validate(value).assessments


@pytest.mark.parametrize("scope", ["collection", "administrative_area", "unknown"])
def test_coordinate_and_nice_reason_cannot_promote_a_nonconcrete_entity(scope):
    context, cards, value = inputs()
    value["assessments"][0]["entity_scope"] = scope
    result = decide(value, context, cards)
    assert not result.approved_ids
    assert not result.reason_revisions
    assert not result.evidence_needs


def test_broad_request_cannot_expose_retrieval_indices_as_user_requirements():
    from roambot.providers.discovery_review import observation_context

    context = {"user_request": {"messages": ["想换个环境"], "criteria": []},
               "requested_directions": [{"index": 1, "experience": "检索假设"}],
               "covered_direction_indices": []}
    before = copy.deepcopy(context)
    visible = observation_context(context)
    assert visible["user_request"]["criteria"] == []
    assert visible["acceptance_policy"] == {"all_of": [], "any_of": []}
    assert "requested_directions" not in visible
    assert "covered_direction_indices" not in visible
    assert context == before


@pytest.mark.parametrize("change", ["none", "missing", "past", "unquoted", "map_only", "venue_only", "forged_year"])
def test_event_requires_venue_bound_period_overlapping_the_trip(change):
    context, cards, value = inputs()
    context.update(start_date="2026-10-18", end_date="2026-10-20")
    context["user_request"]["criteria"] = context["user_request"]["criteria"][:1]
    item = value["assessments"][0]
    item["checks"] = item["checks"][:1]
    check = item["checks"][0]
    cards[0]["sources"][0]["excerpt"] = "活动于2026-10-18至2026-10-19举办。"
    check["activity"] = {"kind": "event", "period": {
        "start_date": "2026-10-18", "end_date": "2026-10-19",
        "evidence_id": "p", "quote": "活动于2026-10-18至2026-10-19举办。"}}
    if change == "missing":
        check["activity"]["period"] = None
    elif change == "past":
        check["activity"]["period"].update(start_date="2026-10-15", end_date="2026-10-16")
        cards[0]["sources"][0]["excerpt"] = "活动于2026-10-15至2026-10-16举办。"
        check["activity"]["period"]["quote"] = cards[0]["sources"][0]["excerpt"]
    elif change == "unquoted":
        check["activity"]["period"]["quote"] = "资料中没有的活动排期"
    elif change == "map_only":
        cards[0]["sources"][0].update(kind="map_record", field="name_and_type")
    elif change == "venue_only":
        check["activity"] = {"kind": "venue_only", "period": None}
    elif change == "forged_year":
        cards[0]["sources"][0]["excerpt"] = "活动于2024-10-18至2024-10-19举办。"
        check["activity"]["period"]["quote"] = cards[0]["sources"][0]["excerpt"]
    result = decide(value, context, cards)
    assert result.approved_ids == (["real"] if change == "none" else [])
    if change not in {"none", "venue_only"}:
        assert result.evidence_needs[0].date_sensitive


def test_event_numeric_date_normalization_does_not_borrow_the_requested_year():
    from datetime import date
    from roambot.services.discovery_assessment import quoted_event_dates

    assert {date(2026, 10, 18), date(2026, 10, 19)} <= quoted_event_dates("2026年10月18日至19日")
    assert {date(2026, 9, 18), date(2026, 10, 19)} <= quoted_event_dates("2026/9/18 至 10/19")
    assert quoted_event_dates("10月18日至19日") == set()


@pytest.mark.parametrize("preference", ["unknown", "contradicted"])
def test_optional_failure_and_broad_vote_cannot_veto_supported_explicit_goal(preference):
    context, cards, value = inputs()
    value["assessments"][0]["checks"][1]["state"] = preference
    if preference == "contradicted":
        value["assessments"][0]["checks"][1]["evidence_ids"] = ["p"]
    result = decide(value, context, cards)
    assert result.approved_ids == ["real"] and not result.rejected
    assert len(result.reason_revisions) == 1 and not result.evidence_needs


@pytest.mark.parametrize("state", ["unknown", "contradicted"])
def test_missing_required_condition_is_not_repaired_away(state):
    context, cards, value = inputs()
    check = value["assessments"][0]["checks"][2]
    check["state"] = state
    result = decide(value, context, cards)
    assert not result.approved_ids and not result.reason_revisions
    assert [r.place_id for r in result.rejected] == ["real"]
    assert [n.requirement for n in result.evidence_needs] == ([3] if state == "unknown" else [])


def test_nonmatching_goal_or_entity_cannot_be_fixed_by_a_nice_reason():
    context, cards, value = inputs()
    for entity in (True, False):
        changed = copy.deepcopy(value)
        changed["assessments"][0]["entity_matches"] = entity
        changed["assessments"][0]["checks"][0]["state"] = "contradicted"
        assert not decide(changed, context, cards).approved_ids


@pytest.mark.parametrize(
    "bad",
    [
        "missing",
        "duplicate",
        "foreign",
        "invented_criterion",
        "foreign_source",
        "route_only",
        "false_revision",
    ],
)
def test_incomplete_or_unbound_observations_cannot_be_used_as_approval(bad):
    context, cards, value = inputs()
    item = value["assessments"][0]
    if bad == "missing":
        item["checks"].pop()
    elif bad == "duplicate":
        value["assessments"].append(copy.deepcopy(item))
    elif bad == "foreign":
        item["place_id"] = "not-this-batch"
    elif bad == "invented_criterion":
        item["checks"][0]["requirement"] = 6
    elif bad == "foreign_source":
        cards[0]["sources"][0]["place_id"] = "another-venue"
    elif bad == "route_only":
        item["checks"][0]["evidence_ids"] = ["r"]
    else:
        item["evidence_ids"] = ["invented"]
    with pytest.raises(ValueError):
        decide(value, context, cards)


def test_missing_final_copy_is_invalid_and_broad_requests_still_need_intent_match():
    context, cards, value = inputs()
    broken = copy.deepcopy(value)
    del broken["assessments"][0]["grounded_reason"]
    with pytest.raises(ValueError):
        decide(broken, context, cards)
    context["user_request"]["criteria"] = []
    item = value["assessments"][0]
    item["checks"] = []
    assert not decide(value, context, cards).approved_ids
    item["broad_intent_matches"] = True
    assert decide(value, context, cards).approved_ids == ["real"]


def test_source_first_review_does_not_turn_a_draft_or_proposed_support_into_fact():
    from roambot.providers.discovery_review import fact_view

    _, cards, _ = inputs()
    cards[0]["required_experiences"] = [{"requirement": "草稿自称满足", "quotes": ["未验证文字"]}]
    actual = fact_view(cards)[0]
    assert (
        not {"reason", "experience", "required_experiences", "preferred_experiences"}
        & actual.keys()
    )
    assert actual["sources"] == cards[0]["sources"]
    assert actual["place"] == cards[0]["place"]
    assert "reason" in cards[0], "Preparing the fact view must not mutate the original draft"


@pytest.mark.parametrize("operator,states,approved", [
    ("any", ("supported", "unknown", "supported"), True),
    ("any", ("unknown", "supported", "supported"), True),
    ("any", ("supported", "supported", "unknown"), False),
    ("any", ("unknown", "unknown", "supported"), False),
    ("all", ("supported", "unknown", "supported"), False),
    ("all", ("supported", "supported", "supported"), True),
])
def test_activity_choice_does_not_drop_independent_required_facility(operator, states, approved):
    context, cards, value = inputs()
    context["user_request"]["criteria"][1].update(role="goal", importance="required")
    context["user_request"]["requirement_groups"] = [
        {"quote": "活动选择", "operator": operator, "requirements": [1, 2]}]
    for check, state in zip(value["assessments"][0]["checks"], states, strict=True):
        check.update(state=state, evidence_ids=["p"] if state == "supported" else [])
    result = decide(value, context, cards)
    assert bool(result.approved_ids) is approved
    if approved:
        assert not result.evidence_needs, "An unused alternative must not trigger paid research"


def test_tolerance_needs_no_venue_proof_but_cannot_replace_a_required_condition():
    context, cards, value = inputs()
    context["user_request"]["criteria"][1]["importance"] = "accepted"
    value["assessments"][0]["checks"][1].update(state="supported", evidence_ids=[])
    assert decide(value, context, cards).approved_ids == ["real"]
    value["assessments"][0]["checks"][2].update(state="unknown", evidence_ids=[])
    assert not decide(value, context, cards).approved_ids


def test_reason_basis_requires_a_verbatim_quote_from_the_actual_cited_venue():
    context, cards, value = inputs()
    value["assessments"][0]["anchored_facts"] = [{"evidence_id": "p", "quote": "必要设施"}]
    assert decide(value, context, cards).approved_ids == ["real"]
    value["assessments"][0]["anchored_facts"][0]["quote"] = "新增且并未记载的服务"
    with pytest.raises(ValueError, match="摘录"):
        decide(value, context, cards)


def test_omitted_or_unproved_unused_alternative_cannot_drop_an_independent_hard_limit():
    context, cards, value = inputs()
    context["user_request"]["criteria"][1].update(role="goal", importance="required")
    context["user_request"]["requirement_groups"] = [
        {"quote": "活动选择", "operator": "any", "requirements": [1, 2]}]
    value["assessments"][0]["checks"].pop(1)
    assert decide(value, context, cards).approved_ids == ["real"]
    value["assessments"][0]["checks"][1].update(state="unknown", evidence_ids=[])
    assert not decide(value, context, cards).approved_ids


def test_uncited_negative_is_unknown_and_never_an_approval_for_a_required_fact():
    context, cards, value = inputs()
    value["assessments"][0]["checks"][2].update(state="contradicted", evidence_ids=[])
    result = decide(value, context, cards)
    assert not result.approved_ids
    assert [need.requirement for need in result.evidence_needs] == [3]


def test_citation_cardinality_can_normalize_but_conflicting_ids_cannot():
    from roambot.domain.discovery_assessment import RequirementFinding

    assert RequirementFinding(requirement=1, state="supported", evidence_id="p").evidence_ids == ["p"]
    assert RequirementFinding(requirement=1, state="unknown", evidence_id=[], evidence_ids=[]).evidence_ids == []
    with pytest.raises(ValueError):
        RequirementFinding(requirement=1, state="supported", evidence_id="p", evidence_ids=["foreign"])
