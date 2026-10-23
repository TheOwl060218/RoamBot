"""Evidence authority and search priority, independent of venue vocabulary."""

from datetime import UTC, datetime, timedelta

import pytest
from test_discovery_workflow import workflow

from roambot.domain.discovery import (
    BatchReview,
    EvidenceNeed,
    ExperienceRequirement,
    GroundedBatch,
    VenueSelection,
)
from roambot.services.discovery_batches import BatchWorker, freeze_batch
from roambot.services.discovery_grounding import map_fact_passages


def prepare(tmp_path):
    run = workflow(tmp_path, message="核对地图登记类型，有座位更好")
    run.plan = run.model.plan()
    run.plan.requirements = [
        ExperienceRequirement(text="地图登记类型", quote="地图登记类型", map_field="map_type"),
        ExperienceRequirement(text="可坐下", quote="有座位更好", importance="preferred"),
    ]
    run.configure_plan()
    return run


@pytest.mark.parametrize("batch_mode", [False, True])
def test_actual_map_field_can_support_its_own_fact_without_mandatory_web(tmp_path, batch_mode):
    run = prepare(tmp_path)
    run.search.search = lambda query: pytest.fail("Existing map metadata needs no web lookup")
    ids = run.retrieve()
    assert ids and not run.metrics["web_attempts"]

    def compose(conversation, goal, context, candidates):
        cards = []
        for c in candidates:
            proof = next(s for s in c["sources"] if s.get("field") == "map_type")
            cards.append(
                {
                    "place_id": c["place"]["id"],
                    "experience": "地图登记类型",
                    "reason": "地图提供了该地点的登记分类及真实地点记录，"
                    "可打开地图查看该地点的位置。",
                    "evidence_ids": [proof["id"]],
                    "requirement_support": [{"requirement": 1, "passage_ids": [proof["id"]]}],
                }
            )
        return GroundedBatch(cards=cards)

    run.model.compose = compose
    if batch_mode:
        run.revision = 1
        batch = freeze_batch(run, 0, ids, 1)
        worker = BatchWorker(run.model, lambda *args: BatchReview(approved_ids=ids, rejected=[]))
        draft = worker.compose(batch)
        decision = worker.review(batch, draft)
        run.commit_reviewed_batch(batch, draft, decision, revision=1)
    else:
        run.compose(ids)
    assert len(run.cards) == len(ids)
    assert all(c["sources"][0]["kind"] == "map_record" for c in run.cards)
    assert all("map_type" in c["sources"][0]["excerpt"] for c in run.cards)
    assert not run.errors


def test_map_fact_is_not_evidence_for_unstated_facilities_or_another_field(tmp_path):
    from roambot.domain.discovery import RequirementSupport
    from roambot.services.discovery_criteria import criterion_view, supported_criteria

    run = prepare(tmp_path)
    ids = run.retrieve()
    batch = freeze_batch(run, 0, ids, 1).payload()
    proof = next(p for p in batch["passages"].values() if p.get("field") == "map_type")
    support = [RequirementSupport(requirement=1, passage_ids=[proof["id"]])]
    for field in (None, "address", "opentime_today"):
        criterion = ExperienceRequirement(text="使用条件", quote="有座位更好", map_field=field)
        assert (
            supported_criteria(criterion_view([criterion]), support, batch["passages"], ids[0])
            is None
        )


def test_map_fact_fragments_preserve_values_and_do_not_reuse_past_daily_hours():
    old = (datetime.now(UTC) - timedelta(days=2)).timestamp()
    place = {
        "id": "amap:actual",
        "name": "实际名称",
        "city": "城市",
        "address": "真实地址",
        "map_type": "Provider动态分类",
        "verified_at": old,
        "facts": {"opentime_today": "09:00-17:00", "cost": "60", "rating": "5"},
    }
    evidence = {
        "id": "e1",
        "kind": "map_record",
        "place_id": place["id"],
        "url": "https://www.amap.com/detail/actual",
    }
    fragments = map_fact_passages(place, evidence)
    assert {p["field"] for p in fragments} == {
        "name_and_type",
        "city",
        "address",
        "map_type",
        "cost",
    }
    identity = next(p["value"] for p in fragments if p["field"] == "name_and_type")
    assert identity == {"name": place["name"], "map_type": place["map_type"]}
    assert next(p["value"] for p in fragments if p["field"] == "cost") == "60"
    assert all(p["place_id"] == place["id"] and p["evidence_id"] == "e1" for p in fragments)
    assert "opentime_today" in place["facts"], "Do not mutate cached map facts"


def test_pending_preference_does_not_outrank_actual_required_evidence_gap(tmp_path):
    run = prepare(tmp_path)
    run.plan.requirements[0].map_field = None
    run.plan.requirements[0].text = "核心活动资料"
    ids = run.retrieve()
    run.web_seen.clear()
    run.metrics["web_attempts"] = 0
    run.evidence_needs.clear()
    run.record_evidence_needs(
        [
            EvidenceNeed(place_id=ids[1], query="偏好政策", requirement=2),
            EvidenceNeed(place_id=ids[0], query="核心活动资料", requirement=1),
            EvidenceNeed(place_id=ids[0], query="未知条件", requirement=6),
        ],
        ids,
    )
    run.evidence_query = "宽泛的偏好补查"
    queries = []
    run.web_search = lambda query: queries.append(query) or []
    run.supplement()
    assert queries == [run.places[ids[0]]["name"] + " 核心活动资料"]
    assert not any(n.requirement == 6 for n in run.evidence_needs)


def test_missing_public_core_evidence_queues_core_instead_of_optional_policy(tmp_path):
    run = prepare(tmp_path)
    run.plan.requirements[0].map_field = None
    run.search.search = lambda query: []
    ids = run.retrieve()
    run.model.compose = lambda *args: GroundedBatch(cards=[])
    run.compose(ids)
    eligible = run.pending_evidence_needs()
    assert eligible
    assert all(n.requirement == 1 for n in eligible)
    assert {n.place_id for n in eligible} <= set(ids)
    assert "可坐下" not in eligible[0].query


def test_targeted_supplement_reuses_verified_candidate_instead_of_renominating(tmp_path):
    run = prepare(tmp_path)
    run.plan.requirements[0].map_field = None
    run.search.search = lambda query: []
    run.ensure_core_evidence(run.retrieve())
    need = run.pending_evidence_needs()[0]
    run.web_seen.clear()
    name = run.places[need.place_id]["name"]
    run.web_search = lambda query: [
        {
            "url": "https://example.org/current",
            "title": name,
            "excerpt": name + "公开的当前资料。",
            "kind": "search_excerpt",
        }
    ]
    run.model.nominate = lambda *args: pytest.fail(
        "Existing entity does not need another nomination"
    )
    assert need.place_id in run.supplement()


def test_id_only_nomination_uses_actual_bound_name_without_repeating_map_calls(tmp_path):
    run = workflow(tmp_path)
    run.plan = run.model.plan()
    run.configure_plan()
    run.model.nominate = lambda *args: VenueSelection(venues=[{"place_id": "amap:2"}])
    ids = run.retrieve()
    assert ids == ["amap:2"]
    assert run.places[ids[0]]["name"] == "湖边绿地"
    assert len([call for call in run.maps.calls if call[0] == "search"]) == 1


def test_unknown_id_only_nomination_cannot_create_or_search_an_invented_entity(tmp_path):
    run = workflow(tmp_path)
    run.plan = run.model.plan()
    run.configure_plan()
    run.model.nominate = lambda *args: VenueSelection(venues=[{"place_id": "amap:invented"}])
    assert run.retrieve() == []
    assert "amap:invented" not in run.places
    assert len([call for call in run.maps.calls if call[0] == "search"]) == 1


def test_free_form_gap_query_cannot_rewrite_its_bound_user_condition(tmp_path):
    run = prepare(tmp_path)
    run.plan.requirements[0].map_field = None
    ids = run.retrieve()
    need = EvidenceNeed(place_id=ids[0], query="无关的偏好政策", requirement=1)
    assert run.need_query(need) == run.places[ids[0]]["name"] + " " + run.plan.requirements[0].text
    assert need.query not in run.need_query(need)

    from datetime import date
    run.context.start_date = date(2026, 10, 18)
    run.context.end_date = date(2026, 10, 19)
    need.date_sensitive = True
    assert run.need_query(need).endswith("2026-10-18 2026-10-19")
    assert need.query not in run.need_query(need)


def test_unreviewed_path_cannot_use_a_business_name_to_claim_user_activity(tmp_path):
    run = prepare(tmp_path)
    run.plan.requirements[0].map_field = None
    run.reviewer = None
    run.review = None
    run.search.search = lambda query: []
    ids = run.retrieve()
    assert run.compose(ids) == 0
    assert not run.cards


def test_same_explicitly_cited_registration_can_be_shared_but_category_alone_cannot(tmp_path):
    from roambot.domain.discovery import RequirementSupport
    from roambot.services.discovery_criteria import criterion_view, supported_criteria

    run = prepare(tmp_path)
    ids = run.retrieve()
    passages = freeze_batch(run, 0, ids, 1).payload()["passages"]
    joint = next(
        p
        for p in passages.values()
        if p["place_id"] == ids[0] and p.get("field") == "name_and_type"
    )
    category = next(
        p for p in passages.values() if p["place_id"] == ids[0] and p.get("field") == "map_type"
    )
    criteria = criterion_view(
        [
            ExperienceRequirement(text="经营活动", quote="经营活动"),
            ExperienceRequirement(text="非纯展示", quote="非纯展示"),
        ]
    )
    supports = [
        RequirementSupport(requirement=1, passage_ids=[joint["id"]]),
        RequirementSupport(requirement=2, passage_ids=[category["id"]]),
    ]
    result = supported_criteria(criteria, supports, passages, ids[0], allow_business_inference=True)
    assert result and joint["excerpt"] in result["required_experiences"][1]["quotes"]
    supports[0].passage_ids = [category["id"]]
    assert (
        supported_criteria(criteria, supports, passages, ids[0], allow_business_inference=True)
        is None
    )
