from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx

from roambot.config import ProviderMode, Settings
from roambot.providers.mock import MockProviderBundle
from roambot.providers.protocols import (
    DistanceProvider,
    ExplanationProvider,
    Geocoder,
    PlaceProvider,
    WeatherProvider,
)


class ConfigurationError(RuntimeError):
    pass


@dataclass
class RequestTrace:
    events: set[str] = field(default_factory=set)

    def mark(self, event: str) -> None:
        self.events.add(event)


@dataclass(frozen=True)
class ProviderBundle:
    geocoder: Geocoder
    places: PlaceProvider
    distance: DistanceProvider
    weather: WeatherProvider
    explanations: ExplanationProvider
    trace: RequestTrace


class ProviderRuntime:
    def __init__(
        self,
        adapters: MockProviderBundle,
        *,
        client: httpx.Client | None,
        demo: bool,
    ) -> None:
        self._adapters = adapters
        self._client = client
        self._demo = demo

    def new_request_bundle(self) -> ProviderBundle:
        trace = RequestTrace()
        if self._demo:
            trace.mark("demo")
        return ProviderBundle(
            geocoder=self._adapters.geocoder,
            places=self._adapters.places,
            distance=self._adapters.distance,
            weather=self._adapters.weather,
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
    return ProviderRuntime(adapters, client=client, demo=False)


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


def _build_live_adapters(**_: Any) -> MockProviderBundle:
    raise ConfigurationError("Live provider adapters are not available yet.")
