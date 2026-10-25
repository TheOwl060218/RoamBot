"""Location correction and uncertainty boundaries, no real providers."""
import pytest
from pydantic import ValidationError
from test_discovery import Maps, Weather
from test_discovery_sources import Model, Search
from roambot.domain.discovery import DiscoveryRequest, RetrievalPlan, SearchContext
from roambot.persistence.discovery_cache import DiscoveryCache
from roambot.services.discovery_sources import DiscoverySourceWorkflow


def run_at(tmp_path, details, region=None):
    body = DiscoveryRequest(message='找个地方放空', location={'longitude': 120, 'latitude': 31, 'system': 'gcj02'},
                            location_details=details)
    maps, model = Maps(), Model()
    maps.area = lambda point: '江苏省 苏州市'
    run = DiscoverySourceWorkflow(body, maps, Weather(), Search(), model,
        DiscoveryCache(tmp_path / 'location.sqlite3'), 'location-test')
    run.plan = RetrievalPlan(context=SearchContext(region=region), goal=body.message, web_queries=['放松'])
    return run


def test_precise_device_location_has_visible_area_and_no_extra_reverse_lookup(tmp_path):
    run = run_at(tmp_path, {'accuracy_m': 40, 'captured_at': 1000})
    run.configure_plan()
    assert run.center is not None
    assert run.snapshot()['position'] == {'label': '江苏省 苏州市', 'source': 'device',
        'approximate': False, 'accuracy_m': 40, 'captured_at': 1000}
    assert run.search_area() == '江苏省 苏州市'


@pytest.mark.parametrize('region', [None, '苏州'])
def test_coarse_device_location_cannot_anchor_routes(tmp_path, region):
    run = run_at(tmp_path, {'accuracy_m': 20000}, region)
    run.configure_plan()
    assert run.center is None
    assert run.snapshot()['position']['approximate'] is True
    assert not run.routes
    assert run.context.region == region


def test_selected_location_overrides_old_origin_without_geocoding_or_chat_quote(tmp_path):
    run = run_at(tmp_path, {'source': 'selected', 'name': '苏州站'})
    run.context = SearchContext(origin='旧的出发地', origin_quote='旧的出发地')
    run.configure_plan()
    assert run.context.origin == run.center_name == '苏州站'
    assert run.center.longitude == 120
    assert not any(call[0] == 'geocode' for call in run.maps.calls)
    assert run.snapshot()['position']['source'] == 'selected'


def test_explicit_relocate_does_not_keep_previous_selected_origin(tmp_path):
    run = run_at(tmp_path, {'source': 'device', 'accuracy_m': 30, 'replace_origin': True})
    run.context = SearchContext(origin='旧的出发地')
    run.configure_plan()
    assert run.context.origin is None
    assert run.center_name == '当前位置'


def test_location_button_reuses_only_server_supplied_search_plan(tmp_path):
    run = run_at(tmp_path, {'source': 'selected', 'name': '苏州站'})
    run.previous['_location_plan'] = run.plan.model_dump(mode='json')
    run.model.plan = lambda *args: pytest.fail('Location button must not reinterpret the same wish')
    value = run.load_plan({}, [])
    assert value['goal'] == '找个地方放空'
    assert run.metrics['model_calls'] == 0


@pytest.mark.parametrize('details', [{'accuracy_m': -1}, {'accuracy_m': float('nan')}, {'source': 'selected'}])
def test_invalid_location_metadata_rejected(details):
    with pytest.raises(ValidationError):
        DiscoveryRequest(message='放松', location={'longitude': 120, 'latitude': 31}, location_details=details)


def test_metadata_without_coordinates_is_rejected():
    with pytest.raises(ValidationError):
        DiscoveryRequest(message='放松', location_details={'accuracy_m': 40})


def test_distance_prefilter_uses_entrance_not_remote_poi_center(tmp_path):
    run = run_at(tmp_path, {'accuracy_m': 30})
    run.configure_plan()
    run.context.max_distance_km = 5
    run.places['amap:1'] = {'id': 'amap:1',
        'coordinate': {'longitude': 121, 'latitude': 32, 'system': 'gcj02'},
        'facts': {'entr_location': '120.001,31'}}
    assert run.facts(['amap:1']) == ['amap:1']
    assert ('route', 'amap:1', 'walking') in run.maps.calls


def region_only_run(tmp_path, *, origin=None, maximum=None):
    message = '从苏州站出发找公园' if origin else '去苏州看看公园'
    if maximum:
        message += '，5公里以内'
    body = DiscoveryRequest(message=message, use_location=False,
        location={'longitude': 104, 'latitude': 30, 'system': 'wgs84'})
    previous = {'context': SearchContext().model_dump(),
        'center': {'longitude': 104, 'latitude': 30, 'system': 'gcj02'}, 'center_name': '旧设备位置'}
    maps, model = Maps(), Model()
    run = DiscoverySourceWorkflow(body, maps, Weather(), Search(), model,
        DiscoveryCache(tmp_path / 'region-only.sqlite3'), 'region-test', previous=previous)
    run.plan = RetrievalPlan(context=SearchContext(region='苏州', origin=origin,
        origin_quote=origin, max_distance_km=maximum, distance_quote='5公里以内' if maximum else None), goal=message, web_queries=['公园'])
    return run


def test_region_only_clears_inherited_device_point_without_routes_or_reverse_lookup(tmp_path):
    run = region_only_run(tmp_path)
    run.configure_plan()
    assert run.location is run.center is None
    assert run.center_name is None
    assert run.context.region == '苏州'
    assert run.snapshot()['position']['source'] == 'region'
    assert run.snapshot()['position']['label'] == '苏州'
    assert run.maps.calls == []


def test_region_only_never_relaxes_a_hard_distance_limit(tmp_path):
    run = region_only_run(tmp_path, maximum=5)
    run.configure_plan()
    assert run.center is None
    assert run.context.max_distance_km == 5


def test_explicit_new_departure_still_works_after_region_only_choice(tmp_path):
    run = region_only_run(tmp_path, origin='苏州站')
    run.configure_plan()
    assert run.center_name == '苏州站'
    assert ('geocode', '苏州站') in run.maps.calls
    assert not any(call[0] == 'gps' for call in run.maps.calls)


def test_region_only_ui_action_reuses_owned_plan_without_reinterpreting_the_wish(tmp_path):
    run = region_only_run(tmp_path)
    run.previous['_location_plan'] = run.plan.model_dump(mode='json')
    run.model.plan = lambda *args: pytest.fail('Region button should reuse the owned plan')
    assert run.load_plan({}, [])['goal'] == run.body.message
    assert run.metrics['model_calls'] == 0

def test_nearby_is_search_scope_not_an_unspoken_hard_distance(tmp_path):
    run = run_at(tmp_path, {})
    run.body = DiscoveryRequest(message='附近散步')
    run.turns = [{'role': 'user', 'content': run.body.message}]
    plan = RetrievalPlan(context=SearchContext(), goal='附近散步', nearby_quote='附近', web_queries=['公园'])
    assert run.plan_context(plan).max_distance_km is None


def test_explicit_distance_still_survives_nearby_search(tmp_path):
    run = run_at(tmp_path, {})
    run.body = DiscoveryRequest(message='附近散步，3公里以内')
    run.turns = [{'role': 'user', 'content': run.body.message}]
    plan = RetrievalPlan(context=SearchContext(max_distance_km=3, distance_quote='3公里以内'),
        goal=run.body.message, nearby_quote='附近', web_queries=['公园'])
    assert run.plan_context(plan).max_distance_km == 3
