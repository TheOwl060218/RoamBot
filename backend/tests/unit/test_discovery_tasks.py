"""Only execution boundaries for the alternative, not semantic quality evidence."""
import pytest
from test_discovery import Maps, Weather

from roambot.domain.discovery import DiscoveryRequest, RetrievalDirection, RetrievalPlan, SearchContext
from roambot.persistence.discovery_cache import DiscoveryCache
from roambot.providers.protocols import ProviderError
from roambot.services.discovery_tasks import DiscoveryTaskWorkflow, TaskSelection


class Model:
    version = "offline-task-boundary"

    def __init__(self):
        self.calls = []
        self.before_return = lambda: None
        self.business = False
        self.bad = False
        self.fail = False

    def plan(self, *args):
        self.calls.append("plan")
        return RetrievalPlan(intent="business" if self.business else "search",
            context=SearchContext(region="苏州"), goal="换换环境",
            directions=[RetrievalDirection(experience="方式甲", map_query="甲", web_query="甲"),
                        RetrievalDirection(experience="方式乙", map_query="乙", web_query="乙")])

    def choose(self, conversation, context, cards, published):
        self.calls.append("choose")
        if self.fail:
            raise ProviderError("bad_response", "offline protocol failure")
        chosen = [{"place_id": c["place"]["id"], "experience": "体验甲" if i % 2 else "体验乙",
                   "reason": "已有地点登记资料支持这项休闲选择，可以按自己的兴趣前往了解。",
                   "evidence_ids": [c["sources"][0]["id"]]} for i, c in enumerate(cards[:6])]
        if self.bad:
            chosen[0]["place_id"] = "invented"
        self.before_return()
        return TaskSelection(cards=chosen)


def task_run(tmp_path):
    model = Model()
    run = DiscoveryTaskWorkflow(DiscoveryRequest(message="换换环境"), Maps(), Weather(), None,
        model, DiscoveryCache(tmp_path / "facts.sqlite3"), "actor-one")
    return run, model


def test_broad_task_has_two_calls_no_optional_fact_requests_or_independent_judge(tmp_path):
    run, model = task_run(tmp_path)
    run.run()
    assert run.status == "completed", run.errors
    assert len(run.cards) == 4
    assert model.calls == ["plan", "choose"]
    assert run.snapshot()["metrics"]["budget_used"] == {"model": 2, "search": 0}
    assert not run.weather.calls
    assert all(c["route"] is None and c["weather"] is None and not c["reviewed"] for c in run.cards)
    from roambot.domain.discovery_snapshot import StoredCard
    restored = StoredCard.model_validate(run.cards[0]).model_dump(mode="json")
    assert restored["sources"][0]["excerpt"].startswith("名称与登记类型：")
    assert restored["reason"] == run.cards[0]["reason"]


@pytest.mark.parametrize("change", ["cancel", "owner", "context"])
def test_task_cannot_publish_after_cancellation_owner_or_context_change(tmp_path, change):
    run, model = task_run(tmp_path)

    def change_state():
        if change == "cancel":
            run.cancelled.set()
        elif change == "owner":
            run.scope = "other-actor"
        else:
            run.context.region = "其他地区"

    model.before_return = change_state
    run.run()
    assert not run.cards
    assert run.status in {"failed", "cancelled"}


def test_task_keeps_valid_neighbors_without_publishing_an_invented_id(tmp_path):
    run, model = task_run(tmp_path)
    model.bad = True
    run.run()
    assert "invented" not in {c["place"]["id"] for c in run.cards}
    assert run.cards and run.errors
    assert run.budget.counts["model"] <= 3


def test_task_does_not_retry_identical_malformed_model_call(tmp_path):
    run, model = task_run(tmp_path)
    model.fail = True
    run.run()
    assert run.status == "failed" and not run.cards
    assert model.calls == ["plan", "choose"]


def test_task_enforces_real_distance_before_selection_without_requiring_a_date(tmp_path):
    run, model = task_run(tmp_path)
    message = "从苏州站出发，5公里内"
    run.body.message = message
    run.turns[-1]["content"] = message
    original = model.plan

    def plan(*args):
        value = original(*args)
        value.context = SearchContext(origin="苏州站", origin_quote="从苏州站出发",
            region="苏州", max_distance_km=5, distance_quote="5公里内")
        return value

    model.plan = plan
    run.run()
    assert run.cards
    assert "amap:4" not in {c["place"]["id"] for c in run.cards}
    assert all(c["route"]["distance_km"] <= 5 and not c["route"]["estimated"] for c in run.cards)
    assert not run.weather.calls


def test_business_handoff_never_retrieves_or_claims_execution(tmp_path):
    run, model = task_run(tmp_path)
    model.business = True
    run.maps.search = lambda *args: pytest.fail("Business handoff must not retrieve places")
    run.run()
    assert model.calls == ["plan"]
    assert run.snapshot()["intent"] == "business"
    assert run.status == "completed" and not run.reply and not run.cards


def test_same_command_on_different_result_sets_does_not_reuse_old_object_plan(tmp_path):
    cache = DiscoveryCache(tmp_path / "shared-task-plan.sqlite3")
    model = Model()
    model.business = True
    seen = []
    original = model.plan

    def plan(*args):
        seen.append(args[3])
        return original(*args)

    model.plan = plan
    for key in ("result-a", "result-b"):
        previous = {"context": {}, "cards": [{"place": {"id": key, "name": key},
                    "experience": "休闲", "reason": "旧结果理由不进入新规划的候选身份。"}]}
        run = DiscoveryTaskWorkflow(DiscoveryRequest(message="收藏第二个"), None, None, None,
            model, cache, "same-owner", previous)
        run.run()
        assert run.status == "completed", run.errors
    assert model.calls == ["plan", "plan"]
    assert [cards[0]["id"] for cards in seen] == ["result-a", "result-b"]


def test_actual_map_shortlist_is_researched_once_before_reason_generation(tmp_path):
    from test_discovery import Web
    run, model = task_run(tmp_path)
    run.research_shortlist = True
    queries, seen = [], []
    class Search(Web):
        def search(self, query):
            queries.append(query)
            return super().search(query)
    run.search = Search()
    original = model.choose
    def choose(conversation, context, cards, published):
        seen.extend(cards)
        return original(conversation, context, cards, published)
    model.choose = choose
    run.run()
    assert run.status == "completed", run.errors
    assert len(queries) == 1 and queries[0].startswith("苏州 ")
    assert all(name in queries[0] for name in ("独立书店", "湖边绿地", "城市展览"))
    assert "另一家书店" not in queries[0]
    assert run.budget.counts == {"model": 2, "search": 1}
    bound = [c for c in seen if any(s["kind"] == "search_excerpt" for s in c["sources"])]
    assert [c["place"]["id"] for c in bound] == ["amap:1"]


def test_research_cache_cannot_reuse_same_place_name_query_across_regions(tmp_path):
    run, _ = task_run(tmp_path)
    queries = []
    class Search:
        def search(self, query):
            queries.append(query)
            return []
    run.search = Search()
    run.context.region = "城市甲"
    assert run.web_search('"同名公园"') == []
    # A distinct request owns a fresh budget while sharing this actor's cache.
    other, _ = task_run(tmp_path)
    other.search = run.search
    other.context.region = "城市乙"
    assert other.web_search('"同名公园"') == []
    assert queries == ['城市甲 "同名公园"', '城市乙 "同名公园"']


def test_current_map_places_with_fresh_public_sources_do_not_need_paid_search(tmp_path):
    from roambot.persistence.discovery_knowledge import DiscoveryKnowledge
    run, _ = task_run(tmp_path)
    run.research_shortlist = True
    run.knowledge = DiscoveryKnowledge(tmp_path / 'public.sqlite3')
    for place in run.maps.search('', '苏州', None, None)[:3]:
        run.knowledge.remember(place, [{'kind': 'web_page', 'title': place['name'],
            'url': 'https://example.org/' + place['id'].replace(':', '-'),
            'excerpt': place['name'] + '的实际公开介绍。'}])
    class Search:
        def search(self, query):
            pytest.fail('Fresh venue-bound sources should be reused before paid search')
    run.search = Search()
    run.run()
    assert run.status == 'completed', run.errors
    assert run.budget.counts == {'model': 2, 'search': 0}
    assert run.metrics['public_place_hits'] == 3


def test_empty_first_route_window_continues_to_later_actual_candidates(tmp_path):
    run, model = task_run(tmp_path)
    class ManyPlaces(Maps):
        def search(self, *args):
            base = super().search(*args)[0]
            return [base | {'id': f'amap:{i}', 'name': '同名场所'} for i in range(18)]
        def route(self, center, place, mode):
            self.calls.append(('route', place['id'], mode))
            return {'mode': mode, 'distance_km': 8 if int(place['id'].split(':')[1]) < 12 else 3,
                    'duration_minutes': 20, 'estimated': False}
    run.maps = ManyPlaces()
    message = '从苏州站出发，5公里内'
    run.body.message = message
    run.turns[-1]['content'] = message
    original = model.plan
    def plan(*args):
        value = original(*args)
        value.context = SearchContext(region='苏州', origin='苏州站', origin_quote='从苏州站出发',
            max_distance_km=5, distance_quote='5公里内')
        return value
    model.plan = plan
    run.run()
    assert run.status == 'completed', run.errors
    assert {c['place']['id'] for c in run.cards} == {f'amap:{i}' for i in range(12, 18)}
    assert len([call for call in run.maps.calls if call[0] == 'route']) == 18
    assert model.calls == ['plan', 'choose']
    assert run.budget.counts == {'model': 2, 'search': 0}
