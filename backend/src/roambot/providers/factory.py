from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Protocol

import httpx

from roambot.config import ProviderMode, Settings
from roambot.providers.amap import AMapProvider
from roambot.providers.cached import (
    CachedDistanceProvider,
    CachedGeocoder,
    CachedPlaceProvider,
    CachedWeatherProvider,
    CacheStore,
)
from roambot.providers.http import ProviderHttpClient
from roambot.providers.mock import MockProviderBundle
from roambot.providers.openai_compatible import OpenAICompatibleExplanationProvider
from roambot.providers.protocols import (
    DistanceProvider,
    ExplanationProvider,
    Geocoder,
    PlaceProvider,
    WeatherProvider,
)
from roambot.providers.qweather import QWeatherProvider
from roambot.providers.trace import ProviderEvent, ProviderTrace


class ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderBundle:
    geocoder: Geocoder
    places: PlaceProvider
    distance: DistanceProvider
    weather: WeatherProvider
    explanations: ExplanationProvider
    trace: ProviderTrace


class AdapterBundle(Protocol):
    geocoder: Geocoder
    places: PlaceProvider
    distance: DistanceProvider
    weather: WeatherProvider
    explanations: ExplanationProvider


@dataclass(frozen=True)
class LiveAdapterBundle:
    geocoder: Geocoder
    places: PlaceProvider
    distance: DistanceProvider
    weather: WeatherProvider
    explanations: ExplanationProvider


class ProviderRuntime:
    def __init__(
        self,
        adapters: AdapterBundle,
        *,
        client: httpx.Client | None,
        demo: bool,
        cache_repository: CacheStore | None = None,
    ) -> None:
        self._adapters = adapters
        self._client = client
        self._demo = demo
        self._cache_repository = cache_repository

    def new_request_bundle(self) -> ProviderBundle:
        trace = ProviderTrace()
        if self._demo:
            trace.mark(ProviderEvent.DEMO)
        geocoder = self._adapters.geocoder
        places = self._adapters.places
        distance = self._adapters.distance
        weather = self._adapters.weather
        if not self._demo and self._cache_repository is not None:
            def clock() -> datetime:
                return datetime.now(UTC)

            geocoder = CachedGeocoder(
                geocoder, self._cache_repository, "amap", clock, trace
            )
            places = CachedPlaceProvider(
                places, self._cache_repository, "amap", clock, trace
            )
            distance = CachedDistanceProvider(
                distance, self._cache_repository, "amap", clock, trace
            )
            weather = CachedWeatherProvider(
                weather, self._cache_repository, "qweather", clock, trace
            )
        return ProviderBundle(
            geocoder=geocoder,
            places=places,
            distance=distance,
            weather=weather,
            explanations=self._adapters.explanations,
            trace=trace,
        )

    def close(self) -> None:
        if self._client is not None:
            self._client.close()


def build_provider_runtime(
    settings: Settings,
    vault_values: Mapping[str, str],
    cache_repository: object | None,
) -> ProviderRuntime:
    if settings.provider_mode is ProviderMode.MOCK:
        return ProviderRuntime(MockProviderBundle.default(), client=None, demo=True)

    credentials = _validated_credentials(vault_values)
    client = httpx.Client(timeout=settings.provider_timeout_seconds)
    try:
        adapters = _build_live_adapters(
            settings=settings,
            credentials=credentials,
            client=client,
            cache_repository=cache_repository,
        )
    except Exception:
        client.close()
        raise
    return ProviderRuntime(
        adapters,
        client=client,
        demo=False,
        cache_repository=cache_repository,
    )


def _validated_credentials(values: Mapping[str, str]) -> dict[str, str]:
    required = (
        ("amap_api_key", "AMap"),
        ("qweather_api_key", "QWeather"),
        ("llm_api_key", "LLM"),
    )
    credentials: dict[str, str] = {}
    for field_name, provider_name in required:
        value = values.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError(f"Missing credential for {provider_name}.")
        credentials[field_name] = value.strip()
    return credentials


def _build_live_adapters(
    *,
    settings: Settings,
    credentials: Mapping[str, str],
    client: httpx.Client,
    cache_repository: object | None,
) -> LiveAdapterBundle:
    del cache_repository
    if settings.qweather_api_host is None or settings.llm_base_url is None:
        raise ConfigurationError("Live provider hosts are not configured.")
    if settings.llm_model is None:
        raise ConfigurationError("Live LLM model is not configured.")

    amap_key = credentials["amap_api_key"]
    qweather_key = credentials["qweather_api_key"]
    llm_key = credentials["llm_api_key"]
    amap = AMapProvider(
        ProviderHttpClient(
            client,
            provider="amap",
            base_url=str(settings.amap_base_url),
            timeout=settings.provider_timeout_seconds,
            secrets=(amap_key,),
        ),
        amap_key,
    )

    def china_today() -> date:
        return datetime.now(timezone(timedelta(hours=8))).date()

    weather = QWeatherProvider(
        ProviderHttpClient(
            client,
            provider="qweather",
            base_url=str(settings.qweather_api_host),
            timeout=settings.provider_timeout_seconds,
            secrets=(qweather_key,),
        ),
        qweather_key,
        today=china_today,
    )
    explanations = OpenAICompatibleExplanationProvider(
        ProviderHttpClient(
            client,
            provider="llm",
            base_url=str(settings.llm_base_url),
            timeout=settings.provider_timeout_seconds,
            secrets=(llm_key,),
        ),
        llm_key,
        settings.llm_model,
    )
    return LiveAdapterBundle(
        geocoder=amap,
        places=amap,
        distance=amap,
        weather=weather,
        explanations=explanations,
    )
