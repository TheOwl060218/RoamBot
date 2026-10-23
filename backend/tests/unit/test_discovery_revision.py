"""Repair unsupported wording without changing the venue or bypassing evidence."""

import copy

import pytest
from test_discovery_batches import ready_run

from roambot.domain.discovery import BatchReview, ExperienceRequirement, RejectedCard
from roambot.services.discovery_batches import BatchWorker, freeze_batch
from roambot.services.discovery_revision import validated_revisions

CORRECTED = "资料登记的营业内容与本次活动一致，可围绕这项实际服务安排休闲小聚。"


def reviewer(cards):
    first = cards[0]
    return BatchReview(
        approved_ids=[c["place"]["id"] for c in cards],
        rejected=[],
        reason_revisions=[
            {
                "place_id": first["place"]["id"],
                "reason": CORRECTED,
                "experience": "休闲小聚",
                "evidence_ids": [first["sources"][0]["id"]],
            }
        ],
    )


@pytest.mark.parametrize("coordinated", [False, True])
def test_revision_reaches_publication_without_another_model_or_search_call(tmp_path, coordinated):
    run, ids = ready_run(tmp_path)
    original_compose = run.model.compose
    seen = []

    def compose(*args):
        draft = original_compose(*args)
        draft.cards[0].reason = "该地点提供免费私人包间和专人接待，因此适合本次活动，不需提前预约。"
        draft.cards[0].experience = "私人包间"
        return draft

    def review(cards):
        seen.append(copy.deepcopy(cards))
        return reviewer(cards)

    run.model.compose = compose
    run.search.search = lambda *args: pytest.fail("Copy repair must not purchase evidence")
    before_searches = run.metrics["web_attempts"]
    before_compositions = run.model.calls.count("compose")
    before_place, before_route = copy.deepcopy(run.places[ids[0]]), copy.deepcopy(run.routes)
    if coordinated:
        worker = BatchWorker(run.model, lambda conversation, context, cards: review(cards))
        batch = freeze_batch(run, 0, ids, 1)
        draft = worker.compose(batch)
        decision = worker.review(batch, draft)
        assert not run.cards and "私人包间" in draft.payload()["cards"][0]["reason"]
        run.commit_reviewed_batch(batch, draft, decision, revision=1)
    else:
        run.reviewer = review
        run.compose(ids)
    assert len(seen) == 1 and len(run.cards) == len(ids)
    assert seen[0][0]["experience"] == "私人包间", "Visible labels must also be reviewed"
    published = next(c for c in run.cards if c["place"]["id"] == ids[0])
    assert published["reason"] == CORRECTED and published["experience"] == "休闲小聚"
    assert published["place"] == before_place and run.routes == before_route
    assert run.metrics["web_attempts"] == before_searches
    assert run.model.calls.count("compose") == before_compositions + 1


@pytest.mark.parametrize(
    "bad",
    ["unknown_venue", "rejected", "duplicate", "unknown_source", "cross_source", "route_only"],
)
def test_revision_cannot_create_an_approval_or_cite_unavailable_facts(tmp_path, bad):
    run, ids = ready_run(tmp_path)
    batch = freeze_batch(run, 0, ids, 1)
    cards = batch.payload()["candidates"]
    result = reviewer(cards)
    revision = result.reason_revisions[0]
    if bad == "unknown_venue":
        revision.place_id = "invented"
    elif bad == "rejected":
        result.approved_ids.remove(ids[0])
        result.rejected.append(RejectedCard(place_id=ids[0], note="无法证明用户必要条件"))
    elif bad == "duplicate":
        result.reason_revisions.append(revision.model_copy())
    elif bad == "unknown_source":
        revision.evidence_ids = ["invented"]
    elif bad == "cross_source":
        revision.evidence_ids = [cards[1]["sources"][0]["id"]]
    else:
        cards[0]["sources"].append({"id": "r", "kind": "measure_routes"})
        revision.evidence_ids = ["r"]
    with pytest.raises(ValueError):
        validated_revisions(result, cards)
    assert not run.cards


def test_reason_repair_cannot_replace_missing_required_condition_support(tmp_path):
    run, ids = ready_run(tmp_path)
    run.plan.requirements = [ExperienceRequirement(text="必要设施", quote="必要设施")]
    compose = run.model.compose

    def missing(*args):
        draft = compose(*args)
        for card in draft.cards:
            card.requirement_support = []
        return draft

    run.model.compose = missing
    batch = freeze_batch(run, 0, ids, 1)
    worker = BatchWorker(run.model, lambda *args: pytest.fail("No repair without required proof"))
    decision = worker.review(batch, worker.compose(batch))
    assert not decision.payload()["approved_ids"]
    assert (
        run.commit_reviewed_batch(batch, worker.compose(batch), decision, revision=1)["published"]
        == 0
    )


def test_cached_review_reapplies_revision_and_cancelled_commit_does_not_publish(tmp_path):
    run, ids = ready_run(tmp_path)
    calls = []

    def review(conversation, context, cards):
        calls.append(1)
        return reviewer(cards)

    worker = BatchWorker(run.model, review, cache=run.cache)
    batch = freeze_batch(run, 0, ids, 1)
    first = worker.compose(batch)
    worker.review(batch, first)
    repeated = worker.compose(batch)
    decision = worker.review(batch, repeated)
    assert calls == [1] and len(decision.payload()["reason_revisions"]) == 1
    run.cancelled.set()
    with pytest.raises(ValueError):
        run.commit_reviewed_batch(batch, repeated, decision, revision=1)
    assert not run.cards


@pytest.mark.parametrize("coordinated", [False, True])
def test_final_writer_sees_all_actual_facts_and_new_citations_reach_publication(
    tmp_path, coordinated
):
    run, ids = ready_run(tmp_path)
    chosen = []

    def review(cards):
        source = next(s for s in cards[0]["sources"] if s.get("field") == "address")
        chosen.append(source)
        return BatchReview(
            approved_ids=[c["place"]["id"] for c in cards],
            rejected=[],
            reason_revisions=[
                {
                    "place_id": cards[0]["place"]["id"],
                    "reason": CORRECTED,
                    "evidence_ids": [source["id"]],
                }
            ],
        )

    if coordinated:
        batch = freeze_batch(run, 0, ids, 1)
        worker = BatchWorker(run.model, lambda conversation, context, cards: review(cards))
        draft = worker.compose(batch)
        assert all(".f.address" not in key for key in draft.payload()["cards"][0]["evidence_ids"])
        decision = worker.review(batch, draft)
        run.commit_reviewed_batch(batch, draft, decision, revision=1)
    else:
        run.reviewer = review
        run.compose(ids)
    first = next(c for c in run.cards if c["place"]["id"] == ids[0])
    assert first["reason"] == CORRECTED
    assert any(chosen[0]["excerpt"] in s["excerpt"] for s in first["sources"])
    assert all(s["place_id"] == ids[0] for s in first["sources"])
