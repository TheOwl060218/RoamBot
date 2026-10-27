"""Activity suitability, verifiable conditions and list requirements are distinct."""

import json
from types import SimpleNamespace

import pytest
from test_discovery_workflow import workflow

from roambot.domain.discovery import BatchReview, ExperienceRequirement, RequirementSupport
from roambot.providers.discovery import review_batch
from roambot.services.discovery_batches import BatchWorker, freeze_batch, prepare_review
from roambot.services.discovery_criteria import criterion_view, supported_criteria


def requirements():
    return [
        ExperienceRequirement(text="休闲活动", quote="休闲活动", role="goal"),
        ExperienceRequirement(text="指定设施", quote="指定设施"),
        ExperienceRequirement(text="不同体验", quote="不同体验", role="goal", scope="collection"),
    ]


def test_goal_and_collection_do_not_require_literal_factual_proof_but_facilities_do():
    criteria = criterion_view(requirements())
    proof = {
        "p": {
            "evidence_id": "source",
            "place_id": "actual",
            "kind": "web_page",
            "excerpt": "具体设施的实际介绍",
        }
    }
    support = [RequirementSupport(requirement=2, passage_ids=["p"])]
    result = supported_criteria(criteria, support, proof, "actual")
    assert result["required_experiences"] == [
        {"requirement": "指定设施", "quotes": ["具体设施的实际介绍"], "map_field": None}
    ]
    assert supported_criteria(criteria, [], proof, "actual") is None
    proof["p"].update(kind="map_record", field="map_type")
    assert supported_criteria(criteria, support, proof, "actual") is None


@pytest.mark.parametrize("requirement", [1, 3])
def test_optional_goal_or_collection_citations_still_cannot_be_unknown_or_cross_venue(requirement):
    criteria = criterion_view([requirements()[i] for i in (0, 2)])
    index = 1 if requirement == 1 else 2
    assert supported_criteria(criteria, [], {}, "actual") is not None
    support = [RequirementSupport(requirement=index, passage_ids=["invented"])]
    assert supported_criteria(criteria, support, {}, "actual") is None
    assert (
        supported_criteria(criteria, support, {"invented": {"place_id": "other"}}, "actual") is None
    )


@pytest.mark.parametrize("coordinated", [False, True])
def test_goal_only_cards_are_reviewed_against_original_message_without_auto_facility_search(
    tmp_path, coordinated
):
    run = workflow(tmp_path, message="休闲活动，整组不同体验")
    run.plan = run.model.plan()
    run.plan.requirements = [requirements()[0], requirements()[2]]
    run.configure_plan()
    run.search.search = lambda query: pytest.fail(
        "No automatic facility proof for an activity goal"
    )
    ids = run.retrieve()
    observed = []

    def review(cards):
        from roambot.domain.discovery import BatchReview

        observed.extend(cards)
        return BatchReview(
            approved_ids=[],
            rejected=[
                {"place_id": c["place"]["id"], "note": "事实虽存在，但与用户完整活动不符"}
                for c in cards
            ],
        )

    if coordinated:
        worker = BatchWorker(run.model, lambda conversation, context, cards: review(cards))
        batch = freeze_batch(run, 0, ids, 1)
        draft = worker.compose(batch)
        prepared = prepare_review(batch, draft).payload()
        assert prepared["context"]["user_request"]["messages"] == [run.body.message]
        assert prepared["cards"] and not prepared["rejections"]
        result = worker.review(batch, draft).payload()
        assert not result["approved_ids"]
    else:
        run.reviewer = review
        run.compose(ids)
        assert not run.cards
    assert observed and all(not c["required_experiences"] for c in observed)
    run.ensure_core_evidence(ids, force=True)
    assert not run.pending_evidence_needs() and not run.metrics["web_attempts"]


def test_collection_and_optional_preferences_cannot_queue_mandatory_research(tmp_path):
    run = workflow(tmp_path, message="休闲活动，整组不同体验，有指定设施更好")
    run.plan = run.model.plan()
    run.plan.requirements = [
        requirements()[0],
        requirements()[2],
        ExperienceRequirement(text="指定设施", quote="指定设施", importance="preferred"),
    ]
    run.configure_plan()
    ids = run.retrieve()
    run.record_evidence_needs(
        [
            {"place_id": ids[0], "query": "整组要求", "requirement": 2},
            {"place_id": ids[1], "query": "偏好条件", "requirement": 3},
        ],
        ids,
    )
    assert not run.pending_evidence_needs()
    assert "不同体验" not in run.selection_queries()


def test_goal_protocol_cannot_silently_bypass_independent_suitability_review(tmp_path):
    run = workflow(tmp_path, message="休闲活动")
    run.plan = run.model.plan()
    run.plan.requirements = [requirements()[0]]
    run.configure_plan()
    ids = run.retrieve()
    run.reviewer = None
    run.review = None
    with pytest.raises(ValueError, match="独立适配审查"):
        run.compose(ids)
    assert not run.cards


@pytest.mark.parametrize("assessed", [False, True])
def test_required_collection_goal_needs_an_actual_whole_list_assessment(tmp_path, assessed):
    run = workflow(tmp_path, message="休闲活动，整组不同体验")
    plan = run.model.plan()
    plan.requirements = [requirements()[0], requirements()[2]]
    run.model.plan = lambda *args: plan

    def review(cards):
        ids = [c["place"]["id"] for c in cards]
        return BatchReview(
            approved_ids=ids,
            rejected=[],
            collection_assessments=[
                {
                    "requirement": 2,
                    "satisfied": True,
                    "place_ids": ids,
                    "note": "各候选的实际活动不同",
                }
            ]
            if assessed and ids
            else [],
        )

    run.reviewer = review
    run.run()
    assert run.cards, "A list-level gap must not discard individually correct places"
    assert run.status == ("completed" if assessed else "partial")
    assert run.metrics["unmet_collection_requirements"] == ([] if assessed else [2])


def test_collection_assessment_cannot_reference_wrong_condition_or_unapproved_members(tmp_path):
    run = workflow(tmp_path)
    run.plan = run.model.plan()
    run.plan.requirements = requirements()
    for index, ids in ((1, ["real"]), (3, ["invented"]), (3, ["real", "real"])):
        result = BatchReview(
            approved_ids=["real"],
            rejected=[],
            collection_assessments=[
                {"requirement": index, "satisfied": True, "place_ids": ids, "note": "假通过"}
            ],
        )
        with pytest.raises(ValueError, match="整组判断"):
            run.record_collection_review(result, set())
        assert not run.collection_assessments


def test_older_parallel_prefix_cannot_certify_the_current_collection(tmp_path):
    run = workflow(tmp_path)
    run.plan = run.model.plan()
    run.plan.requirements = requirements()
    run.cards = [{"place": {"id": "newly-published"}}]
    result = BatchReview(
        approved_ids=["real"],
        rejected=[],
        collection_assessments=[
            {"requirement": 3, "satisfied": True, "place_ids": ["real"], "note": "仅判断旧快照"}
        ],
    )
    run.record_collection_review(result, set())
    assert run.collection_gaps() == [3]


@pytest.mark.parametrize("mutate", [False, True])
def test_final_collection_uses_all_published_cards_and_rejects_a_changed_snapshot(tmp_path, mutate):
    from roambot.domain.discovery_assessment import CollectionReview

    run = workflow(tmp_path)
    run.plan = run.model.plan()
    run.plan.requirements = requirements()
    run.model.source_first = True
    run.cards = [{"place": {"id": key}} for key in ("first", "last")]
    observed = []

    def evaluate(conversation, context, cards):
        observed.extend(c["place"]["id"] for c in cards)
        if mutate:
            run.cards.append({"place": {"id": "new"}})
        return CollectionReview(
            collection_assessments=[
                {
                    "requirement": 3,
                    "satisfied": True,
                    "place_ids": observed,
                    "note": "完整结果满足整组要求",
                }
            ]
        )

    run.model.assess_collection = evaluate
    if mutate:
        with pytest.raises(ValueError, match="已变化"):
            run.finalize_collection()
        assert run.collection_gaps() == [3]
    else:
        run.finalize_collection()
        run.finalize_collection()
        assert run.collection_gaps() == []
        assert run.metrics["model_calls"] == 1
    assert observed == ["first", "last"]


def test_composer_and_soft_only_review_do_not_receive_retrieval_guesses_as_constraints(tmp_path):
    run = workflow(tmp_path)
    run.plan = run.model.plan()
    run.plan.requirements = [
        ExperienceRequirement(text="附加偏好", quote="附加偏好", importance="preferred")
    ]
    from roambot.domain.discovery import RetrievalDirection

    run.plan.directions = [
        RetrievalDirection(experience="检索猜测", map_query="检索词", web_query="检索词")
    ]
    assert "retrieval_hypotheses" not in run.request_context()
    sent = []

    def post_json(**kwargs):
        sent.append(kwargs["json_body"])
        return {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "assess_batch",
                                    "arguments": json.dumps({"assessments": []}),
                                }
                            }
                        ]
                    },
                }
            ]
        }

    provider = SimpleNamespace(
        _http=SimpleNamespace(post_json=post_json),
        _model="same",
        _key="not-real",
        _enable_thinking=False,
    )
    original = run.review_context() | {"retrieval_hypotheses": ["应移除的猜测"]}
    review_batch(provider, run.turns, original, [])
    actual = json.loads(sent[0]["messages"][1]["content"])["context"]
    assert (
        not {"retrieval_hypotheses", "requested_directions", "covered_direction_indices"}
        & actual.keys()
    )
    assert actual["user_request"] == original["user_request"]
    assert "requested_directions" in original, "Review must not mutate shared orchestration state"
