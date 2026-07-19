from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from enum import StrEnum
from typing import Annotated

import typer
from pydantic import ValidationError

from roambot.config import ProviderMode, Settings
from roambot.domain.models import (
    Coordinate,
    DailySuitability,
    DailyWeather,
    Destination,
    DistanceEstimate,
    GroupAccessibilityScore,
    RecommendationItem,
    SceneryType,
    ScoreBreakdown,
)
from roambot.persistence.database import create_engine_and_session_factory, initialize_schema
from roambot.persistence.repositories import CacheRepository
from roambot.providers.factory import (
    ConfigurationError,
    ProviderBundle,
    build_provider_runtime,
)
from roambot.providers.protocols import ProviderError
from roambot.providers.trace import ProviderEvent
from roambot.security.vault import CredentialVault, VaultAuthenticationError

app = typer.Typer(no_args_is_help=True)
credentials_app = typer.Typer(no_args_is_help=True)
providers_app = typer.Typer(no_args_is_help=True)
app.add_typer(credentials_app, name="credentials")
app.add_typer(providers_app, name="providers")

_SERVICES = {
    "amap": "amap_api_key",
    "qweather": "qweather_api_key",
    "llm": "llm_api_key",
}
_SKIPPED_CREDENTIAL = "roambot-smoke-not-selected"
_PUBLIC_CITY = "苏州"
_PUBLIC_ORIGIN = "苏州站"
_PUBLIC_DESTINATION = "金鸡湖景区"
_PUBLIC_DESTINATION_COORDINATE = Coordinate(longitude=120.704, latitude=31.315)


class SmokeProvider(StrEnum):
    AMAP = "amap"
    QWEATHER = "qweather"
    LLM = "llm"


@dataclass(frozen=True)
class SmokeReport:
    selected: frozenset[SmokeProvider]
    cache_state: str
    candidate_count: int
    generated_at: datetime


class SmokeStepError(RuntimeError):
    def __init__(self, provider: SmokeProvider, code: str) -> None:
        super().__init__(code)
        self.provider = provider
        self.code = code


def _vault() -> CredentialVault:
    return CredentialVault(Settings().data_dir / "credentials.vault")


def _master_password(*, confirmation: bool = False) -> str:
    return typer.prompt("主密码", hide_input=True, confirmation_prompt=confirmation)


def _authentication_failure() -> None:
    typer.echo("Unable to authenticate credential vault.", err=True)
    raise typer.Exit(code=1)


def _existing_vault() -> CredentialVault:
    vault = _vault()
    if not vault.path.exists():
        typer.echo("Credential vault has not been initialized.", err=True)
        raise typer.Exit(code=1)
    return vault


def _status_line(service: str, configured: bool) -> None:
    typer.echo(f"{service}: {'configured' if configured else 'unconfigured'}")


def _now() -> datetime:
    return datetime.now(UTC)


def _selected_providers(
    only: SmokeProvider | None,
    skip_llm: bool,
) -> frozenset[SmokeProvider]:
    if only is not None:
        if only is SmokeProvider.LLM and skip_llm:
            typer.echo("--only llm cannot be combined with --skip-llm.", err=True)
            raise typer.Exit(code=2)
        return frozenset({only})
    selected = {SmokeProvider.AMAP, SmokeProvider.QWEATHER}
    if not skip_llm:
        selected.add(SmokeProvider.LLM)
    return frozenset(selected)


def _runtime_credentials(
    values: dict[str, str | None],
    selected: frozenset[SmokeProvider],
) -> dict[str, str]:
    credentials: dict[str, str] = {}
    for service, credential_name in _SERVICES.items():
        value = values.get(credential_name)
        provider = SmokeProvider(service)
        if provider in selected and (not isinstance(value, str) or not value.strip()):
            typer.echo(f"{service}: credential is not configured.", err=True)
            raise typer.Exit(code=1)
        credentials[credential_name] = (
            value.strip() if isinstance(value, str) and value.strip() else _SKIPPED_CREDENTIAL
        )
    return credentials


def _call[T](provider: SmokeProvider, operation: Callable[[], T]) -> T:
    try:
        return operation()
    except ProviderError as exc:
        raise SmokeStepError(provider, exc.code) from None
    except Exception:
        raise SmokeStepError(provider, "unexpected_error") from None


def _synthetic_weather(day: date) -> DailyWeather:
    return DailyWeather(
        date=day,
        condition="smoke fixture",
        temp_min_c=24,
        temp_max_c=31,
        precipitation_mm=0,
        wind_speed_kmh=12,
        humidity_percent=60,
        visibility_km=18,
        uv_index=7,
    )


def _synthetic_destination() -> Destination:
    return Destination(
        provider_id="smoke:jinji-lake",
        name=_PUBLIC_DESTINATION,
        address="public smoke destination",
        city=_PUBLIC_CITY,
        coordinate=_PUBLIC_DESTINATION_COORDINATE,
        type_name="scenic area",
        type_code="smoke",
        scenery_tags=frozenset({SceneryType.LAKE}),
        popularity_rank=1,
    )


def _synthetic_item(
    destination: Destination,
    distances: list[DistanceEstimate],
    weather: DailyWeather,
) -> RecommendationItem:
    if not distances:
        distances = [
            DistanceEstimate(
                origin_label="public smoke origin",
                distance_km=8.0,
                duration_minutes=20,
            )
        ]
    distance_values = [estimate.distance_km for estimate in distances]
    average_distance = sum(distance_values) / len(distance_values)
    return RecommendationItem(
        destination=destination,
        distances=distances,
        group_accessibility=GroupAccessibilityScore(
            average_distance_km=average_distance,
            max_distance_km=max(distance_values),
            distance_variance=0,
            distance_stddev=0,
            fairness_score=100,
        ),
        weather=[weather],
        daily_suitability=[
            DailySuitability(date=weather.date, score=85, reasons=["smoke fixture"])
        ],
        score=ScoreBreakdown(
            weather=85,
            distance=80,
            fairness=100,
            popularity=90,
            coverage_penalty=0,
            total=86,
        ),
        explanation="",
    )


def _run_provider_smoke(
    bundle: ProviderBundle,
    selected: frozenset[SmokeProvider],
) -> SmokeReport:
    today = _now().astimezone(timezone(timedelta(hours=8))).date()
    destination = _synthetic_destination()
    distances: list[DistanceEstimate] = []
    weather = _synthetic_weather(today + timedelta(days=1))

    if SmokeProvider.AMAP in selected:
        origin = _call(
            SmokeProvider.AMAP,
            lambda: bundle.geocoder.geocode(_PUBLIC_ORIGIN, _PUBLIC_CITY),
        )
        destination = _call(
            SmokeProvider.AMAP,
            lambda: bundle.places.resolve(_PUBLIC_DESTINATION, _PUBLIC_CITY),
        )
        distances = _call(
            SmokeProvider.AMAP,
            lambda: bundle.distance.measure([origin], destination),
        )

    if SmokeProvider.QWEATHER in selected:
        days = _call(
            SmokeProvider.QWEATHER,
            lambda: bundle.weather.daily(
                destination.coordinate,
                today,
                today + timedelta(days=6),
            ),
        )
        weather = next((day for day in days if day.date > today), days[0] if days else None)
        if weather is None:
            raise SmokeStepError(SmokeProvider.QWEATHER, "forecast_unavailable")

    if SmokeProvider.LLM in selected:
        item = _synthetic_item(destination, distances, weather)
        explanations = _call(
            SmokeProvider.LLM,
            lambda: bundle.explanations.explain([item]),
        )
        if not isinstance(explanations, list) or len(explanations) != 1:
            raise SmokeStepError(SmokeProvider.LLM, "bad_response")

    cache_state = "disabled"
    if selected & {SmokeProvider.AMAP, SmokeProvider.QWEATHER}:
        cache_state = "hit" if ProviderEvent.CACHE in bundle.trace.events else "miss"
    return SmokeReport(
        selected=selected,
        cache_state=cache_state,
        candidate_count=1,
        generated_at=_now(),
    )


def _print_smoke_report(report: SmokeReport) -> None:
    call_counts = {
        SmokeProvider.AMAP: 3,
        SmokeProvider.QWEATHER: 1,
        SmokeProvider.LLM: 1,
    }
    for provider in SmokeProvider:
        selected = provider in report.selected
        status = "ok" if selected else "skipped"
        calls = call_counts[provider] if selected else 0
        typer.echo(f"{provider.value}: {status} calls={calls}")
    typer.echo(f"cache: {report.cache_state}")
    typer.echo(f"candidate_count: {report.candidate_count}")
    typer.echo(f"generated_at: {report.generated_at.isoformat()}")


@providers_app.command()
def smoke(
    only: Annotated[SmokeProvider | None, typer.Option("--only")] = None,
    skip_llm: Annotated[bool, typer.Option("--skip-llm")] = False,
) -> None:
    selected = _selected_providers(only, skip_llm)
    try:
        settings = Settings()
    except ValidationError:
        typer.echo("Provider smoke configuration is invalid.", err=True)
        raise typer.Exit(code=1) from None
    if settings.provider_mode is not ProviderMode.LIVE:
        typer.echo("Provider smoke requires ROAMBOT_PROVIDER_MODE=live.", err=True)
        raise typer.Exit(code=1)

    vault = _existing_vault()
    try:
        values = vault.unlock(_master_password())
    except VaultAuthenticationError:
        _authentication_failure()
    credentials = _runtime_credentials(values, selected)

    engine = None
    try:
        engine, session_factory = create_engine_and_session_factory(settings.database_path)
        initialize_schema(engine)
        with session_factory() as db:
            runtime = build_provider_runtime(
                settings,
                credentials,
                cache_repository=CacheRepository(db),
            )
            try:
                report = _run_provider_smoke(runtime.new_request_bundle(), selected)
                db.commit()
            finally:
                runtime.close()
    except SmokeStepError as exc:
        typer.echo(
            f"{exc.provider.value}: failed code={exc.code}",
            err=True,
        )
        raise typer.Exit(code=1) from None
    except ConfigurationError:
        typer.echo("Provider smoke runtime is not configured.", err=True)
        raise typer.Exit(code=1) from None
    except Exception:
        typer.echo("Provider smoke failed code=unexpected_error.", err=True)
        raise typer.Exit(code=1) from None
    finally:
        if engine is not None:
            engine.dispose()

    _print_smoke_report(report)


@credentials_app.command()
def init() -> None:
    vault = _vault()
    if vault.path.exists():
        typer.echo("Credential vault already exists.", err=True)
        raise typer.Exit(code=1)
    vault.create(_master_password(confirmation=True))
    typer.echo("Credential vault initialized.")


@credentials_app.command()
def status() -> None:
    vault = _vault()
    if not vault.path.exists():
        for service in _SERVICES:
            _status_line(service, False)
        return
    try:
        credentials = vault.unlock(_master_password())
    except VaultAuthenticationError:
        _authentication_failure()
    for service, credential_name in _SERVICES.items():
        _status_line(service, credentials[credential_name] is not None)


@credentials_app.command("set")
def set_credential(service: str) -> None:
    credential_name = _SERVICES.get(service)
    if credential_name is None:
        typer.echo("Unsupported credential service.", err=True)
        raise typer.Exit(code=1)
    vault = _existing_vault()
    try:
        vault.update(
            _master_password(),
            credential_name,
            typer.prompt(f"{service} API key", hide_input=True),
        )
    except VaultAuthenticationError:
        _authentication_failure()
    typer.echo(f"{service}: configured")


@credentials_app.command()
def clear(service: str) -> None:
    credential_name = _SERVICES.get(service)
    if credential_name is None:
        typer.echo("Unsupported credential service.", err=True)
        raise typer.Exit(code=1)
    vault = _existing_vault()
    try:
        vault.clear(_master_password(), credential_name)
    except VaultAuthenticationError:
        _authentication_failure()
    typer.echo(f"{service}: unconfigured")


@credentials_app.command()
def reset() -> None:
    confirmation = typer.prompt("Type RESET-CREDENTIALS to confirm")
    if confirmation != "RESET-CREDENTIALS":
        typer.echo("Credential reset cancelled.", err=True)
        raise typer.Exit(code=1)
    vault = _vault()
    try:
        vault.reset()
    except VaultAuthenticationError:
        typer.echo("Unable to reset credential vault.", err=True)
        raise typer.Exit(code=1) from None
    typer.echo("Credential vault reset.")
