from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from math import isfinite

from roambot.domain.models import Coordinate, DailyWeather
from roambot.providers.http import ProviderHttpClient
from roambot.providers.protocols import ProviderError


class QWeatherProvider:
    def __init__(
        self,
        http: ProviderHttpClient,
        api_key: str,
        today: Callable[[], date],
    ) -> None:
        self._http = http
        self._api_key = api_key
        self._today = today

    def daily(
        self,
        coordinate: Coordinate,
        start: date,
        end: date,
    ) -> list[DailyWeather]:
        today = self._today()
        if start < today or end < start or end > today + timedelta(days=6):
            raise ProviderError(
                "forecast_unavailable",
                "所选日期超出七日天气预报范围",
            )

        payload = self._http.get_json(
            operation="weather",
            path="/v7/weather/7d",
            params={
                "location": f"{coordinate.longitude:.2f},{coordinate.latitude:.2f}",
                "lang": "zh",
                "unit": "m",
            },
            headers={"X-QW-Api-Key": self._api_key},
        )
        if payload.get("code") != "200":
            raise ProviderError("unavailable", "和风天气服务暂时不可用")
        raw_days = payload.get("daily")
        if not isinstance(raw_days, list):
            raise _bad_response()

        parsed: dict[date, DailyWeather] = {}
        seen_dates: set[date] = set()
        for raw_day in raw_days:
            if not isinstance(raw_day, dict):
                raise _bad_response()
            day = _parse_date(raw_day.get("fxDate"))
            if day in seen_dates:
                raise _bad_response()
            seen_dates.add(day)
            if start <= day <= end:
                parsed[day] = _parse_daily_weather(raw_day, day)

        required = _date_range(start, end)
        if any(day not in parsed for day in required):
            raise ProviderError(
                "forecast_unavailable",
                "所选日期的天气预报暂不可用",
            )
        return [parsed[day] for day in required]


def _parse_daily_weather(raw: dict[str, object], day: date) -> DailyWeather:
    temp_min = _number(raw.get("tempMin"))
    temp_max = _number(raw.get("tempMax"))
    if temp_min > temp_max:
        raise _bad_response()
    text_day = _text(raw.get("textDay"))
    text_night = _text(raw.get("textNight"))
    condition = text_day if text_day == text_night else f"{text_day}转{text_night}"
    wind_day = _nonnegative(raw.get("windSpeedDay"))
    wind_night = _nonnegative(raw.get("windSpeedNight"))
    humidity = _number(raw.get("humidity"))
    if not 0 <= humidity <= 100:
        raise _bad_response()

    return DailyWeather(
        date=day,
        condition=condition,
        temp_min_c=temp_min,
        temp_max_c=temp_max,
        precipitation_mm=_nonnegative(raw.get("precip")),
        wind_speed_kmh=max(wind_day, wind_night),
        humidity_percent=humidity,
        visibility_km=_nonnegative(raw.get("vis")),
        uv_index=_nonnegative(raw.get("uvIndex")),
    )


def _parse_date(raw: object) -> date:
    if not isinstance(raw, str):
        raise _bad_response()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise _bad_response() from None


def _text(raw: object) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise _bad_response()
    return raw.strip()


def _number(raw: object) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise _bad_response() from None
    if not isfinite(value):
        raise _bad_response()
    return value


def _nonnegative(raw: object) -> float:
    value = _number(raw)
    if value < 0:
        raise _bad_response()
    return value


def _date_range(start: date, end: date) -> list[date]:
    days: list[date] = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def _bad_response() -> ProviderError:
    return ProviderError("bad_response", "和风天气返回的数据格式无效")
