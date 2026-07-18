from collections.abc import Iterator, Mapping

import pytest
from fastapi.testclient import TestClient

from roambot.config import Settings
from roambot.main import create_app
from roambot.providers import factory
from roambot.providers.factory import ConfigurationError, build_provider_runtime
from roambot.providers.mock import MockProviderBundle
from roambot.providers.protocols import (
    DistanceProvider,
    ExplanationProvider,
    Geocoder,
    PlaceProvider,
    WeatherProvider,
)


class ExplodingValues(Mapping[str, str]):
    def __getitem__(self, key: str) -> str:
        raise AssertionError(f"mock mode read credential {key}")

    def __iter__(self) -> Iterator[str]:
        raise AssertionError("mock mode enumerated credentials")

    def __len__(self) -> int:
        raise AssertionError("mock mode counted credentials")


def live_settings() -> Settings:
    return Settings(
        provider_mode="live",
        demo_mode=False,
        qweather_api_host="https://student.qweatherapi.com",
        llm_base_url="https://llm.example.com",
        llm_model="deepseek-v4-flash",
    )


def test_mock_runtime_uses_deterministic_bundle_without_credentials_or_cache() -> None:
    runtime = build_provider_runtime(Settings(), ExplodingValues(), cache_repository=None)

    first = runtime.new_request_bundle()
    second = runtime.new_request_bundle()

    assert first.trace is not second.trace
    assert first.trace.events == {"demo"}
    assert isinstance(first.geocoder, Geocoder)
    assert isinstance(first.places, PlaceProvider)
    assert isinstance(first.distance, DistanceProvider)
    assert isinstance(first.weather, WeatherProvider)
    assert isinstance(first.explanations, ExplanationProvider)


@pytest.mark.parametrize(
    "missing,provider_name",
    [
        ("amap_api_key", "AMap"),
        ("qweather_api_key", "QWeather"),
        ("llm_api_key", "LLM"),
    ],
)
def test_live_runtime_reports_only_the_missing_provider(
    missing: str,
    provider_name: str,
) -> None:
    fake_values = {
        "amap_api_key": "amap-sensitive-value",
        "qweather_api_key": "weather-sensitive-value",
        "llm_api_key": "llm-sensitive-value",
    }
    fake_values[missing] = " "

    with pytest.raises(ConfigurationError) as captured:
        build_provider_runtime(live_settings(), fake_values, cache_repository=object())

    message = str(captured.value)
    assert provider_name in message
    assert all(value.strip() not in message for value in fake_values.values() if value.strip())


def test_live_runtime_adapters_satisfy_protocols_and_trace_is_request_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock = MockProviderBundle.default()
    monkeypatch.setattr(factory, "_build_live_adapters", lambda **_: mock)
    runtime = build_provider_runtime(
        live_settings(),
        {
            "amap_api_key": "amap-sensitive-value",
            "qweather_api_key": "weather-sensitive-value",
            "llm_api_key": "llm-sensitive-value",
        },
        cache_repository=object(),
    )

    try:
        first = runtime.new_request_bundle()
        second = runtime.new_request_bundle()
        assert first.trace is not second.trace
        assert first.trace.events == set()
        assert isinstance(first.geocoder, Geocoder)
        assert isinstance(first.places, PlaceProvider)
        assert isinstance(first.distance, DistanceProvider)
        assert isinstance(first.weather, WeatherProvider)
        assert isinstance(first.explanations, ExplanationProvider)
    finally:
        runtime.close()


def test_create_app_accepts_explicit_mock_settings_without_a_vault() -> None:
    with TestClient(create_app(Settings(provider_mode="mock"))) as client:
        assert client.get("/api/v1/health").json() == {"status": "ready"}
