import json
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest

from roambot.domain.models import Coordinate
from roambot.providers.http import ProviderHttpClient
from roambot.providers.protocols import ProviderError
from roambot.providers.qweather import QWeatherProvider

FIXTURE = Path(__file__).parents[1] / "fixtures" / "qweather" / "weather_7d_success.json"
TODAY = date(2026, 7, 20)
FAKE_KEY = "qweather-test-secret"


def payload() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def provider_for(handler: object) -> QWeatherProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    http = ProviderHttpClient(
        client,
        provider="qweather",
        base_url="https://student.qweatherapi.com",
        secrets=(FAKE_KEY,),
    )
    return QWeatherProvider(http, FAKE_KEY, today=lambda: TODAY)


def test_daily_makes_one_header_authenticated_request_and_maps_dates() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.path == "/v7/weather/7d"
        assert dict(request.url.params) == {
            "location": "120.58,31.30",
            "lang": "zh",
            "unit": "m",
        }
        assert request.headers["X-QW-Api-Key"] == FAKE_KEY
        assert FAKE_KEY not in str(request.url)
        return httpx.Response(200, json=payload())

    days = provider_for(handler).daily(
        Coordinate(longitude=120.579, latitude=31.299),
        TODAY,
        TODAY + timedelta(days=1),
    )

    assert len(requests) == 1
    assert [day.date for day in days] == [TODAY, TODAY + timedelta(days=1)]
    assert days[0].condition == "晴"
    assert days[1].condition == "多云转小雨"
    assert days[1].wind_speed_kmh == 18


@pytest.mark.parametrize(
    "start,end",
    [
        (TODAY - timedelta(days=1), TODAY),
        (TODAY + timedelta(days=1), TODAY),
        (TODAY, TODAY + timedelta(days=7)),
    ],
)
def test_unsupported_date_ranges_fail_before_http(start: date, end: date) -> None:
    def forbidden(_: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP should not be called")

    with pytest.raises(ProviderError) as captured:
        provider_for(forbidden).daily(Coordinate(longitude=120, latitude=31), start, end)
    assert captured.value.code == "forecast_unavailable"


def test_provider_business_error_is_unavailable_and_sanitized() -> None:
    failed = {"code": "401", "message": FAKE_KEY}
    with pytest.raises(ProviderError) as captured:
        provider_for(lambda _: httpx.Response(200, json=failed)).daily(
            Coordinate(longitude=120, latitude=31), TODAY, TODAY
        )
    assert captured.value.code == "unavailable"
    assert FAKE_KEY not in str(captured.value)


def test_missing_requested_day_is_forecast_unavailable() -> None:
    incomplete = payload()
    incomplete["daily"] = incomplete["daily"][1:]
    with pytest.raises(ProviderError) as captured:
        provider_for(lambda _: httpx.Response(200, json=incomplete)).daily(
            Coordinate(longitude=120, latitude=31), TODAY, TODAY + timedelta(days=1)
        )
    assert captured.value.code == "forecast_unavailable"


@pytest.mark.parametrize("mutation", ["duplicate", "bad_number", "bad_date"])
def test_duplicate_or_malformed_requested_data_is_bad_response(mutation: str) -> None:
    malformed = deepcopy(payload())
    daily = malformed["daily"]
    if mutation == "duplicate":
        daily.append(deepcopy(daily[0]))
    elif mutation == "bad_number":
        daily[0]["humidity"] = "101"
    else:
        daily[0]["fxDate"] = "not-a-date"

    with pytest.raises(ProviderError) as captured:
        provider_for(lambda _: httpx.Response(200, json=malformed)).daily(
            Coordinate(longitude=120, latitude=31), TODAY, TODAY
        )
    assert captured.value.code == "bad_response"
