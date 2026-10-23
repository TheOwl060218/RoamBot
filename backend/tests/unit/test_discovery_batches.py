import copy

import pytest

from test_discovery_workflow import workflow
from roambot.domain.discovery import BatchReview
from roambot.domain.discovery_execution import BatchResult
from roambot.services.discovery_batches import BatchWorker, freeze_batch, prepare_review


def ready_run(tmp_path):
    run = workflow(tmp_path)
    run.plan = run.model.plan()
    run.configure_plan()
    ids = run.retrieve()
    run.facts(ids)
    run.revision = 1
    return run, ids


def worker_for(run, seen):
    def review(conversation, context, cards):
        seen.append(copy.deepcopy(cards))
        return BatchReview(approved_ids=[c["place"]["id"] for c in cards], rejected=[])
    return BatchWorker(run.model, review)


def test_batch_compute_does_not_mutate_run(tmp_path):
    run, ids = ready_run(tmp_path)
    batch = freeze_batch(run, 0, ids, 1)
    before = run.snapshot()
    seen = []
    worker = worker_for(run, seen)
    draft = worker.compose(batch)
    decision = worker.review(batch, draft)
    assert len(seen) == 1 and not run.cards
    after = run.snapshot()
    for field in ("cards", "context", "evidence_count", "issues"):
        assert before[field] == after[field]
    result = run.commit_reviewed_batch(batch, draft, decision, revision=1)
    assert result["published"] == 4
    assert len(seen) == 1, "commit must not invoke the reviewer again"
    assert all(c["reviewed"] for c in run.cards)


def test_review_decision_is_bound_to_exact_draft_and_revision(tmp_path):
    run, ids = ready_run(tmp_path)
    batch = freeze_batch(run, 0, ids, 1)
    worker = worker_for(run, [])
    draft = worker.compose(batch)
    decision = worker.review(batch, draft)
    changed = draft.payload()
    changed["cards"][0]["reason"] += "不能冒用原审查结果。"
    with pytest.raises(ValueError):
        run.commit_reviewed_batch(batch, BatchResult.freeze(batch, changed), decision, revision=1)
    with pytest.raises(ValueError):
        run.commit_reviewed_batch(batch, draft, decision, revision=2)
    assert run.cards == []


@pytest.mark.parametrize("change", ["cancel", "foreign_owner", "evidence", "route_cap"])
def test_commit_rechecks_live_state_and_hard_constraints(tmp_path, change):
    run, ids = ready_run(tmp_path)
    batch = freeze_batch(run, 0, ids, 1)
    worker = worker_for(run, [])
    draft = worker.compose(batch)
    decision = worker.review(batch, draft)
    if change == "cancel":
        run.cancelled.set()
    elif change == "foreign_owner":
        run.scope = "other"
    elif change == "evidence":
        next(e for e in run.evidence.values() if e["kind"] == "search_excerpt")["excerpt"] = "changed"
    else:
        run.context = run.context.model_copy(update={"max_distance_km": 1})
    with pytest.raises((ValueError, RuntimeError)):
        run.commit_reviewed_batch(batch, draft, decision, revision=1)
    assert not run.cards


def test_prepare_review_rejects_cross_place_citations_without_losing_good_cards(tmp_path):
    run, ids = ready_run(tmp_path)
    batch = freeze_batch(run, 0, ids, 1)
    worker = worker_for(run, [])
    draft = worker.compose(batch)
    values = draft.payload()
    values["cards"][0]["evidence_ids"] = values["cards"][1]["evidence_ids"]
    draft = BatchResult.freeze(batch, values)
    review_input = prepare_review(batch, draft).payload()
    assert len(review_input["publish_cards"]) == 3
    assert review_input["rejections"] == ["invalid_evidence"]
    decision = worker.review(batch, draft)
    assert run.commit_reviewed_batch(batch, draft, decision, revision=1)["published"] == 3
