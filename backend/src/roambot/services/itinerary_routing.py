"""Bounded heuristic routes. Unknown road/weather facts stay unknown in output."""
import copy
import math
import time
from datetime import datetime, timedelta, timezone

from roambot.domain.models import Coordinate
from roambot.providers.discovery import arrival_coordinate
from roambot.providers.protocols import ProviderError
from roambot.services.itineraries import dates, fail


def km(a, b):
    x, y = arrival_coordinate(a['place']), arrival_coordinate(b['place'])
    lat = math.radians((x.latitude + y.latitude)/2)
    return math.hypot((x.longitude-y.longitude)*math.cos(lat), x.latitude-y.latitude)*111.2


def path_cost(order, cost):
    return sum(cost(a, b) for a, b in zip(order, order[1:]))


def choose_order(stops, cost):
    """Multi-start nearest-neighbour plus a bounded directed reversal search."""
    if len(stops) < 2: return stops[:]
    proposals = [stops[:]]
    for start in stops:
        left, route = [s for s in stops if s['id'] != start['id']], [start]
        while left:
            best = min(left, key=lambda s: cost(route[-1], s))
            left.remove(best); route.append(best)
        proposals.append(route)
    best = min(proposals, key=lambda p: path_cost(p, cost))
    for _ in range(3):
        current, candidate = path_cost(best, cost), best
        for i in range(len(best)-1):
            for j in range(i+2, len(best)+1):
                trial = best[:i]+list(reversed(best[i:j]))+best[j:]
                if path_cost(trial, cost) < current - 1e-6:
                    current, candidate = path_cost(trial, cost), trial
        if candidate is best: break
        best = candidate
    return best


def bad_weather(day):
    return min(day['precipitation_mm'], 30)*2 + max(0, day['wind_speed_kmh']-20)*.5 + max(0, day['temp_max_c']-33)*2


class ItineraryRouter:
    def __init__(self, maps, weather, *, route_limit=48, weather_limit=4, map_interval=0):
        self.maps, self.weather = maps, weather
        self.route_limit, self.weather_limit = route_limit, weather_limit
        self.map_interval = map_interval

    def generate(self, original, optimize, request_id):
        doc = copy.deepcopy(original)
        days = dates(doc['start_date'], doc['end_date'])
        if not days: fail('itinerary_dates_required', '请先确定出行日期。')
        if not doc['stops']: fail('itinerary_empty', '先把想去的地点加入行程。')
        if optimize and len(doc['stops']) > 16:
            fail('optimization_limit', '一次自动安排最多16个地点；可分批安排或手动调整后更新路线。')
        now = time.time()
        mode = doc['travel_mode']
        by_id = {s['id']: s for s in doc['stops']}
        cached = doc.get('route_cache', {})
        cache = {key: value for key, value in cached.items() if now-value.get('fetched_at', 0) < 600}
        counts = {'route': 0, 'weather': 0}
        tried = set()
        last_map = [0.0]
        started = time.monotonic()
        def key(a, b):
            coords = [arrival_coordinate(v['place']).model_dump() for v in (a, b)]
            return mode + ':' + ':'.join(f"{p['longitude']:.6f},{p['latitude']:.6f}" for p in coords)
        def measure(a, b):
            ref = key(a, b)
            if ref in cache: return cache[ref]
            if ref in tried or counts['route'] >= self.route_limit or time.monotonic()-started > 80: return None
            tried.add(ref); counts['route'] += 1
            try:
                wait = self.map_interval - (time.monotonic()-last_map[0])
                if wait > 0: time.sleep(wait)
                last_map[0] = time.monotonic()
                result = self.maps.route(arrival_coordinate(a['place']), b['place'], mode, geometry=True)
                if any(not math.isfinite(result[v]) or result[v] < 0 for v in ('distance_km', 'duration_minutes')):
                    return None
                cache[ref] = result | {'fetched_at': now}
                return cache[ref]
            except (ProviderError, ValueError, KeyError, TypeError):
                return None
        def cost(a, b):
            known = cache.get(key(a, b))
            return known['distance_km'] if known else km(a, b)

        # Regional forecasts are fetched only within the provider's current
        # seven-day horizon. Each entry records its representative coordinate.
        today = datetime.now(timezone(timedelta(hours=8))).date()
        first, last = max(today, datetime.fromisoformat(days[0]).date()), min(today+timedelta(days=6), datetime.fromisoformat(days[-1]).date())
        weather, samples = {}, []
        for stop in doc['stops']:
            old_weather = doc.get('weather', {}).get(stop['id'])
            requested = {(first+timedelta(days=i)).isoformat() for i in range((last-first).days+1)} if first <= last else set()
            if old_weather and requested and now-old_weather.get('fetched_at', 0) < 600 and requested <= {v['date'] for v in old_weather['days']}:
                weather[stop['id']] = old_weather
                samples.append({'stop': stop, 'data': old_weather})
                continue
            representative = min(samples, key=lambda v: km(stop, v['stop']), default=None)
            if representative is not None and km(stop, representative['stop']) < 15:
                weather[stop['id']] = representative['data']
                continue
            if first > last or counts['weather'] >= self.weather_limit or time.monotonic()-started > 80:
                continue
            counts['weather'] += 1
            try:
                coordinate = arrival_coordinate(stop['place'])
                rows = [v.model_dump(mode='json') for v in self.weather.daily(coordinate, first, last)]
                value = {'days': rows, 'coordinate': coordinate.model_dump(), 'fetched_at': now, 'regional': True}
                samples.append({'stop': stop, 'data': value}); weather[stop['id']] = value
            except (ProviderError, ValueError, TypeError):
                continue

        if optimize:
            # Spend on a sparse set of plausible edges, reserve capacity for
            # every leg of the final route; no full N x N road matrix.
            stops = doc['stops']
            preliminary = choose_order(stops, km)
            shortlist = list(zip(preliminary, preliminary[1:]))
            shortlist += [(a, b) for a in stops for b in sorted((v for v in stops if v['id'] != a['id']), key=lambda v: km(a, v))[:2]]
            for a, b in shortlist:
                if counts['route'] >= self.route_limit - len(stops): break
                measure(a, b)
            order = choose_order(stops, cost)
            groups = []
            active_days = min(len(days), len(order))
            # Balanced contiguous spatial groups keep all selected places and
            # avoid filling the sole sunny day with the entire trip.
            for i in range(active_days):
                groups.append(order[i*len(order)//active_days:(i+1)*len(order)//active_days])
            def weather_cost(group, day):
                values = [next((v for v in weather.get(s['id'], {}).get('days', []) if v['date']==day), None) for s in group]
                known = [bad_weather(v) for s in group for v in weather.get(s['id'], {}).get('days', [])]
                neutral = sum(known)/len(known) if known else 0
                return sum(bad_weather(v) if v is not None else neutral for v in values)
            available = days[:]
            assignments = []
            for group in groups:
                chosen = min(available, key=lambda d: weather_cost(group, d))
                assignments.append((group, chosen)); available.remove(chosen)
            # Improve the initial date assignment without affecting within-day
            # order; unknown forecasts never imply better weather than known.
            for i in range(len(assignments)):
                for j in range(i+1, len(assignments)):
                    a, da = assignments[i]; b, db = assignments[j]
                    if weather_cost(a, db)+weather_cost(b, da) < weather_cost(a, da)+weather_cost(b, db):
                        assignments[i], assignments[j] = (a, db), (b, da)
            assigned = {day: [s['id'] for s in group] for group, day in assignments}
            doc['days'] = [{'date': day, 'stop_ids': assigned.get(day, [])} for day in days]
            doc['unassigned_ids'] = []

        routes, notices = [], []
        for day in doc['days']:
            for a_id, b_id in zip(day['stop_ids'], day['stop_ids'][1:]):
                a, b = by_id[a_id], by_id[b_id]
                actual = measure(a, b)
                route = {'date': day['date'], 'from_id': a_id, 'to_id': b_id, 'mode': mode,
                         'actual': actual is not None, 'path': [], 'distance_km': None, 'duration_minutes': None}
                if actual:
                    route.update({k: actual.get(k) for k in ('path', 'distance_km', 'duration_minutes')})
                    route['path'] = route.get('path') or []
                routes.append(route)
        if any(not r['actual'] for r in routes): notices.append('部分路段未取得道路数据，地图以虚线示意。')
        if doc['unassigned_ids']: notices.append(f"还有{len(doc['unassigned_ids'])}个地点待安排，更新路线不会自动插入。")
        if not weather: notices.append('当前未取得这些日期的天气，已按地点与路程安排。')
        elif any(not any(v['date']==d['date'] for v in weather.get(sid, {}).get('days', [])) for d in doc['days'] for sid in d['stop_ids']):
            notices.append('部分日期或区域暂无天气预报，未把缺失天气计入优劣。')
        if any((r.get('duration_minutes') or 0)>180 for r in routes): notices.append('部分路段交通超过3小时，请核对是否适合当天安排。')
        if any(sum(r.get('duration_minutes') or 0 for r in routes if r['date']==d['date'])>360 for d in doc['days']):
            notices.append('有日期交通合计超过6小时，尚未包含游览停留时间。')
        if any(bad_weather(v)>30 for value in weather.values() for v in value['days']):
            notices.append('部分预报有较多降水或较强风，请查看当天具体天气。')
        doc.update(routes=routes, weather=weather, notices=notices,
            route_status='partial' if any(not r['actual'] for r in routes) else 'ready',
            generated_at=datetime.now(timezone.utc).isoformat(), route_cache=dict(list(cache.items())[-160:]),
            generation_stats=counts, last_generation_request=request_id,
            arrangement='automatic' if optimize else 'manual', updated_at=datetime.now(timezone.utc).isoformat())
        return doc
