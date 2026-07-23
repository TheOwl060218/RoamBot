from pathlib import Path

import pytest
from pydantic import ValidationError

from roambot.config import ProviderMode, Settings


def test_provider_settings_have_safe_mock_defaults() -> None:
    settings = Settings()

    assert settings.provider_mode is ProviderMode.MOCK
    assert settings.demo_mode is True
    assert settings.data_dir == Path("data")
    assert settings.provider_timeout_seconds == 5.0
    assert (
        settings.max_geocode_calls,
        settings.max_poi_search_calls,
        settings.max_weather_calls,
        settings.max_distance_calls,
        settings.max_llm_calls,
    ) == (3, 6, 5, 5, 1)
    assert "api_key" not in repr(settings)
    assert "master_password" not in repr(settings)


def test_live_mode_requires_live_only_settings() -> None:
    valid = {
        "provider_mode": "live",
        "demo_mode": False,
        "qweather_api_host": "https://student.qweatherapi.com",
        "llm_base_url": "https://llm.example.com",
        "llm_model": "deepseek-v4-flash",
    }

    settings = Settings(**valid)
    assert str(settings.qweather_api_host) == "https://student.qweatherapi.com/"

    for field, value in (
        ("demo_mode", True),
        ("qweather_api_host", None),
        ("qweather_api_host", "http://student.qweatherapi.com"),
        ("qweather_api_host", "https://api.qweather.com"),
        ("llm_base_url", None),
        ("llm_base_url", "http://llm.example.com"),
        ("llm_model", "  "),
    ):
        with pytest.raises(ValidationError):
            Settings(**{**valid, field: value})


def test_live_mode_accepts_llm_base_url_with_api_path_prefix() -> None:
    settings = Settings(
        provider_mode="live",
        demo_mode=False,
        qweather_api_host="https://student.qweatherapi.com",
        llm_base_url="https://llm.example.com/v1",
        llm_model="deepseek-v4-flash",
    )

    assert str(settings.llm_base_url) == "https://llm.example.com/v1"


@pytest.mark.parametrize(
    "field,value",
    [
        ("qweather_api_host", "https://user:pass@student.qweatherapi.com"),
        ("qweather_api_host", "https://student.qweatherapi.com:8443"),
        ("qweather_api_host", "https://student.qweatherapi.com/v7"),
        ("qweather_api_host", "https://student.qweatherapi.com?debug=1"),
        ("qweather_api_host", "https://student.qweatherapi.com#fragment"),
        ("llm_base_url", "https://user:pass@llm.example.com"),
        ("llm_base_url", "https://llm.example.com?debug=1"),
    ],
)
def test_live_hosts_are_https_roots_without_sensitive_url_parts(
    field: str,
    value: str,
) -> None:
    values = {
        "provider_mode": "live",
        "demo_mode": False,
        "qweather_api_host": "https://student.qweatherapi.com",
        "llm_base_url": "https://llm.example.com",
        "llm_model": "deepseek-v4-flash",
        field: value,
    }

    with pytest.raises(ValidationError):
        Settings(**values)


def test_provider_settings_forbid_unknown_constructor_fields() -> None:
    with pytest.raises(ValidationError):
        Settings(amap_api_key="not-a-real-key")
