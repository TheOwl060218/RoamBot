"""User operations with isolated SQLite and deterministic provider boundaries."""
import copy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from test_discovery_commands import source_job
from test_history import register, PASSWORD
from roambot.api.routes.itineraries import get_itinerary_router
from roambot.api.routes.commands import get_business_planner
from roambot.providers.mock import MockWeatherProvider
from roambot.services.itinerary_routing import ItineraryRouter, km


def call(client, method, path, csrf='', body=None):
    result = client.request(method, '/api/v1/itineraries'+path,
        headers={'X-CSRF-Token': csrf} if csrf else {}, json=body)
    assert result.status_code in {200, 201}, result.text
    return result.json()


def create(client, csrf='', name='两天旅行'):
    return call(client, 'POST', '', csrf, {'name': name})['itinerary']


def seed(client, csrf='', rounds=3):
    trip = create(client, csrf)
    for i in range(rounds):
        job = source_job(client, csrf)
        run = client.app.state.discovery_jobs.jobs[job][2]
        for j, c in enumerate(run.cards):
            c['place']['id'] += f'-{i}'
            c['place']['name'] += f'-{i}'
            c['place']['coordinate']['longitude'] += i*.03+j*.005
            trip = call(client, 'POST', f"/{trip['id']}/stops", csrf,
                {'source_job_id': job, 'place_id': c['place']['id']})['itinerary']
    return trip, job


def configure(client, trip, csrf=''):
    start = datetime.now(timezone(timedelta(hours=8))).date()
    return call(client, 'PATCH', '/'+trip['id'], csrf, {'version': trip['version'],
        'start_date': start.isoformat(), 'end_date': (start+timedelta(days=1)).isoformat(),
        'travel_mode': 'walking'})['itinerary']


class Roads:
    def __init__(self): self.calls = []
    def route(self, origin, place, mode, *, geometry=False):
        self.calls.append((origin.longitude, place['id'], mode))
        point = place['coordinate']
        distance = abs(origin.longitude-point['longitude'])*100 + .2
        return {'distance_km': distance, 'duration_minutes': distance*12, 'mode': mode,
                'path': [[origin.longitude, origin.latitude], [point['longitude'], point['latitude']]]}


def test_three_rounds_dates_generate_edit_update_restore_and_no_calls_while_dragging(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, 'itinerary_owner')
    trip, job = seed(client, csrf)
    assert len(trip['stops']) == 6
    same = call(client, 'POST', f"/{trip['id']}/stops", csrf,
        {'source_job_id': job, 'place_id': trip['stops'][-1]['place']['id']})
    assert not same['added'] and len(same['itinerary']['stops']) == 6
    trip = configure(client, trip, csrf)
    roads = Roads()
    client.app.dependency_overrides[get_itinerary_router] = lambda: ItineraryRouter(roads, MockWeatherProvider())
    request_id = str(uuid4())
    body = {'version': trip['version'], 'request_id': request_id, 'optimize': True}
    trip = call(client, 'POST', f"/{trip['id']}/generate", csrf, body)['itinerary']
    assert len(trip['days']) == 2 and all(d['stop_ids'] for d in trip['days'])
    assert len([v for d in trip['days'] for v in d['stop_ids']]) == 6
    assert trip['route_status'] == 'ready' and trip['routes'] and trip['weather']
    before = len(roads.calls)
    replay = call(client, 'POST', f"/{trip['id']}/generate", csrf, body)['itinerary']
    assert replay == trip and len(roads.calls) == before
    days = copy.deepcopy(trip['days']); days[0]['stop_ids'].reverse()
    moved = days[0]['stop_ids'].pop(); days[1]['stop_ids'].insert(0, moved)
    trip = call(client, 'PUT', f"/{trip['id']}/order", csrf, {'version': trip['version'], 'days': days, 'unassigned_ids': []})['itinerary']
    assert len(roads.calls) == before and trip['route_status'] == 'dirty'
    trip = call(client, 'POST', f"/{trip['id']}/generate", csrf,
        {'version': trip['version'], 'request_id': str(uuid4()), 'optimize': False})['itinerary']
    assert trip['days'] == days  # Update never re-optimizes manual edits.
    assert trip['route_status'] == 'ready'
    stop_id = trip['days'][1]['stop_ids'][0]
    trip = call(client, 'DELETE', f"/{trip['id']}/stops/{stop_id}?version={trip['version']}", csrf)['itinerary']
    assert len(trip['stops']) == 5
    assert call(client, 'GET', '/'+trip['id'])['itinerary'] == trip
    assert client.get('/api/v1/itineraries/'+trip['id']).headers['Cache-Control'] == 'no-store'


def test_guest_login_adoption_is_durable_and_cannot_be_claimed_by_another_account(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    trip, _ = seed(client, rounds=1)
    cookie = client.cookies.get('roambot_assistant_identity')
    csrf = register(client, 'adopt_itinerary')
    assert call(client, 'GET', '/'+trip['id'])['itinerary']['stops'] == trip['stops']
    assert client.cookies.get('roambot_assistant_identity') is None
    client.post('/api/v1/auth/logout', headers={'X-CSRF-Token': csrf})
    assert call(client, 'GET', '')['itineraries'] == []
    with TestClient(client.app) as thief:
        thief.cookies.set('roambot_assistant_identity', cookie)
        register(thief, 'another_itinerary')
        assert thief.get('/api/v1/itineraries/'+trip['id']).status_code == 404
    logged = client.post('/api/v1/auth/login', json={'username': 'adopt_itinerary', 'password': PASSWORD})
    assert logged.status_code == 200
    assert call(client, 'GET', '/'+trip['id'])['itinerary']['stops'] == trip['stops']


def test_transfer_is_atomic_duplicate_safe_and_foreign_targets_cannot_remove_source(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    trip, _ = seed(client, rounds=1)
    target = create(client, name='另一个行程')
    assert call(client, 'GET', '')['current_id'] == target['id']
    stop = trip['stops'][0]
    response = client.post(f"/api/v1/itineraries/{trip['id']}/stops/{stop['id']}/move",
        json={'version': trip['version'], 'target_id': 'foreign'})
    assert response.status_code == 404
    assert call(client, 'GET', '/'+trip['id'])['itinerary'] == trip
    target = call(client, 'POST', f"/{trip['id']}/stops/{stop['id']}/move", body={'version': trip['version'], 'target_id': target['id']})['itinerary']
    assert target['stops'][0]['place'] == stop['place']
    assert len(call(client, 'GET', '/'+trip['id'])['itinerary']['stops']) == 1


def test_stale_edits_invented_places_foreign_sources_and_csrf_are_rejected(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    csrf = register(client, 'itinerary_guards')
    trip, job = seed(client, csrf, rounds=1)
    assert client.patch('/api/v1/itineraries/'+trip['id'], json={'version': trip['version'], 'name': 'bad'}).status_code == 403
    headers = {'X-CSRF-Token': csrf}
    assert client.patch('/api/v1/itineraries/'+trip['id'], headers=headers, json={'version': 1, 'name': 'stale'}).status_code == 409
    assert client.post(f"/api/v1/itineraries/{trip['id']}/stops", headers=headers,
        json={'source_job_id': job, 'place_id': 'invented'}).status_code == 404
    assert client.post(f"/api/v1/itineraries/{trip['id']}/stops", headers=headers,
        json={'source_job_id': job, 'place_id': 'invented', 'coordinate': {'longitude': 1, 'latitude': 1}}).status_code == 422
    with TestClient(client.app) as other:
        other_trip = create(other)
        assert other.post(f"/api/v1/itineraries/{other_trip['id']}/stops", json={'source_job_id': job, 'place_id': trip['stops'][0]['place']['id']}).status_code == 404


def test_favorites_and_chat_use_the_same_bound_apis(auth_api_fixture):
    client, _, _ = auth_api_fixture(); csrf = register(client, 'itinerary_chat')
    trip, job = seed(client, csrf, rounds=1)
    client.app.dependency_overrides[get_business_planner] = lambda: lambda request, context: {
        'actions': [{'tool': 'add_to_itinerary', 'arguments': {'place': 2}}], 'question': None}
    response = client.post('/api/v1/assistant/commands/proposals', headers={'X-CSRF-Token': csrf},
        json={'request_id': str(uuid4()), 'message': '把第二个加入行程', 'context': {'page': '/explore', 'discovery_job_id': job}})
    assert response.status_code == 200, response.text
    proposal = response.json()
    executed = client.post('/api/v1/assistant/commands/execute', headers={'X-CSRF-Token': csrf},
        json={'request_id': proposal['request_id'], 'proposal': proposal['proposal']})
    assert executed.json()['status'] == 'completed', executed.text
    assert len(executed.json()['steps'][0]['result']['itinerary']['stops']) == 2
    favorite = client.post('/api/v1/favorites', headers={'X-CSRF-Token': csrf}, json={
        'provider': 'amap', 'destination': {'provider_id': 'amap:favorite_test', 'name': '已收藏书屋', 'city': '苏州',
            'address': '实际地址', 'coordinate': {'longitude': 120.7, 'latitude': 31.3}, 'type_name': '书店', 'type_code': '1'}})
    assert favorite.status_code in {200, 201}, favorite.text
    favorite_id = favorite.json()['favorite']['id']
    result = call(client, 'POST', f"/{trip['id']}/stops", csrf, {'favorite_id': favorite_id})['itinerary']
    assert result['stops'][-1]['place']['name'] == '已收藏书屋'


def test_guest_chat_can_open_a_bound_day_map_without_generating_routes(auth_api_fixture):
    client, _, _ = auth_api_fixture()
    trip, _ = seed(client, rounds=1)
    trip = configure(client, trip)
    days = copy.deepcopy(trip['days'])
    days[1]['stop_ids'] = [s['id'] for s in trip['stops']]
    trip = call(client, 'PUT', '/'+trip['id']+'/order', body={
        'version': trip['version'], 'days': days, 'unassigned_ids': []})['itinerary']
    client.app.dependency_overrides[get_business_planner] = lambda: lambda request, context: {
        'actions': [{'tool': 'show_itinerary_map', 'arguments': {'day_number': 2}}], 'question': None}
    proposal = client.post('/api/v1/assistant/commands/proposals', json={
        'request_id': str(uuid4()), 'message': '看看第二天的路线地图', 'context': {
            'page': '/itineraries/'+trip['id'], 'itinerary_id': trip['id'], 'itinerary_version': trip['version']}})
    assert proposal.status_code == 200, proposal.text
    value = proposal.json()
    result = client.post('/api/v1/assistant/commands/execute', json={
        'request_id': value['request_id'], 'proposal': value['proposal']}).json()
    assert result['status'] == 'completed', result
    assert result['steps'][0]['result']['effect'] == {'tool': 'show_itinerary_map',
        'arguments': {'itinerary_id': trip['id'], 'date': trip['days'][1]['date']}}
    assert call(client, 'GET', '/'+trip['id'])['itinerary'] == trip
