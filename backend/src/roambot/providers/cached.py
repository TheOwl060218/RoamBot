from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import Any, Protocol
from unicodedata import normalize

from pydantic import TypeAdapter, ValidationError

from roambot.domain.models import (
    DailyWeather,
    Destination,
    DistanceEstimate,
    Origin,
    SceneryType,
)
from roambot.persistence.repositories import CacheEntry
from roambot.providers.protocols import (
    DistanceProvider,
    Geocoder,
    PlaceProvider,
    WeatherProvider,
)
from roambot.providers.trace import ProviderEvent, ProviderTrace

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]

CACHE_TTLS = {
    "geocode": timedelta(days=30),
    "poi_search": timedelta(days=7),
    "distance": timedelta(days=1),
    "weather": timedelta(hours=1),
}
_ORIGIN = TypeAdapter(Origin)
_DESTINATION = TypeAdapter(Destination)
_DESTINATIONS = TypeAdapter(list[Destination])
_DISTANCES = TypeAdapter(list[DistanceEstimate])
_WEATHER = TypeAdapter(list[DailyWeather])


class CacheStore(Protocol):
    def get_fresh(self, cache_key: str, now: datetime) -> CacheEntry | None: ...

    def put(
        self,
        cache_key: str,
        provider: str,
        operation: str,
        payload_json: dict[str, object],
        created_at: datetime,
        expires_at: datetime,
    ) -> None: ...

    def delete(self, cache_key: str) -> None: ...


def make_cache_key(
    provider: str,
    operation: str,
    params: Mapping[str, Any],
) -> str:
    envelope = {
        "schema_version": 1,
        "provider": provider,
        "operation": operation,
        "params": _canonicalize(dict(params)),
    }
    encoded = json.dumps(
        envelope,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


class _CachedProvider:
    def __init__(
        self,
        cache: CacheStore,
        provider: str,
        clock: Callable[[], datetime],
        trace: ProviderTrace,
    ) -> None:
        self._cache = cache
        self._provider = provider
        self._clock = clock
        self._trace = trace

    def _get(self, key: str, model_name: str, adapter: TypeAdapter[Any]) -> Any | None:
        now = self._now()
        entry = self._cache.get_fresh(key, now)
        if entry is None:
            return None
        try:
            payload = json.loads(entry.payload_json)
            if (
                not isinstance(payload, dict)
                or set(payload) != {"schema_version", "model", "value"}
                or payload["schema_version"] != 1
                or payload["model"] != model_name
            ):
                raise ValueError
            value = adapter.validate_python(payload["value"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, ValidationError):
            self._cache.delete(key)
            return None
        self._trace.mark(ProviderEvent.CACHE)
        return value

    def _put(
        self,
        key: str,
        operation: str,
        model_name: str,
        value: Any,
    ) -> None:
        now = self._now()
        adapter = _adapter_for(model_name)
        payload = {
            "schema_version": 1,
            "model": model_name,
            "value": adapter.dump_python(value, mode="json"),
        }
        self._cache.put(
            key,
            self._provider,
            operation,
            payload,
            now,
            now + CACHE_TTLS[operation],
        )

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise ValueError("cache clock must return aware UTC")
        return now.astimezone(UTC)


class CachedGeocoder(_CachedProvider):
    def __init__(
        self,
        inner: Geocoder,
        cache: CacheStore,
        provider: str,
        clock: Callable[[], datetime],
        trace: ProviderTrace,
    ) -> None:
        super().__init__(cache, provider, clock, trace)
        self._inner = inner

    def geocode(self, address: str, city: str) -> Origin:
        key = make_cache_key(
            self._provider,
            "geocode",
            {"address": address, "city": city},
        )
        cached = self._get(key, "Origin", _ORIGIN)
        if cached is not None:
            return cached
        value = self._inner.geocode(address, city)
        self._put(key, "geocode", "Origin", value)
        return value


class CachedPlaceProvider(_CachedProvider):
    def __init__(
        self,
        inner: PlaceProvider,
        cache: CacheStore,
        provider: str,
        clock: Callable[[], datetime],
        trace: ProviderTrace,
    ) -> None:
        super().__init__(cache, provider, clock, trace)
        self._inner = inner

    def search(
        self,
        center,
        city: str,
        scenery_types: tuple[SceneryType, ...],
        radius_km: float,
    ) -> list[Destination]:
        params = {
            "query_kind": "search",
            "center": _coordinate(center, 6),
            "city": city,
            "scenery_types": list(scenery_types),
            "radius_km": f"{radius_km:.3f}",
        }
        key = make_cache_key(self._provider, "poi_search", params)
        cached = self._get(key, "DestinationList", _DESTINATIONS)
        if cached:
            return cached
        if cached == []:
            self._cache.delete(key)
        value = self._inner.search(center, city, scenery_types, radius_km)
        if value:
            self._put(key, "poi_search", "DestinationList", value)
        return value

    def resolve(self, name: str, city: str) -> Destination:
        key = make_cache_key(
            self._provider,
            "poi_search",
            {"query_kind": "resolve", "name": name, "city": city},
        )
        cached = self._get(key, "Destination", _DESTINATION)
        if cached is not None:
            return cached
        value = self._inner.resolve(name, city)
        self._put(key, "poi_search", "Destination", value)
        return value


class CachedDistanceProvider(_CachedProvider):
    def __init__(
        self,
        inner: DistanceProvider,
        cache: CacheStore,
        provider: str,
        clock: Callable[[], datetime],
        trace: ProviderTrace,
    ) -> None:
        super().__init__(cache, provider, clock, trace)
        self._inner = inner

    def measure(self, origins, destination: Destination) -> list[DistanceEstimate]:
        key = make_cache_key(
            self._provider,
            "distance",
            {
                "origins": [_coordinate(origin.coordinate, 6) for origin in origins],
                "destination": _coordinate(destination.coordinate, 6),
                "type": "driving",
            },
        )
        cached = self._get(key, "DistanceEstimateList", _DISTANCES)
        if cached is not None:
            return cached
        value = self._inner.measure(origins, destination)
        self._put(key, "distance", "DistanceEstimateList", value)
        return value


class CachedWeatherProvider(_CachedProvider):
    def __init__(
        self,
        inner: WeatherProvider,
        cache: CacheStore,
        provider: str,
        clock: Callable[[], datetime],
        trace: ProviderTrace,
    ) -> None:
        super().__init__(cache, provider, clock, trace)
        self._inner = inner

    def daily(self, coordinate, start: date, end: date) -> list[DailyWeather]:
        key = make_cache_key(
            self._provider,
            "weather",
            {
                "coordinate": _coordinate(coordinate, 2),
                "start": start,
                "end": end,
                "lang": "zh",
                "unit": "m",
            },
        )
        cached = self._get(key, "DailyWeatherList", _WEATHER)
        if cached is not None:
            return cached
        value = self._inner.daily(coordinate, start, end)
        self._put(key, "weather", "DailyWeatherList", value)
        return value


def _adapter_for(model_name: str) -> TypeAdapter[Any]:
    return {
        "Origin": _ORIGIN,
        "Destination": _DESTINATION,
        "DestinationList": _DESTINATIONS,
        "DistanceEstimateList": _DISTANCES,
        "DailyWeatherList": _WEATHER,
    }[model_name]


def _canonicalize(value: Any) -> JsonValue:
    if isinstance(value, str):
        return " ".join(normalize("NFC", value).strip().split())
    if isinstance(value, Enum):
        return _canonicalize(value.value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _canonicalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    raise TypeError(f"unsupported cache-key value: {type(value).__name__}")


def _coordinate(coordinate, places: int) -> str:
    return f"{coordinate.longitude:.{places}f},{coordinate.latitude:.{places}f}"
