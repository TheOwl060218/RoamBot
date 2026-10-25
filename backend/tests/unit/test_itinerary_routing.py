import copy
from datetime import datetime, timedelta, timezone
from roambot.services.itinerary_routing import ItineraryRouter, choose_order, path_cost
from roambot.domain.models import DailyWeather
from roambot.providers.protocols import ProviderError


def itinerary(n=6):
    today = datetime.now(timezone(timedelta(hours=8))).date()
    days = [(today+timedelta(days=i)).isoformat() for i in range(2)]
    stops = [{'id': str(i), 'place': {'id': str(i), 'name': str(i), 'coordinate': {
        'longitude': 120+(i//3)*.3+(i%3)*.001, 'latitude': 31, 'system': 'gcj02'}, 'facts': {}}} for i in range(n)]
    return {'stops': stops, 'start_date': days[0], 'end_date': days[-1], 'travel_mode': 'walking',
        'days': [{'date': days[0], 'stop_ids': [s['id'] for s in stops]}, {'date': days[1], 'stop_ids': []}],
        'unassigned_ids': [], 'route_cache': {}}


class Roads:
    def __init__(self, broken=False): self.calls = 0; self.broken = broken
    def route(self, a, b, mode, geometry=False):
        self.calls += 1
        if self.broken: raise ProviderError('unavailable', 'offline')
        return {'distance_km': 1, 'duration_minutes': 12, 'path': [[a.longitude, a.latitude], [b['coordinate']['longitude'], 31]]}


class Weather:
    def __init__(self): self.calls = 0
    def daily(self, coordinate, first, last):
        self.calls += 1
        return [DailyWeather(date=first+timedelta(days=i), condition='雨' if (i==0)==(coordinate.longitude<120.1) else '晴',
            temp_min_c=15, temp_max_c=20, precipitation_mm=20 if (i==0)==(coordinate.longitude<120.1) else 0,
            wind_speed_kmh=5, humidity_percent=60, visibility_km=10, uv_index=3)
            for i in range((last-first).days+1)]


def test_weather_changes_day_assignment_without_losing_points_or_fabricating_times():
    doc = itinerary(); before = copy.deepcopy(doc)
    roads, weather = Roads(), Weather()
    result = ItineraryRouter(roads, weather).generate(doc, True, 'test')
    assert result['days'][0]['stop_ids'] == ['3', '4', '5']
    assert result['days'][1]['stop_ids'] == ['0', '1', '2']
    assert sum(len(d['stop_ids']) for d in result['days']) == 6
    assert weather.calls == 2 and roads.calls <= 48
    assert doc == before
    assert not any('arrival_time' in s or 'stay_minutes' in s for s in result['stops'])


def test_missing_roads_remain_unknown_and_updates_keep_manual_order():
    doc = itinerary(3); roads = Roads(True)
    doc['days'][0]['stop_ids'] = ['2', '0', '1']
    result = ItineraryRouter(roads, Weather(), route_limit=6).generate(doc, False, 'manual')
    assert result['days'] == doc['days']
    assert result['route_status'] == 'partial'
    assert all(not v['actual'] and v['distance_km'] is None and v['duration_minutes'] is None for v in result['routes'])
    assert roads.calls == 2  # Failures are not automatically retried.


def test_explicit_update_reuses_unchanged_road_legs():
    doc = itinerary(3); roads, weather = Roads(), Weather()
    routing = ItineraryRouter(roads, weather)
    first = routing.generate(doc, False, 'one'); count = roads.calls; weather_count = weather.calls
    second = routing.generate(first, False, 'two')
    assert second['days'] == first['days']
    assert roads.calls == count
    assert weather.calls == weather_count


def test_remote_dates_have_no_made_up_weather_or_forecast_calls():
    doc = itinerary(2)
    start = datetime.now(timezone.utc).date()+timedelta(days=40)
    doc['start_date'], doc['end_date'] = start.isoformat(), (start+timedelta(days=1)).isoformat()
    weather = Weather()
    result = ItineraryRouter(Roads(), weather).generate(doc, True, 'far')
    assert weather.calls == 0 and result['weather'] == {}
    assert result['notices']


def test_order_search_can_improve_a_zigzag_without_claiming_global_optimality():
    points = [{'id': str(i), 'x': x} for i, x in enumerate([0, 8, 1, 7, 2, 6])]
    cost = lambda a, b: abs(a['x']-b['x'])
    actual = choose_order(points, cost)
    assert path_cost(actual, cost) < path_cost(points, cost)
    assert {v['id'] for v in actual} == {v['id'] for v in points}
