"""A fact batch reaches one model call; it still needs a bound decision ledger."""

import pytest
from test_discovery_workflow import workflow

from roambot.domain.discovery import BatchReview, ExperienceRequirement
from roambot.domain.discovery_assessment import NativeBatchAssessment
from roambot.domain.discovery_execution import BatchResult
from roambot.services.discovery_assessment import decide_assessment
from roambot.services.discovery_batches import BatchWorker, freeze_batch, prepare_review


def observed_decision(context, cards, *, unknown=()):
    criteria = context["user_request"]["criteria"]
    raw = {"assessments": []}
    for card in cards:
        refs = [
            source["id"]
            for source in card["sources"]
            if source["kind"] in {"map_record", "web_page", "search_excerpt"}
        ]
        raw["assessments"].append(
            {
                "place_id": card["place"]["id"],
                "entity_matches": True,
                "broad_intent_matches": True,
                "experience": "休闲体验",
                "grounded_reason": "该地点的真实资料支持本次休闲活动，"
                "可以依据已有场所信息继续了解并作选择。",
                "evidence_ids": refs[:1],
                "note": "实际来源与本次活动相符",
                "checks": [
                    {
                        "requirement": r["index"],
                        "state": "unknown" if r["index"] in unknown else "supported",
                        "evidence_ids": [] if r["index"] in unknown else refs[:1],
                        "note": "待核实必要属性" if r["index"] in unknown else "已有实际依据",
                    }
                    for r in criteria
                    if r.get("scope", "place") == "place"
                ],
            }
        )
    return decide_assessment(NativeBatchAssessment.model_validate(raw), context, cards)


def direct_run(tmp_path):
    run = workflow(tmp_path, message="苏州休闲活动")
    run.model.source_first = True
    plan = run.model.plan()
    plan.requirements = [ExperienceRequirement(text="休闲活动", quote="休闲活动", role="goal")]
    original_plan = run.model.plan
    run.model.calls.clear()

    def planned(*args):
        original_plan(*args)
        return plan

    run.model.plan = planned
    run.model.compose = lambda *args: pytest.fail("No duplicate composition model call")
    run.search.search = lambda *args: pytest.fail("No evidence purchase for a supported activity")
    run.reviewer = lambda cards: observed_decision(run.review_context(), cards)
    return run


def prepared(tmp_path):
    run = direct_run(tmp_path)
    run.plan = run.model.plan()
    run.configure_plan()
    ids = run.retrieve()
    run.revision = 1
    worker = BatchWorker(
        run.model, lambda conversation, context, cards: observed_decision(context, cards)
    )
    return run, ids, worker


def test_direct_pipeline_has_planning_and_bounded_assessments_without_intermediate_copy(tmp_path):
    run = direct_run(tmp_path)
    run.run()
    assert run.status == "completed", run.errors
    assert len(run.cards) == 4 and all(c["reason"] and c["reviewed"] for c in run.cards)
    # Four candidates use two direct batches, with no intermediate composition.
    assert run.metrics["model_calls"] == 3
    assert run.model.calls == ["plan"]
    assert not run.metrics["web_attempts"] and not run.weather.calls
    assert all(card["route"] is None for card in run.cards)


def test_broad_direct_intent_uses_map_facts_without_invented_required_fields_or_web(tmp_path):
    run = direct_run(tmp_path)
    run.plan = run.model.plan()
    run.plan.requirements = []
    run.configure_plan()
    ids = run.retrieve()
    run.process_candidates(ids)
    assert len(run.cards) == 4
    assert all(card["reviewed"] for card in run.cards)
    assert run.request_context()["user_request"]["criteria"] == []
    assert run.metrics["web_attempts"] == 0
    assert not run.errors


def test_frozen_direct_batch_contains_only_ids_and_never_publishes_unwritten_text(tmp_path):
    run, ids, worker = prepared(tmp_path)
    batch = freeze_batch(run, 0, ids, 1)
    draft = worker.compose(batch)
    assert set(draft.payload()) == {"candidate_ids"}
    review_input = prepare_review(batch, draft).payload()
    assert all("reason" not in c and "experience" not in c for c in review_input["publish_cards"])
    assert not run.cards
    decision = worker.review(batch, draft)
    assert decision.payload()["source_assessment"] is not None
    run.commit_reviewed_batch(batch, draft, decision, revision=1)
    assert len(run.cards) == len(ids)


@pytest.mark.parametrize("used", [False, True])
def test_direct_publication_does_not_label_every_retrieved_page_as_recommendation_basis(
    tmp_path, used
):
    run, ids, worker = prepared(tmp_path)
    name = run.places[ids[0]]["name"]
    evidence = run.add_evidence(
        ids[0],
        {
            "kind": "web_page",
            "title": name + "相关资料",
            "url": "https://example.org/retrieved",
            "excerpt": name + "的另一份已检索介绍，不自动证明推荐。",
        },
    )

    def review(conversation, context, cards):
        assert any(
            s["kind"] == "web_page"
            for c in cards
            if c["place"]["id"] == ids[0]
            for s in c["sources"]
        )
        result = observed_decision(context, cards)
        if used:
            observations = NativeBatchAssessment.model_validate(result.source_assessment)
            item = observations.assessments[0]
            fragment = next(
                s["id"]
                for c in cards
                if c["place"]["id"] == item.place_id
                for s in c["sources"]
                if s["kind"] == "web_page"
            )
            item.evidence_ids = [fragment]
            item.checks[0].evidence_ids = [fragment]
            return decide_assessment(observations, context, cards)
        return result

    worker.reviewer = review
    batch = freeze_batch(run, 0, ids, 1)
    draft = worker.compose(batch)
    decision = worker.review(batch, draft)
    run.commit_reviewed_batch(batch, draft, decision, revision=1)
    card = next(c for c in run.cards if c["place"]["id"] == ids[0])
    assert (evidence["id"] in {source["id"] for source in card["sources"]}) is used
    assert any(source["kind"] == "map_record" for source in card["sources"])
    assert evidence["id"] in run.evidence, (
        "Do not delete retrieved evidence from the internal ledger"
    )


@pytest.mark.parametrize(
    "change", ["cancel", "owner", "facts", "distance", "missing_ledger", "changed_copy"]
)
def test_direct_batch_rechecks_state_and_deterministic_decision_before_publication(
    tmp_path, change
):
    run, ids, worker = prepared(tmp_path)
    batch = freeze_batch(run, 0, ids, 1)
    draft = worker.compose(batch)
    decision = worker.review(batch, draft)
    if change == "cancel":
        run.cancelled.set()
    elif change == "owner":
        run.scope = "someone-else"
    elif change == "facts":
        run.places[ids[0]]["address"] = "changed"
    elif change == "distance":
        run.context = run.context.model_copy(update={"max_distance_km": 1})
    else:
        changed = decision.payload()
        if change == "missing_ledger":
            changed["source_assessment"] = None
        else:
            changed["reason_revisions"][0]["reason"] = (
                "未经过原证据判断的新说法，不得借用旧批准直接对用户发布。"
            )
        decision = BatchResult.freeze(decision.batch, changed)
    with pytest.raises((ValueError, RuntimeError)):
        run.commit_reviewed_batch(batch, draft, decision, revision=1)
    assert not run.cards


def test_direct_approval_needs_real_observations_not_just_good_sounding_copy(tmp_path):
    run, ids, _ = prepared(tmp_path)
    worker = BatchWorker(
        run.model,
        lambda conversation, context, cards: BatchReview(
            approved_ids=[c["place"]["id"] for c in cards], rejected=[]
        ),
    )
    batch = freeze_batch(run, 0, ids, 1)
    with pytest.raises(ValueError, match="逐项观察"):
        worker.review(batch, worker.compose(batch))
    assert not run.cards


def test_direct_required_unknown_is_rejected_and_still_targets_only_the_missing_fact(tmp_path):
    run, ids, _ = prepared(tmp_path)
    run.plan.requirements.append(ExperienceRequirement(text="必要设施", quote="必要设施"))
    worker = BatchWorker(
        run.model,
        lambda conversation, context, cards: observed_decision(context, cards, unknown={2}),
    )
    batch = freeze_batch(run, 0, ids, 1)
    draft = worker.compose(batch)
    decision = worker.review(batch, draft)
    assert not decision.payload()["approved_ids"]
    assert {n["requirement"] for n in decision.payload()["evidence_needs"]} == {2}
    assert run.commit_reviewed_batch(batch, draft, decision, revision=1)["published"] == 0


def test_direct_empty_batch_is_a_noop_without_a_provider_call(tmp_path):
    run, _, _ = prepared(tmp_path)
    run.reviewer = lambda cards: pytest.fail("No model call for an empty batch")
    assert run.assess_candidates([]) == 0
    assert not run.cards


def test_direct_payload_cannot_add_omit_or_duplicate_candidates(tmp_path):
    run, ids, worker = prepared(tmp_path)
    batch = freeze_batch(run, 0, ids, 1)
    for changed in (ids[:-1], ids + [ids[0]], ids[:-1] + ["invented"]):
        with pytest.raises(ValueError):
            worker.review(batch, BatchResult.freeze(batch, {"candidate_ids": changed}))


def test_observed_vote_cannot_upgrade_a_map_category_into_required_facility_proof(tmp_path):
    run, ids, _ = prepared(tmp_path)
    run.plan.requirements = [ExperienceRequirement(text="必要设施", quote="必要设施")]
    batch = freeze_batch(run, 0, ids, 1)
    data = prepare_review(batch, BatchWorker(run.model, None).compose(batch)).payload()
    for card in data["cards"]:
        card["sources"] = [s for s in card["sources"] if s.get("field") == "map_type"]
    result = observed_decision(data["context"], data["cards"])
    assert not result.approved_ids
    assert {n.requirement for n in result.evidence_needs} == {1}


def test_direct_publication_keeps_assessed_order_within_one_activity(tmp_path):
    run, ids, _ = prepared(tmp_path)
    worker = BatchWorker(
        run.model,
        lambda conversation, context, cards: observed_decision(context, list(reversed(cards))),
    )
    batch = freeze_batch(run, 0, ids, 1)
    draft = worker.compose(batch)
    decision = worker.review(batch, draft)
    run.commit_reviewed_batch(batch, draft, decision, revision=1)
    assert [c["place"]["id"] for c in run.cards] == list(reversed(ids))


def test_coordinated_direct_pipeline_also_skips_duplicate_composition(tmp_path):
    from test_discovery_orchestrator import EightModel, build

    model = EightModel()
    model.source_first = True
    plan = model.plan()
    plan.requirements = [ExperienceRequirement(text="不同体验", quote="不同体验", role="goal")]
    model.calls.clear()
    original_plan = model.plan

    def planned(*args):
        original_plan(*args)
        return plan

    model.plan = planned
    model.compose = lambda *args: pytest.fail("No composition call in the coordinated direct flow")
    run = build(
        tmp_path,
        model=model,
        reviewer=lambda conversation, context, cards: observed_decision(context, cards),
    )
    run.reviewer = lambda cards: observed_decision(run.review_context(), cards)
    run.run()
    assert run.status == "completed", run.errors
    # One planning call plus 2/3/3 direct assessments, without composition calls.
    assert len(run.cards) == 8 and run.metrics["model_calls"] == 4
    assert model.calls == ["plan"]


def test_parallel_direct_assessments_finalize_the_real_complete_collection_once(tmp_path):
    import threading

    from test_discovery_orchestrator import EightModel, build

    from roambot.domain.discovery_assessment import CollectionReview

    first_entered, tail_entered = threading.Event(), threading.Event()
    model = EightModel()
    model.source_first = True
    plan = model.plan()
    plan.requirements = [
        ExperienceRequirement(text="不同体验", quote="不同体验", role="goal"),
        ExperienceRequirement(text="整组要求", quote="不同体验", scope="collection"),
    ]
    model.calls.clear()
    model.plan = lambda *args: plan
    model.compose = lambda *args: pytest.fail("No duplicate composition model call")
    whole_lists = []

    def review(conversation, context, cards):
        if len(cards) == 2:
            first_entered.set()
            assert tail_entered.wait(2), "Native tail assessment must overlap the first"
        else:
            assert first_entered.wait(2)
            tail_entered.set()
        return observed_decision(context, cards)

    def final(conversation, context, cards):
        ids = [c["place"]["id"] for c in cards]
        whole_lists.append(ids)
        assert len(ids) == 8 and run.gate.active == 1
        return CollectionReview(
            collection_assessments=[
                {"requirement": 2, "satisfied": True, "place_ids": ids, "note": "判断完整实际列表"}
            ]
        )

    model.assess_collection = final
    run = build(tmp_path, model=model, reviewer=review)
    run.reviewer = lambda cards: review(run.turns, run.review_context(), cards)
    ordered_ids = []
    retrieve = run.retrieve

    def capture_retrieval():
        ids = retrieve()
        ordered_ids.extend(ids)
        return ids

    run.retrieve = capture_retrieval
    run.run()
    assert run.status == "completed", run.errors
    assert len(ordered_ids) == 8 and set(ordered_ids) == {f"amap:{i}" for i in range(1, 9)}
    assert [c["place"]["id"] for c in run.cards] == ordered_ids
    assert whole_lists == [[c["place"]["id"] for c in run.cards]]
    assert run.metrics["model_calls"] == 5 and not run.collection_gaps()
