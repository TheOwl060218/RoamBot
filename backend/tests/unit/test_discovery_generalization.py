"""General contracts: no production vocabulary of example requests or place types."""

import copy

import pytest
from test_discovery_workflow import workflow

from roambot.domain.discovery import (
    BatchReview,
    EvidenceNeed,
    ExperienceRequirement,
    GroundedBatch,
    RequirementSupport,
    RetrievalPlan,
    SearchContext,
    VenueSelection,
)
from roambot.domain.discovery_execution import BatchResult
from roambot.services.discovery_batches import BatchWorker, freeze_batch, prepare_review
from roambot.services.discovery_selection import select_places, select_sources


def test_public_hits_do_not_hide_current_per_query_map_candidates(tmp_path):
    from types import SimpleNamespace

    run = workflow(tmp_path, message="苏州参观")
    run.plan = RetrievalPlan(
        context=SearchContext(region="苏州"),
        goal="参观",
        map_queries=["场所"],
        requirements=[ExperienceRequirement(text="参观", quote="参观", role="goal")],
    )
    run.configure_plan()
    fresh = run.maps.search("场所", "苏州", None, None)
    cached = []
    for index, place in enumerate(fresh):
        place = copy.deepcopy(place)
        place.update(id=f"amap:cached-{index}", name="缓存" + place["name"])
        cached.append({"place": place, "sources": []})
    assert len(cached) >= 4, "Exercise the dense-public-cache path"
    run.knowledge = SimpleNamespace(
        find=lambda *args, **kwargs: cached, remember=lambda *args: None
    )
    selected = run.retrieve()
    assert run.metrics["public_place_hits"] >= 4
    assert {place["id"] for place in fresh} <= set(selected)
    assert any(place["place"]["id"] in selected for place in cached)


@pytest.mark.parametrize("batch_mode", [False, True])
def test_unproven_preference_is_not_a_missing_hard_condition(tmp_path, batch_mode):
    run = workflow(tmp_path, message="可以参观，坐着更好")
    run.plan = RetrievalPlan(
        context=SearchContext(region="苏州"),
        goal="可以参观，坐着更好",
        map_queries=["活动场所"],
        web_queries=["活动资料"],
        requirements=[
            ExperienceRequirement(text="可参观", quote="可以参观"),
            ExperienceRequirement(text="可坐下", quote="坐着更好", importance="preferred"),
        ],
    )
    run.configure_plan()
    ids = run.retrieve()
    original = run.model.compose

    def compose(*args):
        batch = original(*args)
        for card in batch.cards:
            card.requirement_support = card.requirement_support[:1]
        return batch

    run.model.compose = compose
    if batch_mode:
        frozen = freeze_batch(run, 0, ids, 1)
        context = frozen.payload()["context"]
        assert context["requirements"][1]["importance"] == "preferred"
        draft = BatchResult.freeze(
            frozen,
            compose(run.turns, run.plan.goal, context, frozen.payload()["candidates"]).model_dump(),
        )
        reviewed = prepare_review(frozen, draft).payload()
        assert len(reviewed["publish_cards"]) == 4
        assert all(len(c["required_experiences"]) == 1 for c in reviewed["cards"])
        assert all(c["preferred_experiences"] == [] for c in reviewed["cards"])
    else:
        run.compose(ids)
        assert len(run.cards) == 4
        assert not run.errors
        assert all(len(c["required_experiences"]) == 1 for c in run.review_inputs.values())


@pytest.mark.parametrize("indices", [[], [2], [1, 1], [1, 3]])
def test_preferences_never_allow_missing_required_or_duplicate_unknown_support(tmp_path, indices):
    run = workflow(tmp_path, message="必须可参观，坐着更好")
    run.plan = RetrievalPlan(
        context=SearchContext(region="苏州"),
        goal="可以参观，坐着更好",
        map_queries=["活动场所"],
        web_queries=["活动资料"],
        requirements=[
            ExperienceRequirement(text="可参观", quote="可参观"),
            ExperienceRequirement(text="可坐下", quote="坐着更好", importance="preferred"),
        ],
    )
    run.configure_plan()
    ids = run.retrieve()
    batch = freeze_batch(run, 0, ids, 1)
    proposed = run.model.compose(
        run.turns, run.plan.goal, batch.payload()["context"], batch.payload()["candidates"]
    )
    for card in proposed.cards:
        passage = card.requirement_support[0].passage_ids
        card.requirement_support = [
            RequirementSupport(requirement=i, passage_ids=passage) for i in indices
        ]
    # Revalidate to ensure test substitutions still obey the public typed contract.
    draft = BatchResult.freeze(
        batch, GroundedBatch.model_validate(proposed.model_dump()).model_dump()
    )
    result = prepare_review(batch, draft).payload()
    assert not result["publish_cards"] and len(result["rejections"]) == 4


@pytest.mark.parametrize("terms", [("天文", "观测"), ("摄影", "展览"), ("手工", "体验")])
def test_evidence_window_selects_relevant_tail_and_preserves_original_sources(terms):
    sources = [
        {"title": "普通资料", "excerpt": "重复内容" * 40, "url": f"https://same.example.org/{i}"}
        for i in range(25)
    ]
    focus = " ".join(terms)
    target = {
        "title": focus,
        "excerpt": focus + "的具体公开资料",
        "url": "https://official.example.net/detail",
    }
    sources.append(target)
    before = copy.deepcopy(sources)
    selected = select_sources(sources, [focus], limit=4)
    assert target in selected and len(selected) == 4
    assert sources == before
    assert all(any(s is original for original in sources) for s in selected)
    assert len({s["url"] for s in select_sources(sources + [target], [focus], limit=50)}) == 26


def test_nomination_place_window_does_not_crowd_out_distinct_map_leads_or_use_rating():
    places = [
        {
            "id": str(i),
            "name": "相近场所" + str(i),
            "city": "同城",
            "address": "地址",
            "map_type": "provider-type-a",
            "facts": {"rating": "5"},
        }
        for i in range(60)
    ]
    places += [
        {
            "id": "other",
            "name": "另一种活动场所",
            "city": "同城",
            "address": "地址",
            "map_type": "provider-type-b",
            "facts": {"rating": "1"},
        }
    ]
    selected = select_places(places, [], limit=8)
    assert any(p["id"] == "other" for p in selected)
    assert len(selected) == 8
    assert places[0] == selected[0]


def test_verified_candidate_gap_targets_real_place_and_does_not_become_a_user_requirement(tmp_path):
    run = workflow(tmp_path)
    run.plan = run.model.plan()
    run.configure_plan()
    ids = run.retrieve()
    before = copy.deepcopy(run.plan.requirements)
    need = EvidenceNeed(place_id=ids[1], query="具体使用条件 当前公开介绍")
    run.record_evidence_needs([need], ids)
    # Duplicate needs and invented place IDs cannot create additional work.
    run.record_evidence_needs([need, EvidenceNeed(place_id="invented", query="随意搜索")], ids)
    run.evidence_query = "旧的宽泛补查"
    queries = []
    run.web_search = lambda query: queries.append(query) or []
    run.supplement()
    assert queries == [run.places[ids[1]]["name"] + " 具体使用条件 当前公开介绍"]
    assert run.plan.requirements == before
    assert len(run.evidence_needs) == 1


def test_empty_composition_records_missing_fact_without_publishing_or_faking_completion(tmp_path):
    run = workflow(tmp_path)
    run.plan = run.model.plan()
    run.configure_plan()
    ids = run.retrieve()
    run.model.compose = lambda *args: GroundedBatch(
        cards=[], evidence_needs=[EvidenceNeed(place_id=ids[0], query="具体活动的使用条件")]
    )
    assert run.compose(ids) == 0
    assert not run.cards
    assert run.evidence_needs[0].place_id == ids[0]
    assert run.context.start_date is None


def test_candidate_nomination_receives_user_criteria_separately_from_search_hypotheses(tmp_path):
    run = workflow(tmp_path, message="能参观，坐着更好")
    run.plan = RetrievalPlan(
        context=SearchContext(region="苏州"),
        goal="参观并休息",
        requirements=[
            ExperienceRequirement(text="能参观", quote="能参观"),
            ExperienceRequirement(text="可坐下", quote="坐着更好", importance="preferred"),
        ],
        directions=[{"experience": "本轮检索假设", "map_query": "活动场所", "web_query": "资料"}],
    )
    run.configure_plan()
    seen = []

    def nominate(conversation, goal, context, sources, places):
        seen.append(context)
        return VenueSelection(venues=[])

    run.model.nominate = nominate
    run.nominate()
    assert seen[0]["user_request"]["criteria"][1]["importance"] == "preferred"
    assert seen[0]["retrieval_hypotheses"][0]["experience"] == "本轮检索假设"
    assert "本轮检索假设" not in str(seen[0]["user_request"])


@pytest.mark.parametrize("cancel", [False, True])
def test_frozen_missing_evidence_commits_only_for_current_uncancelled_run(tmp_path, cancel):
    run = workflow(tmp_path)
    run.plan = run.model.plan()
    run.configure_plan()
    ids = run.retrieve()
    run.revision = 1
    batch = freeze_batch(run, 0, ids, 1)
    draft = BatchResult.freeze(
        batch,
        {
            "cards": [],
            "evidence_needs": [
                {"place_id": ids[0], "query": "开放使用条件"},
                {"place_id": "invented", "query": "无关查询"},
            ],
        },
    )
    worker = BatchWorker(run.model, lambda *args: pytest.fail("No cards to review"))
    decision = worker.review(batch, draft)
    assert run.evidence_needs == [], "workers must not mutate coordinator state"
    if cancel:
        run.cancelled.set()
        with pytest.raises((ValueError, RuntimeError)):
            run.commit_reviewed_batch(batch, draft, decision, revision=1)
        assert run.evidence_needs == []
    else:
        run.commit_reviewed_batch(batch, draft, decision, revision=1)
        assert [n.place_id for n in run.evidence_needs] == [ids[0]]
        assert not run.cards


def test_review_gap_must_belong_to_actual_batch_and_does_not_modify_criteria(tmp_path):
    run = workflow(tmp_path)
    run.plan = run.model.plan()
    run.configure_plan()
    ids = run.retrieve()
    run.revision = 1
    before = copy.deepcopy(run.plan)
    batch = freeze_batch(run, 0, ids, 1)

    def review(*args):
        return BatchReview(
            approved_ids=ids,
            rejected=[],
            evidence_needs=[
                EvidenceNeed(place_id=ids[0], query="使用时间"),
                EvidenceNeed(place_id="foreign", query="别人的待查信息"),
            ],
        )

    worker = BatchWorker(run.model, review)
    draft = worker.compose(batch)
    decision = worker.review(batch, draft)
    assert not run.evidence_needs
    run.commit_reviewed_batch(batch, draft, decision, revision=1)
    assert [n.place_id for n in run.evidence_needs] == [ids[0]]
    assert run.plan == before


def test_downstream_goal_uses_actual_user_message_even_when_planner_summary_is_wrong(tmp_path):
    message = "参观一下，有座位更好"
    run = workflow(tmp_path, message=message)
    run.plan = run.model.plan()
    run.plan.goal = "必须有座位才允许参观"
    run.configure_plan()
    seen = []
    nominate = run.model.nominate
    compose = run.model.compose

    def inspect_nomination(conversation, goal, *args):
        seen.append(goal)
        return nominate(conversation, goal, *args)

    def inspect_composition(conversation, goal, *args):
        seen.append(goal)
        return compose(conversation, goal, *args)

    run.model.nominate = inspect_nomination
    run.model.compose = inspect_composition
    ids = run.retrieve()
    run.compose(ids)
    assert seen == [message, message]
    assert freeze_batch(run, 0, ids, 1).payload()["goal"] == message
    assert run.plan.goal == "必须有座位才允许参观", "do not mask diagnostic evidence"
