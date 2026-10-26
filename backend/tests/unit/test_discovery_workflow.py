import copy
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pytest
from test_discovery import Maps, Weather, Web

from roambot.domain.discovery import (
    BatchReview,
    DiscoveryRequest,
    ExperienceRequirement,
    GroundedBatch,
    RecommendationBatch,
    RetrievalPlan,
    SearchContext,
    VenueSelection,
)
from roambot.persistence.discovery_cache import DiscoveryCache
from roambot.providers.protocols import ProviderError
from roambot.services.discovery_workflow import DiscoveryWorkflow


class Model:
    def __init__(self, context=None):
        self.context = context or SearchContext(region="苏州")
        self.calls = []

    def plan(self, *args):
        self.calls.append("plan")
        return RetrievalPlan(
            context=self.context,
            goal="这次希望换换心情",
            web_queries=["活动"],
            map_queries=["书店 湖边 展览"],
        )

    def nominate(self, *args):
        self.calls.append("nominate")
        return VenueSelection(
            venues=[
                {"name": name, "place_id": f"amap:{i}"}
                for i, name in enumerate(("独立书店", "湖边绿地", "城市展览", "另一家书店"), 1)
            ]
        )

    def compose(self, conversation, goal, context, candidates):
        self.calls.append("compose")

        def citation(candidate):
            web = next(
                (
                    s["id"]
                    for s in candidate["sources"]
                    if s["kind"] in {"web_page", "search_excerpt"}
                ),
                None,
            )
            return web or next(
                s["id"] for s in candidate["sources"] if s.get("field") == "name_and_type"
            )

        return GroundedBatch(
            cards=[
                {
                    "place_id": c["place"]["id"],
                    "experience": "翻书" if c["place"]["id"] in {"amap:1", "amap:4"} else "散步",
                    "reason": "本次推荐依据实际检索到的场地资料，"
                    "具体地点与出处已经核实，可以继续查看详情。",
                    "evidence_ids": [citation(c)],
                    "requirement_support": [
                        {
                            "requirement": r["index"],
                            "passage_ids": [citation(c)],
                        }
                        for r in context.get("requirements", [])
                    ],
                }
                for c in candidates
            ]
        )


class EvidenceWeb(Web):
    def search(self, query):
        return [
            {
                "title": name + "介绍",
                "url": f"https://example.org/venue/{i}",
                "excerpt": name + "有明确可供参观的空间。这是该场地的公开资料正文。",
                "kind": "search_excerpt",
            }
            for i, name in enumerate(("独立书店", "湖边绿地", "城市展览", "另一家书店"), 1)
        ]


def workflow(tmp_path, *, model=None, previous=None, scope="one", message="苏州看看"):
    return DiscoveryWorkflow(
        DiscoveryRequest(message=message),
        Maps(),
        Weather(),
        EvidenceWeb(),
        model or Model(),
        DiscoveryCache(tmp_path / "facts.sqlite3"),
        scope,
        previous,
        source="demo",
        reviewer=lambda cards: BatchReview(
            approved_ids=[c["place"]["id"] for c in cards], rejected=[]
        ),
    )


def test_fixed_pipeline_produces_grounded_stable_interleaved_cards_without_optional_facts(tmp_path):
    run = workflow(tmp_path)
    run.run()
    assert run.status == "completed"
    assert [c["place"]["id"] for c in run.cards] == ["amap:1", "amap:2", "amap:4", "amap:3"]
    assert run.metrics["model_calls"] == 4
    assert run.model.calls == ["plan", "nominate", "compose"]
    assert not run.weather.calls
    assert all(c["route"] is None and c["weather"] is None for c in run.cards)
    assert run.first_batch_ms is not None


@pytest.mark.parametrize("message", ["收藏第二个再查看位置", "关闭地图", "选择前两个进行比较"])
def test_business_intent_hands_off_without_search_or_optional_facts(tmp_path, message):
    class BusinessModel(Model):
        def plan(self, *args):
            self.calls.append("plan")
            return RetrievalPlan(intent="business", context=SearchContext(), goal=message)

    run = workflow(tmp_path, model=BusinessModel(), message=message)
    run.run()
    result = run.snapshot()
    assert result["intent"] == "business"
    assert result["status"] == "completed"
    assert result["reply"] == ""  # No claim that the business task has executed.
    assert result["cards"] == []
    assert run.model.calls == ["plan"]
    assert not run.weather.calls
    assert result["metrics"]["web_attempts"] == 0
    assert result["metrics"]["search_credits"] == 0
    assert result["candidate_count"] == 0


def test_actual_route_cap_filters_before_model_composition(tmp_path):
    model = Model(
        SearchContext(
            origin="苏州站",
            origin_quote="从苏州站出发",
            max_distance_km=5,
            distance_quote="5公里内",
        )
    )
    run = workflow(tmp_path, model=model, message="从苏州站出发，5公里内看看")
    run.run()
    assert run.cards
    assert "amap:4" not in [c["place"]["id"] for c in run.cards]
    assert all(c["route"]["distance_km"] <= 5 for c in run.cards)
    assert not run.weather.calls


def test_repeat_query_reuses_facts_but_does_not_cache_personalized_model_replies(tmp_path):
    first = workflow(tmp_path)
    first.run()
    second = workflow(tmp_path)
    second.run()
    assert second.cards and second.maps.calls == []
    assert second.metrics["cache_hits"] == 4
    assert second.model.calls == ["compose"]
    third = workflow(tmp_path, scope="different-session")
    third.run()
    assert third.metrics["cache_hits"] == 0
    assert third.maps.calls


def test_date_only_followup_retains_venues_and_origin_and_recomputes_weather(tmp_path):
    first = workflow(
        tmp_path,
        model=Model(SearchContext(origin="苏州站", origin_quote="苏州站")),
        message="苏州站出发",
    )
    first.run()
    start = date.today() + timedelta(days=1)
    model = Model()
    model.plan = lambda *args: RetrievalPlan(
        context=SearchContext(
            origin=None, region=None, start_date=start, end_date=start, date_quote="明天"
        ),
        goal="还是那些地方，改成明天",
        reuse_previous=True,
    )
    run = workflow(tmp_path, model=model, previous=first.snapshot(), message="改成明天")
    run.run()
    assert run.cards
    assert run.context.origin == "苏州站"
    assert run.context.start_date == start
    assert run.weather.calls
    assert not [call for call in run.maps.calls if call[0] in {"route", "search"}]
    assert model.calls == ["compose"]


def test_cancellation_after_planning_starts_no_external_retrieval(tmp_path):
    run = workflow(tmp_path)
    original = run.model.plan

    def cancel(*args):
        run.cancelled.set()
        return original(*args)

    run.model.plan = cancel
    run.run()
    assert run.status == "cancelled"
    assert not run.maps.calls and not run.cards


def test_unknown_model_ids_and_cross_place_evidence_cannot_be_published(tmp_path):
    run = workflow(tmp_path)
    run.model.compose = lambda *args: RecommendationBatch(
        cards=[
            {
                "place_id": "amap:1",
                "experience": "翻书",
                "reason": "这是一条试图引用其他地点资料的推荐理由，不能进入用户结果。",
                "evidence_ids": [args[-1][1]["sources"][0]["id"]],
            }
        ]
    )
    run.run()
    assert run.status == "failed" and not run.cards


def test_timeout_does_not_trigger_another_model_roundtrip(tmp_path):
    run = workflow(tmp_path)
    calls = []

    def timeout(*args):
        calls.append(1)
        raise ProviderError("timeout", "timeout")

    run.model.plan = timeout
    run.run()
    assert len(calls) == 1 and run.status == "failed"
    assert run.metrics["model_calls"] == 1


def test_cache_single_flight_ttl_scoping_and_failed_load_are_not_cached(tmp_path):
    now = [10]
    cache = DiscoveryCache(tmp_path / "cache.sqlite3", clock=lambda: now[0])
    entered, release = threading.Event(), threading.Event()
    calls = []

    def load():
        calls.append(1)
        entered.set()
        assert release.wait(2)
        return {"fact": "真实地点资料"}

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(cache.get_or_load, "a", "web", "query", 5, load)
        assert entered.wait(2)
        second = pool.submit(cache.get_or_load, "a", "web", "query", 5, load)
        release.set()
        values = [first.result(), second.result()]
    assert len(calls) == 1 and sorted(hit for _, hit in values) == [False, True]
    now[0] = 20
    _, hit = cache.get_or_load("a", "web", "query", 5, lambda: {"new": True})
    assert not hit
    _, hit = cache.get_or_load("b", "web", "query", 5, lambda: {"other": True})
    assert not hit
    with pytest.raises(ValueError):
        cache.get_or_load("a", "web", "bad", 5, lambda: (_ for _ in ()).throw(ValueError()))
    assert cache.get_or_load("a", "web", "bad", 5, lambda: {"recovered": True})[0]


def test_changed_request_invalidates_short_lived_plan_and_nomination(tmp_path):
    first = workflow(tmp_path)
    first.run()
    changed = workflow(tmp_path, message="这次想找不同于刚才的地方")
    changed.run()
    assert changed.model.calls == ["plan", "nominate", "compose"]


def test_radius_without_center_requests_only_location_not_full_form(tmp_path):
    run = workflow(
        tmp_path,
        model=Model(SearchContext(region="苏州", max_distance_km=5, distance_quote="5公里内")),
        message="苏州，5公里内看看",
    )
    run.run()
    assert run.request_location and not run.maps.calls
    assert run.context.start_date is None


def test_nearby_evidence_does_not_invent_a_hard_distance_limit(tmp_path):
    run = workflow(tmp_path, message="苏州附近放松一下的地方")
    run.plan = RetrievalPlan(
        context=SearchContext(region="苏州"), goal="苏州附近放松一下的地方", nearby_quote="附近"
    )
    run.configure_plan()
    assert run.context.max_distance_km is None
    assert run.context.distance_quote is None
    assert run.context.origin is None and not run.maps.calls


def test_destination_only_does_not_inherit_nearby_default_or_request_location(tmp_path):
    run = workflow(tmp_path, message="去苏州躺着放松的地方")
    run.plan = RetrievalPlan(context=SearchContext(region="苏州"), goal="去苏州躺着放松的地方")
    run.configure_plan()
    assert run.context.max_distance_km is None and run.context.origin is None
    assert not run.request_location and not run.maps.calls


def test_nearby_policy_rejects_invented_quote_and_preserves_explicit_limit(tmp_path):
    run = workflow(tmp_path, message="去苏州躺着放松的地方")
    run.plan = RetrievalPlan(
        context=SearchContext(region="苏州"), goal="去苏州躺着放松的地方", nearby_quote="附近"
    )
    with pytest.raises(ValueError, match="nearby_quote"):
        run.configure_plan()
    assert run.context.max_distance_km is None
    explicit = workflow(tmp_path, message="苏州站附近，2公里内")
    explicit.plan = RetrievalPlan(
        context=SearchContext(
            origin="苏州站", origin_quote="苏州站", max_distance_km=2, distance_quote="2公里内"
        ),
        goal="附近看看",
        nearby_quote="附近",
    )
    explicit.configure_plan()
    assert explicit.context.max_distance_km == 2


def test_plan_missing_evidence_repairs_before_retrieval_and_caches_valid_plan(tmp_path):
    class RepairModel(Model):
        def __init__(self):
            super().__init__(SearchContext(origin="苏州", max_distance_km=5))

        def repair_plan(self, conversation, context, located, rejected, violation):
            self.calls.append("repair")
            assert rejected["context"]["origin"] == "苏州"
            assert "原文" in violation
            assert not located
            return RetrievalPlan(
                context=SearchContext(region="苏州", max_distance_km=5, distance_quote="附近"),
                goal="苏州附近放松一下的地方",
                request_location=True,
            )

    model = RepairModel()
    run = workflow(tmp_path, model=model, message="苏州附近放松一下的地方")
    run.run()
    assert run.status == "completed" and run.request_location
    assert run.context.origin is None and run.center is None
    assert run.context.max_distance_km == 5 and run.context.region == "苏州"
    assert not run.maps.calls and run.metrics["web_attempts"] == 0
    assert model.calls == ["plan", "repair"]
    repeated = workflow(tmp_path, model=model, message="苏州附近放松一下的地方")
    repeated.run()
    assert repeated.status == "completed" and repeated.request_location
    assert model.calls == ["plan", "repair"]


def test_invalid_repair_is_bounded_and_cannot_bypass_explicit_route_limit(tmp_path):
    class InvalidRepair(Model):
        def __init__(self):
            super().__init__(SearchContext(origin="苏州站", max_distance_km=5))

        def repair_plan(self, *args):
            self.calls.append("repair")
            return RetrievalPlan(
                context=SearchContext(
                    origin="苏州站",
                    origin_quote="苏州站",
                    max_distance_km=20,
                    distance_quote="不存在的距离原话",
                ),
                goal="找附近去处",
            )

    model = InvalidRepair()
    run = workflow(tmp_path, model=model, message="苏州站出发，5公里内看看")
    run.run()
    assert run.status == "failed" and not run.cards
    assert model.calls == ["plan", "repair"]
    assert run.context.max_distance_km is None and not run.maps.calls
    assert run.metrics["web_attempts"] == 0


def test_plan_repair_cancellation_starts_no_retrieval(tmp_path):
    model = Model(SearchContext(origin="苏州站"))
    run = workflow(tmp_path, model=model, message="苏州站附近")

    def repair(*args):
        model.calls.append("repair")
        run.cancelled.set()
        return RetrievalPlan(
            context=SearchContext(origin="苏州站", origin_quote="苏州站"), goal="苏州站附近"
        )

    model.repair_plan = repair
    run.run()
    assert run.status == "cancelled" and not run.maps.calls


def test_jobs_bind_cache_scope_to_http_identity(tmp_path):
    import time

    from fastapi.testclient import TestClient

    from roambot.api.routes.discovery import get_discovery_factory
    from roambot.config import Settings
    from roambot.main import create_app

    app = create_app(Settings(provider_mode="mock", data_dir=tmp_path / "app"))
    cache = DiscoveryCache(tmp_path / "api-facts.sqlite3")

    def factory(body, previous):
        return DiscoveryWorkflow(
            body, Maps(), Weather(), Web(), Model(), cache, "", previous, source="demo"
        )

    app.dependency_overrides[get_discovery_factory] = lambda: factory

    def query(client):
        response = client.post("/api/v1/discovery/jobs", json={"message": "苏州看看"})
        assert response.status_code == 200
        key = response.json()["id"]
        for _ in range(100):
            result = client.get("/api/v1/discovery/jobs/" + key).json()
            if result["status"] != "running":
                return result
            time.sleep(0.01)
        pytest.fail("Job did not finish")

    with TestClient(app) as one, TestClient(app) as two:
        first = query(one)
        repeated = query(one)
        other = query(two)
        assert first["cards"] and repeated["cards"] and other["cards"]
        assert repeated["metrics"]["cache_hits"] == 4
        assert other["metrics"]["cache_hits"] == 0


def test_mispaired_place_name_and_id_are_resolved_through_real_map_instead_of_merged(tmp_path):
    run = workflow(tmp_path)
    run.search.search = lambda query: [
        {
            "title": "苏州湖边绿地介绍",
            "url": "https://example.org/lake",
            "excerpt": "湖边绿地的具体场地介绍。",
            "kind": "search_excerpt",
        }
    ]
    run.model.nominate = lambda *args: VenueSelection(
        venues=[
            {
                "name": "湖边绿地",
                "place_id": "amap:1",
                "source_ids": ["s1"],
            }
        ]
    )
    run.run()
    assert run.status == "completed"
    assert [c["place"]["id"] for c in run.cards] == ["amap:2"]
    assert run.cards[0]["place"]["name"] == "湖边绿地"


def test_map_address_and_category_alone_do_not_prove_an_experience(tmp_path):
    run = workflow(tmp_path)
    run.search.search = lambda query: []
    run.run()
    assert not run.cards
    assert "compose" not in run.model.calls


def test_paid_search_budget_is_two_actual_misses_not_two_cache_lookups(tmp_path):
    run = workflow(tmp_path)
    run.plan = run.model.plan()
    run.configure_plan()
    run.web_search("查询一")
    run.web_search("查询一")
    run.web_search("查询二")
    with pytest.raises(ProviderError) as error:
        run.web_search("查询三")
    assert error.value.code == "search_budget"
    assert run.metrics["web_attempts"] == 2


def test_one_invalid_citation_does_not_cancel_other_valid_cards_in_batch(tmp_path):
    run = workflow(tmp_path)
    original = run.model.compose

    def compose(*args):
        batch = original(*args)
        batch.cards[1].evidence_ids = ["invented-citation"]
        return batch

    run.model.compose = compose
    run.run()
    assert len(run.cards) == 3 and run.first_batch_ms is not None
    assert run.status == "partial" and run.metrics["rejected_cards"] == 1


def test_missing_essential_experience_support_is_not_silently_accepted(tmp_path):
    run = workflow(tmp_path, message="要有可休息的草坪")
    base_plan = run.model.plan

    def plan(*args):
        result = base_plan(*args)
        result.requirements = [ExperienceRequirement(text="有可休息的草坪", quote="可休息的草坪")]
        return result

    run.model.plan = plan
    original = run.model.compose

    def compose(*args):
        batch = original(*args)
        for card in batch.cards:
            card.requirement_support = []
        return batch

    run.model.compose = compose
    run.run()
    assert not run.cards and run.metrics["rejected_cards"] == 4


def test_shared_public_facts_save_searches_across_users_without_sharing_private_state(tmp_path):
    from roambot.persistence.discovery_knowledge import DiscoveryKnowledge

    knowledge = DiscoveryKnowledge(tmp_path / "public.sqlite3")
    first = workflow(tmp_path, scope="user-one")
    first.knowledge = knowledge
    first.run()
    assert first.cards and first.metrics["web_attempts"] == 1
    other = workflow(tmp_path, scope="user-two", message="苏州换个心情，看看不同的休闲地方")
    other.knowledge = knowledge
    other.run()
    assert len(other.cards) == 4
    assert other.metrics["web_attempts"] == 0
    assert other.metrics["cache_hits"] == 0
    assert other.model.calls == ["plan", "compose"]


def directional_index():
    places = Maps().search("", "苏州", None, None)

    def entry(place):
        return {
            "place": place,
            "sources": [
                {
                    "title": place["name"] + "介绍",
                    "excerpt": place["name"] + "有明确的活动空间和场地介绍。",
                    "kind": "web_page",
                    "url": "https://example.org/" + place["id"],
                }
            ],
        }

    books = []
    for i in range(5):
        book = copy.deepcopy(places[0])
        book.update(id=f"amap:book{i}", name=f"独立书店{i}")
        books.append(entry(book))
    lake = [entry(places[1])]

    class Index:
        queries = []
        groups = {"书店": books, "湖边": lake}

        def find(self, query, **kwargs):
            self.queries.append(query)
            return self.groups.get(query, [])

        def remember(self, *args):
            pass

    return Index()


def directions_plan():
    return RetrievalPlan(
        context=SearchContext(region="苏州"),
        goal="几种不同的休闲体验",
        directions=[
            {"experience": "翻书", "map_query": "书店", "web_query": "书店阅读空间"},
            {"experience": "水边放松", "map_query": "湖边", "web_query": "湖边休息空间"},
        ],
        map_queries=["书店", "湖边"],
        web_queries=["书店阅读空间", "湖边休息空间"],
    )


def test_public_retrieval_reserves_each_direction_before_more_of_the_popular_one(tmp_path):
    run = workflow(tmp_path)
    run.plan = directions_plan()
    run.context = run.plan.context
    run.knowledge = directional_index()
    result = run.retrieve()
    assert run.knowledge.queries == ["书店", "湖边"]
    assert result[:3] == ["amap:book0", "amap:2", "amap:book1"]
    assert run.metrics["public_query_hits"] == {"书店": 5, "湖边": 1}
    assert run.metrics["web_attempts"] == 0
    assert run.metrics["nomination_skipped"]


def test_many_cached_places_cannot_hide_a_missing_direction(tmp_path):
    run = workflow(tmp_path)
    run.plan = directions_plan()
    run.context = run.plan.context
    run.knowledge = directional_index()
    run.knowledge.groups = {"书店": run.knowledge.groups["书店"], "湖边": []}
    queries = []

    def search(query):
        queries.append(query)
        return EvidenceWeb().search(query)

    run.search.search = search
    run.retrieve()
    assert run.metrics["public_place_hits"] == 5
    assert queries == ["苏州 湖边休息空间"]
    assert run.metrics["web_attempts"] == 1
    assert run.pending_nomination  # Include new evidence after first publication.
    assert "nominate" not in run.model.calls
    run.nominate()
    assert "nominate" in run.model.calls


def test_fresh_search_evidence_reaches_nomination_before_dense_old_topic_sources(tmp_path):
    run = workflow(tmp_path)
    run.plan = directions_plan()
    run.context = run.plan.context
    run.knowledge = directional_index()
    for entry in run.knowledge.groups["书店"]:
        entry["sources"] = [
            {**entry["sources"][0], "url": f"https://old.example.org/{entry['place']['id']}/{i}"}
            for i in range(6)
        ]
    run.knowledge.groups = {"书店": run.knowledge.groups["书店"], "湖边": []}
    run.retrieve()
    fresh_urls = {source["url"] for source in EvidenceWeb().search("")}
    visible = []

    def nominate(conversation, goal, context, sources, places):
        visible.extend(sources)
        return VenueSelection(venues=[])

    run.model.nominate = nominate
    run.nominate()
    # Nomination's source-ID table must include the fresh missing direction, even
    # with >18 cached sources for the other activity. Binding remains by source ID.
    by_id = {f"s{i}": source for i, source in enumerate(run.research_sources, 1)}
    assert len(visible) <= 18
    assert fresh_urls <= {by_id[source["source_id"]]["url"] for source in visible}


def test_review_sees_global_coverage_and_clears_a_resolved_gap(tmp_path):
    run = workflow(tmp_path)
    run.plan = directions_plan()
    run.cards = [{"place": {"id": "amap:book0", "name": "独立书店"}, "experience": "翻书"}]
    assert run.review_context()["already_published"][0]["experience"] == "翻书"
    assert len(run.review_context()["requested_directions"]) == 2
    assert "already_published" not in run.context.model_dump()
    run.evidence_query = "此前缺少的方向"
    run.review_cards([])
    assert run.evidence_query is None


@pytest.mark.parametrize("covered", [False, True])
def test_approved_cards_do_not_imply_requested_directions_were_covered(tmp_path, covered):
    run = workflow(tmp_path)
    run.model.plan = lambda *args: directions_plan()
    run.reviewer = lambda cards: BatchReview(
        approved_ids=[c["place"]["id"] for c in cards],
        rejected=[],
        covered_directions=[
            {"direction": 1, "place_ids": ["amap:1"]},
            {"direction": 2, "place_ids": ["amap:2"]},
        ]
        if covered
        else [],
    )
    run.run()
    assert len(run.cards) == 4
    assert run.status == ("completed" if covered else "partial")
    assert run.metrics["uncovered_direction_indices"] == ([] if covered else [1, 2])
    assert run.metrics["web_attempts"] <= 2


def test_search_hypotheses_do_not_add_hard_conditions_to_an_explicit_user_goal(tmp_path):
    run = workflow(tmp_path, message="苏州可供参观的地方")
    plan = directions_plan()
    plan.requirements = [ExperienceRequirement(text="有可供参观的空间", quote="可供参观")]
    run.model.plan = lambda *args: plan

    # The actual requirement is verified; the planner's optional book/lake split
    # is not an additional user requirement, and no diversity coverage is asserted.
    def review(cards):
        # Access to a space is an actual use condition, not its registered trade.
        # Keep the original web evidence assertion by modelling that distinction.
        approved = [
            c["place"]["id"]
            for c in cards
            if any(s["kind"] in {"web_page", "search_excerpt"} for s in c["sources"])
        ]
        return BatchReview(
            approved_ids=approved,
            rejected=[
                {"place_id": c["place"]["id"], "note": "缺少可供参观的使用条件依据"}
                for c in cards
                if c["place"]["id"] not in approved
            ],
            covered_directions=[],
        )

    run.reviewer = review
    run.run()
    assert run.cards and run.status == "completed"
    assert run.metrics["uncovered_direction_indices"] == [1, 2]
    assert run.metrics["web_attempts"] == 1


def test_missing_direction_is_targeted_after_first_published_batch(tmp_path):
    run = workflow(tmp_path)
    run.plan = directions_plan()
    run.context = run.plan.context
    run.covered_directions = {1}
    queries = []
    run.search.search = lambda query: queries.append(query) or EvidenceWeb().search(query)
    run.supplement()
    assert queries == ["苏州 湖边休息空间"]


def test_reviewed_same_activity_uses_one_request_local_label_not_fake_variety(tmp_path):
    run = workflow(tmp_path)
    run.plan = directions_plan()
    run.plan.directions[0].experience = "随手翻本书"
    run.reviewer = lambda cards: BatchReview(
        approved_ids=["amap:1", "amap:4"],
        rejected=[],
        covered_directions=[{"direction": 1, "place_ids": ["amap:1", "amap:4"]}],
    )
    cards = [
        {"place": {"id": "amap:1"}, "experience": "独立阅读角落", "sources": []},
        {"place": {"id": "amap:4"}, "experience": "文艺气氛翻书", "sources": []},
    ]
    run.review_cards(cards)
    assert [c["experience"] for c in cards] == ["随手翻本书", "随手翻本书"]


def test_published_quote_does_not_expose_other_venue_sections(tmp_path):
    run = workflow(tmp_path)
    run.search.search = lambda query: [
        {
            "title": "场所合集",
            "url": "https://example.org/list",
            "kind": "web_page",
            "excerpt": "01独立书店\n\n独立书店经营旧书。\n\n"
            "02另一家书店\n\n另一家书店有摄影集专柜。",
        }
    ]
    run.run()
    first = next(c for c in run.cards if c["place"]["id"] == "amap:1")
    quotes = [s["excerpt"] for s in first["sources"] if s["kind"] == "web_page"]
    assert quotes and all("摄影集" not in quote for quote in quotes)
