import json
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from unicodedata import normalize

import pytest

from roambot.domain.models import Coordinate, SceneryType
from roambot.persistence.repositories import CacheEntry
from roambot.providers.cached import (
    CACHE_TTLS,
    CachedDistanceProvider,
    CachedGeocoder,
    CachedPlaceProvider,
    CachedWeatherProvider,
    make_cache_key,
)
from roambot.providers.mock import MockProviderBundle
from roambot.providers.protocols import ProviderError
from roambot.providers.trace import ProviderEvent, ProviderTrace

NOW = datetime(2026, 7, 18, 8, 0, tzinfo=UTC)


class MemoryCache:
    def __init__(self) -> None:
        self.entries: dict[str, CacheEntry] = {}
        self.deleted: list[str] = []

    def get_fresh(self, key: str, now: datetime) -> CacheEntry | None:
        entry = self.entries.get(key)
        return entry if entry is not None and now < entry.expires_at else None

    def put(
        self,
        key: str,
        provider: str,
        operation: str,
        payload: dict[str, object],
        created_at: datetime,
        expires_at: datetime,
    ) -> None:
        self.entries[key] = CacheEntry(
            cache_key=key,
            provider=provider,
            operation=operation,
            payload_json=json.dumps(
                payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
            created_at=created_at,
            expires_at=expires_at,
        )

    def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.entries.pop(key, None)


class CountingBundle:
    def __init__(self) -> None:
        bundle = MockProviderBundle.default()
        self.bundle = bundle
        self.calls = {"geocode": 0, "search": 0, "resolve": 0, "distance": 0, "weather": 0}

    def geocode(self, address: str, city: str):
        self.calls["geocode"] += 1
        return self.bundle.geocoder.geocode(address, city)

    def search(self, center, city, scenery_types, radius_km):
        self.calls["search"] += 1
        return self.bundle.places.search(center, city, scenery_types, radius_km)

    def resolve(self, name: str, city: str):
        self.calls["resolve"] += 1
        return self.bundle.places.resolve(name, city)

    def measure(self, origins, destination):
        self.calls["distance"] += 1
        return self.bundle.distance.measure(origins, destination)

    def daily(self, coordinate, start, end):
        self.calls["weather"] += 1
        return self.bundle.weather.daily(coordinate, start, end)


def test_cache_key_uses_canonical_unicode_whitespace_and_ordered_lists() -> None:
    params = {
        "address": "  Suzhou\tRailway  Station ",
        "city": "Su\u0301zhou",
        "scenery_types": [SceneryType.LAKE, SceneryType.PARK],
        "start": date(2026, 7, 20),
    }
    canonical = {
        "schema_version": 1,
        "provider": "amap",
        "operation": "geocode",
        "params": {
            "address": "Suzhou Railway Station",
            "city": normalize("NFC", "Su\u0301zhou"),
            "scenery_types": ["lake", "park"],
            "start": "2026-07-20",
        },
    }
    expected = sha256(
        json.dumps(
            canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()

    assert make_cache_key("amap", "geocode", params) == expected
    assert "Station" not in make_cache_key("amap", "geocode", params)


def test_geocode_cache_uses_30_day_ttl_and_marks_fresh_hit() -> None:
    inner = CountingBundle()
    cache = MemoryCache()
    trace = ProviderTrace()
    provider = CachedGeocoder(inner, cache, "amap", lambda: NOW, trace)

    first = provider.geocode("苏州站", "苏州")
    second = provider.geocode("苏州站", "苏州")

    assert second == first
    assert inner.calls["geocode"] == 1
    assert ProviderEvent.CACHE in trace.events
    entry = next(iter(cache.entries.values()))
    assert entry.expires_at == NOW + CACHE_TTLS["geocode"]
    assert json.loads(entry.payload_json)["model"] == "Origin"


def test_place_search_and_resolve_use_typed_seven_day_cache_entries() -> None:
    inner = CountingBundle()
    cache = MemoryCache()
    trace = ProviderTrace()
    provider = CachedPlaceProvider(inner, cache, "amap", lambda: NOW, trace)
    center = Coordinate(longitude=120.617, latitude=31.335)

    searched = provider.search(center, "苏州", (SceneryType.LAKE, SceneryType.PARK), 50)
    resolved = provider.resolve("金鸡湖景区", "苏州")
    assert provider.search(center, "苏州", (SceneryType.LAKE, SceneryType.PARK), 50) == searched
    assert provider.resolve("金鸡湖景区", "苏州") == resolved

    assert inner.calls["search"] == 1
    assert inner.calls["resolve"] == 1
    entries = list(cache.entries.values())
    assert {json.loads(entry.payload_json)["model"] for entry in entries} == {
        "DestinationList",
        "Destination",
    }
    assert all(entry.expires_at == NOW + CACHE_TTLS["poi_search"] for entry in entries)


def test_distance_and_weather_caches_preserve_order_and_exact_ttls() -> None:
    inner = CountingBundle()
    cache = MemoryCache()
    trace = ProviderTrace()
    origin = inner.bundle.geocoder.geocode("苏州站", "苏州")
    destination = inner.bundle.places.resolve("金鸡湖景区", "苏州")
    distance = CachedDistanceProvider(inner, cache, "amap", lambda: NOW, trace)
    weather = CachedWeatherProvider(inner, cache, "qweather", lambda: NOW, trace)
    start = date(2026, 7, 20)
    end = date(2026, 7, 21)

    first_distance = distance.measure([origin], destination)
    first_weather = weather.daily(destination.coordinate, start, end)
    assert distance.measure([origin], destination) == first_distance
    assert weather.daily(destination.coordinate, start, end) == first_weather
    assert inner.calls["distance"] == 1
    assert inner.calls["weather"] == 1
    ttls = {entry.operation: entry.expires_at - NOW for entry in cache.entries.values()}
    assert ttls == {"distance": timedelta(days=1), "weather": timedelta(hours=1)}


def test_corrupt_cache_is_deleted_and_provider_errors_are_not_cached() -> None:
    inner = CountingBundle()
    cache = MemoryCache()
    trace = ProviderTrace()
    provider = CachedGeocoder(inner, cache, "amap", lambda: NOW, trace)
    key = make_cache_key("amap", "geocode", {"address": "苏州站", "city": "苏州"})
    cache.entries[key] = CacheEntry(
        key,
        "amap",
        "geocode",
        "not-json",
        NOW,
        NOW + timedelta(days=1),
    )

    assert provider.geocode("苏州站", "苏州").label == "苏州站"
    assert cache.deleted == [key]

    class Failing:
        def geocode(self, address: str, city: str):
            del address, city
            raise ProviderError("unavailable", "down")

    failed_cache = MemoryCache()
    with pytest.raises(ProviderError):
        CachedGeocoder(Failing(), failed_cache, "amap", lambda: NOW, ProviderTrace()).geocode(
            "苏州站", "苏州"
        )
    assert failed_cache.entries == {}


def test_cache_clock_requires_aware_utc() -> None:
    inner = CountingBundle()
    provider = CachedGeocoder(
        inner,
        MemoryCache(),
        "amap",
        lambda: NOW.replace(tzinfo=None),
        ProviderTrace(),
    )
    with pytest.raises(ValueError, match="aware UTC"):
        provider.geocode("苏州站", "苏州")
