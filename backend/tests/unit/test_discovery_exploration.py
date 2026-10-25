"""No providers: pool ownership, qualification, freshness and non-repetition."""
import time
from datetime import datetime, timezone

import pytest
from test_discovery_sources import workflow, Model, Search
from test_discovery import Maps, Weather
from roambot.domain.discovery import DiscoveryRequest, RetrievalPlan, SearchContext
from roambot.domain.discovery_snapshot import DiscoveryArchive
from roambot.persistence.discovery_cache import DiscoveryCache
from roambot.services.discovery import DiscoveryJobs, DiscoveryRun
from roambot.services.discovery_sources import DiscoverySourceWorkflow, SelectedPlace, SelectedPlaces
from roambot.services.discovery_exploration import other_area, spatial_order
from roambot.services.personal_data import public_discovery_snapshot


def prepared(tmp_path):
    first, model = workflow(tmp_path)
    model.expanded_candidates = True
    def choose(conversation, context, cards, published):
        picks = [SelectedPlace(place_id=c['place']['id'], experience='休闲',
            evidence_ids=[next(s['id'] for s in c['sources'] if s['kind'] == 'map_record')]) for c in cards]
        return SelectedPlaces(cards=picks[:1], reserve_cards=picks[1:2])
    model.choose = choose
    first.run()
    assert first.cards, first.errors
    assert first.reserve_cards
    return first


def followup(first, tmp_path, *, mode='batch', selected=(), previous=None):
    body = DiscoveryRequest(message='换一批', previous_id='owned', explore_mode=mode,
        view={'selected_ids': list(selected)})
    run = DiscoverySourceWorkflow(body, Maps(), Weather(), Search(), Model(),
        DiscoveryCache(tmp_path/'next.sqlite3'), 'owner', previous=previous or first.snapshot())
    return run


def test_pool_is_only_qualified_and_cached_batch_spends_no_provider_calls(tmp_path):
    first = prepared(tmp_path)
    before = first.snapshot()
    state = before['exploration_state']
    assert len(state['reserve']) + len(first.cards) == 2  # Other map hits weren't approved.
    run = followup(first, tmp_path)
    run.maps.search = lambda *args: pytest.fail('cached batch cannot query maps')
    run.search.search = lambda *args: pytest.fail('cached batch cannot search')
    run.run()
    assert run.status == 'completed', run.errors
    assert run.model.calls == [] and run.maps.calls == []
    assert run.snapshot()['exploration']['used_reserve'] is True
    assert {c['place']['id'] for c in run.cards}.isdisjoint(c['place']['id'] for c in first.cards)
    assert len(run.snapshot()['exploration_state']['seen']) == 2
    assert first.snapshot()['cards'] == before['cards']
    assert first.snapshot()['exploration_state'] == before['exploration_state']


def test_selected_objects_survive_and_foreign_selection_is_rejected(tmp_path):
    first = prepared(tmp_path)
    selected = first.cards[0]['place']['id']
    run = followup(first, tmp_path, selected=[selected])
    run.run()
    assert run.cards[0] == first.cards[0]
    assert run.snapshot()['exploration']['new_count'] == 1
    with pytest.raises(ValueError, match='已选地点'):
        followup(first, tmp_path, selected=['foreign'])


def test_chat_batch_reuses_pool_and_preserves_owned_location_metadata(tmp_path):
    first = prepared(tmp_path)
    old = first.snapshot()
    old['position'] = {'label': '已确认的位置', 'source': 'selected', 'approximate': True,
                       'accuracy_m': 1500, 'captured_at': 12345}
    run = followup(first, tmp_path, previous=old)
    run.body.explore_mode = None  # Ordinary chat goes through existing intake once.
    run.model.plan = lambda *args: RetrievalPlan(context=SearchContext(), goal='换一批',
        web_queries=['相同完整需求'], explore_mode='batch')
    run.run()
    assert run.status == 'completed' and run.used_reserve, run.errors
    assert run.maps.calls == [] and run.search.queries == []
    assert run.snapshot()['position'] == old['position']


def test_expired_pool_retrieves_once_without_replanning_and_keeps_seen_out(tmp_path):
    first = prepared(tmp_path)
    old = first.snapshot()
    old['exploration_state']['created_at'] = time.time() - 601
    run = followup(first, tmp_path, previous=old)
    run.run()
    assert 'plan' not in run.model.calls
    assert run.model.calls == ['nominate', 'choose']
    assert len(run.search.queries) == 1
    assert first.cards[0]['place']['id'] not in {c['place']['id'] for c in run.cards}
    assert not run.used_reserve


def test_new_context_does_not_reuse_a_pool_for_old_conditions(tmp_path):
    first = prepared(tmp_path)
    run = followup(first, tmp_path)
    run.plan = RetrievalPlan(context=SearchContext(region='杭州'), goal='换城市')
    assert run.use_exploration_reserve() is False
    assert run.explore_mode is None and not run.cards


def test_area_novelty_and_soft_spatial_order_preserve_qualified_set():
    def card(key, x, district='旧区'):
        return {'place': {'id': key, 'coordinate': {'longitude': x, 'latitude': 31}, 'facts': {'district': district}}}
    first, neighbour, remote = card('a', 120), card('b', 120.001), card('c', 120.1)
    assert not other_area(neighbour['place'], [first['place']])
    assert other_area(remote['place'], [first['place']])
    assert other_area(card('d', 120.001, '另一区')['place'], [first['place']])
    ordered = spatial_order([first, neighbour, remote])
    assert {c['place']['id'] for c in ordered} == {'a', 'b', 'c'}
    assert spatial_order([first], limit=12) == [first]  # No fabricated area quota.


def test_exploration_archive_restores_pool_but_does_not_publish_it(tmp_path):
    first = prepared(tmp_path)
    archive = DiscoveryArchive.model_validate(first.snapshot() | {'generated_at': datetime.now(timezone.utc)})
    saved = archive.model_dump(mode='json')
    restored = DiscoveryRun(DiscoveryRequest(message='放松'), None, None, None, None,
        previous={'context': {}, 'exploration_state': saved['exploration_state']})
    assert restored.snapshot()['exploration_state']['reserve']
    public = public_discovery_snapshot({'message': '放松', 'context': {}}, saved)
    assert 'exploration_state' not in public
    assert len(public['cards']) == len(first.cards)


def test_exploration_post_is_owned_and_idempotent(tmp_path, monkeypatch):
    first = prepared(tmp_path)
    jobs = DiscoveryJobs()
    jobs.jobs['owned'] = ('owner', time.monotonic(), first)
    monkeypatch.setattr(jobs.pool, 'submit', lambda *args: None)
    calls = []
    def factory(body, previous):
        calls.append(previous)
        return followup(first, tmp_path, previous=previous)
    body = DiscoveryRequest(message='换一批', previous_id='owned', explore_mode='batch')
    key = jobs.start('owner', body, factory)
    assert jobs.start('owner', body, factory) == key
    assert len(calls) == 1 and calls[0]['_explore_plan']['intent'] == 'search'
    with pytest.raises(LookupError):
        jobs.start('someone-else', body, factory)
    jobs.close()
