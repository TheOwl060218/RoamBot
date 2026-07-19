from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from roambot.cli import app
from roambot.domain.models import (
    Coordinate,
    DailyWeather,
    Destination,
    DistanceEstimate,
    Origin,
)
from roambot.providers.factory import ProviderBundle
from roambot.providers.protocols import ProviderError
from roambot.providers.trace import ProviderTrace
from roambot.security.vault import CredentialVault

MASTER_PASSWORD = "smoke-master-password"
SECRETS = {
    "amap_api_key": "smoke-amap-secret",
    "qweather_api_key": "smoke-qweather-secret",
    "llm_api_key": "smoke-llm-secret",
}
NOW = datetime(2026, 7, 18, 8, 30, tzinfo=UTC)


class SmokeAdapters:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.origin = Origin(
            label="Suzhou Railway Station",
            address="public landmark",
            coordinate=Coordinate(longitude=120.617, latitude=31.335),
        )
        self.destination = Destination(
            provider_id="amap:jinji-lake",
            name="Jinji Lake Scenic Area",
            address="public destination",
            city="Suzhou",
            coordinate=Coordinate(longitude=120.704, latitude=31.315),
            type_name="scenic area",
            type_code="test",
            popularity_rank=1,
        )

    def geocode(self, address: str, city: str) -> Origin:
        self.calls.append("geocode")
        assert address and city
        return self.origin

    def search(self, *args: object, **kwargs: object) -> list[Destination]:
        raise AssertionError("smoke must not search for multiple POIs")

    def resolve(self, name: str, city: str) -> Destination:
        self.calls.append("resolve")
        assert name and city
        return self.destination

    def measure(
        self, origins: list[Origin], destination: Destination
    ) -> list[DistanceEstimate]:
        self.calls.append("distance")
        assert origins == [self.origin]
        assert destination == self.destination
        return [
            DistanceEstimate(
                origin_label=self.origin.label,
                distance_km=8.25,
                duration_minutes=22,
            )
        ]

    def daily(
        self, coordinate: Coordinate, start: date, end: date
    ) -> list[DailyWeather]:
        self.calls.append("weather")
        assert coordinate == self.destination.coordinate
        assert end - start == timedelta(days=6)
        return [
            DailyWeather(
                date=start + timedelta(days=offset),
                condition="clear",
                temp_min_c=24,
                temp_max_c=31,
                precipitation_mm=0,
                wind_speed_kmh=12,
                humidity_percent=60,
                visibility_km=18,
                uv_index=7,
            )
            for offset in range(7)
        ]

    def explain(self, items: list[object]) -> list[str]:
        self.calls.append("llm")
        assert len(items) == 1
        return ["A public synthetic recommendation explanation for smoke testing."]


class FakeRuntime:
    def __init__(self, adapters: SmokeAdapters) -> None:
        self.adapters = adapters
        self.closed = False

    def new_request_bundle(self) -> ProviderBundle:
        return ProviderBundle(
            geocoder=self.adapters,
            places=self.adapters,
            distance=self.adapters,
            weather=self.adapters,
            explanations=self.adapters,
            trace=ProviderTrace(),
        )

    def close(self) -> None:
        self.closed = True


def configure_live_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ROAMBOT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ROAMBOT_PROVIDER_MODE", "live")
    monkeypatch.setenv("ROAMBOT_DEMO_MODE", "false")
    monkeypatch.setenv(
        "ROAMBOT_QWEATHER_API_HOST", "https://student.qweatherapi.com"
    )
    monkeypatch.setenv("ROAMBOT_LLM_BASE_URL", "https://llm.example.com")
    monkeypatch.setenv("ROAMBOT_LLM_MODEL", "test-model")


def install_fake_runtime(
    adapters: SmokeAdapters, monkeypatch: pytest.MonkeyPatch
) -> FakeRuntime:
    runtime = FakeRuntime(adapters)
    monkeypatch.setattr("roambot.cli.build_provider_runtime", lambda *_args, **_kwargs: runtime)
    monkeypatch.setattr("roambot.cli._now", lambda: NOW)
    monkeypatch.setattr(
        "roambot.cli.typer.prompt",
        lambda *args, **kwargs: MASTER_PASSWORD,
    )
    return runtime


def test_smoke_runs_fixed_five_call_sequence_without_printing_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_live_environment(tmp_path, monkeypatch)
    CredentialVault(tmp_path / "credentials.vault").create(MASTER_PASSWORD, SECRETS)
    adapters = SmokeAdapters()
    runtime = install_fake_runtime(adapters, monkeypatch)
    prompt_options: list[dict[str, object]] = []

    def hidden_prompt(*args: object, **kwargs: object) -> str:
        prompt_options.append(kwargs)
        return MASTER_PASSWORD

    monkeypatch.setattr("roambot.cli.typer.prompt", hidden_prompt)

    result = CliRunner().invoke(app, ["providers", "smoke"])

    assert result.exit_code == 0, (
        f"{result.output}\ncalls={adapters.calls!r} closed={runtime.closed}"
    )
    assert adapters.calls == ["geocode", "resolve", "distance", "weather", "llm"]
    assert runtime.closed
    assert "amap: ok calls=3" in result.output
    assert "qweather: ok calls=1" in result.output
    assert "llm: ok calls=1" in result.output
    assert "cache: miss" in result.output
    assert "candidate_count: 1" in result.output
    assert "generated_at: 2026-07-18T08:30:00+00:00" in result.output
    assert prompt_options and prompt_options[0]["hide_input"] is True
    for secret in (MASTER_PASSWORD, *SECRETS.values()):
        assert secret not in result.output
    assert "Authorization" not in result.output
    assert "X-QW-Api-Key" not in result.output
    assert "https://" not in result.output


def test_smoke_failure_prints_only_provider_and_sanitized_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_live_environment(tmp_path, monkeypatch)
    CredentialVault(tmp_path / "credentials.vault").create(
        MASTER_PASSWORD,
        {"qweather_api_key": SECRETS["qweather_api_key"]},
    )
    adapters = SmokeAdapters()
    install_fake_runtime(adapters, monkeypatch)
    sensitive_response = "upstream exposed https://secret.invalid and smoke-qweather-secret"

    def fail_weather(*args: object, **kwargs: object) -> list[DailyWeather]:
        raise ProviderError("unavailable", sensitive_response)

    monkeypatch.setattr(adapters, "daily", fail_weather)

    result = CliRunner().invoke(app, ["providers", "smoke", "--only", "qweather"])

    assert result.exit_code == 1
    assert result.output.strip() == "qweather: failed code=unavailable"
    assert sensitive_response not in result.output
    assert SECRETS["qweather_api_key"] not in result.output


@pytest.mark.parametrize(
    ("arguments", "expected_calls"),
    [
        (["--only", "amap"], ["geocode", "resolve", "distance"]),
        (["--only", "qweather"], ["weather"]),
        (["--only", "llm"], ["llm"]),
        (["--skip-llm"], ["geocode", "resolve", "distance", "weather"]),
    ],
)
def test_smoke_selection_is_bounded_and_accepts_missing_unselected_keys(
    arguments: list[str],
    expected_calls: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_live_environment(tmp_path, monkeypatch)
    selected = arguments[-1] if arguments[0] == "--only" else None
    credentials = {
        name: value
        for name, value in SECRETS.items()
        if selected is None or name.startswith(selected)
    }
    CredentialVault(tmp_path / "credentials.vault").create(MASTER_PASSWORD, credentials)
    adapters = SmokeAdapters()
    install_fake_runtime(adapters, monkeypatch)

    result = CliRunner().invoke(app, ["providers", "smoke", *arguments])

    assert result.exit_code == 0, result.output
    assert adapters.calls == expected_calls
    assert sum(f"{provider}:" in result.output for provider in ("amap", "qweather", "llm")) == 3
