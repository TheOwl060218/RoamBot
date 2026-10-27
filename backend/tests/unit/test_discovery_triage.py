"""Match, unknown and incompatible are distinct; unrelated facts are not proof."""

import pytest
from test_discovery_workflow import workflow

from roambot.domain.discovery import (
    ExperienceRequirement,
    GroundedBatch,
    RequirementSupport,
)
from roambot.domain.discovery_execution import BatchResult
from roambot.services.discovery_batches import BatchWorker, freeze_batch
from roambot.services.discovery_criteria import criterion_view, supported_criteria


def prepared(tmp_path):
    run = workflow(tmp_path, message="做本次活动，有附加条件更好")
    run.plan = run.model.plan()
    run.plan.requirements = [ExperienceRequirement(text="本次活动", quote="本次活动")]
    run.configure_plan()
    ids = run.retrieve()
    run.revision = 1
    return run, ids


def test_only_preferences_do_not_force_search_or_invent_a_missing_required_field(tmp_path):
    run = workflow(tmp_path, message="看看当地，有附加条件更好")
    run.plan = run.model.plan()
    run.plan.requirements = [
        ExperienceRequirement(text="附加条件", quote="附加条件", importance="preferred")
    ]
    before = run.plan.requirements[0].model_dump()
    run.configure_plan()
    run.search.search = lambda query: pytest.fail("No mandatory search for a preference")
    ids = run.retrieve()
    compose = run.model.compose

    def no_claimed_preference(*args):
        batch = compose(*args)
        for card in batch.cards:
            card.requirement_support = []
        return batch

    run.model.compose = no_claimed_preference
    run.compose(ids)
    assert len(run.cards) == 4 and not run.metrics["web_attempts"]
    assert run.plan.requirements[0].model_dump() == before


def test_route_can_remain_a_card_fact_but_cannot_be_the_only_activity_support():
    criteria = criterion_view([ExperienceRequirement(text="本次活动", quote="本次活动")])
    passages = {
        "joint": {
            "id": "joint",
            "evidence_id": "e1",
            "place_id": "actual",
            "kind": "map_record",
            "field": "name_and_type",
            "excerpt": "明确的营业记录",
        },
        "route": {
            "id": "route",
            "evidence_id": "e2",
            "place_id": "actual",
            "kind": "measure_routes",
        },
    }
    supports = [RequirementSupport(requirement=1, passage_ids=["joint", "route"])]
    result = supported_criteria(
        criteria, supports, passages, "actual", allow_business_inference=True
    )
    assert result["required_experiences"][0]["quotes"] == ["明确的营业记录"]
    supports[0].passage_ids = ["route"]
    assert (
        supported_criteria(criteria, supports, passages, "actual", allow_business_inference=True)
        is None
    )
    supports[0].passage_ids = ["joint", "invented"]
    assert (
        supported_criteria(criteria, supports, passages, "actual", allow_business_inference=True)
        is None
    )
    passages["route"]["place_id"] = "foreign"
    supports[0].passage_ids = ["joint", "route"]
    assert (
        supported_criteria(criteria, supports, passages, "actual", allow_business_inference=True)
        is None
    )


def test_explicit_primary_registration_reference_is_shared_but_uncited_data_is_not(tmp_path):
    run, ids = prepared(tmp_path)
    passages = freeze_batch(run, 0, ids, 1).payload()["passages"]
    joint = next(
        p
        for p in passages.values()
        if p["place_id"] == ids[0] and p.get("field") == "name_and_type"
    )
    address = next(
        p for p in passages.values() if p["place_id"] == ids[0] and p.get("field") == "address"
    )
    criteria = criterion_view(run.plan.requirements)
    support = [RequirementSupport(requirement=1, passage_ids=[address["id"]])]
    assert (
        supported_criteria(criteria, support, passages, ids[0], allow_business_inference=True)
        is None
    )
    result = supported_criteria(
        criteria, support, passages, ids[0], allow_business_inference=True, cited_ids=[joint["id"]]
    )
    assert joint["excerpt"] in result["required_experiences"][0]["quotes"]


def exclusion_payload(run, ids):
    passages = freeze_batch(run, 0, ids, 1).payload()["passages"]
    proof = next(
        p
        for p in passages.values()
        if p["place_id"] == ids[0] and p.get("field") == "name_and_type"
    )
    return {
        "cards": [],
        "not_suitable": [
            {
                "place_id": ids[0],
                "note": "登记的用途与本次活动不符，不是资料缺失",
                "evidence_ids": [proof["id"]],
            }
        ],
    }


def test_unsuitable_candidate_is_not_automatically_researched_but_unknown_ones_are(tmp_path):
    run, ids = prepared(tmp_path)
    payload = exclusion_payload(run, ids)
    run.model.compose = lambda *args: GroundedBatch.model_validate(payload)
    run.compose(ids)
    assert run.unsuitable == {ids[0]}
    assert run.pending_evidence_needs()
    assert all(n.place_id != ids[0] for n in run.pending_evidence_needs())
    queries = []
    run.web_search = lambda query: queries.append(query) or []
    run.supplement()
    assert len(queries) == 1 and not queries[0].startswith(run.places[ids[0]]["name"])
    place = run.places[ids[0]]
    run.research_sources.append(
        {
            "title": place["name"],
            "url": "https://example.org/new",
            "excerpt": place["name"] + "的新资料",
            "kind": "search_excerpt",
        }
    )
    run.ingest([place])
    assert ids[0] not in run.unsuitable, "new evidence must allow a fresh assessment"


@pytest.mark.parametrize("cancel", [False, True])
def test_unsuitable_decisions_are_committed_only_by_current_uncancelled_coordinator(
    tmp_path, cancel
):
    run, ids = prepared(tmp_path)
    batch = freeze_batch(run, 0, ids, 1)
    payload = exclusion_payload(run, ids)
    payload["not_suitable"].append(
        {
            "place_id": ids[1],
            "note": "错误借用另一个地点依据",
            "evidence_ids": payload["not_suitable"][0]["evidence_ids"],
        }
    )
    draft = BatchResult.freeze(batch, payload)
    worker = BatchWorker(run.model, lambda *args: pytest.fail("No publication to review"))
    decision = worker.review(batch, draft)
    assert not run.unsuitable
    if cancel:
        run.cancelled.set()
        with pytest.raises(ValueError):
            run.commit_reviewed_batch(batch, draft, decision, revision=1)
        assert not run.unsuitable
    else:
        run.commit_reviewed_batch(batch, draft, decision, revision=1)
        assert run.unsuitable == {ids[0]}
