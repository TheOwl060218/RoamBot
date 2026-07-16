from datetime import date

from roambot.domain.models import DailyWeather, SceneryType
from roambot.domain.scoring import (
    aggregate_weather,
    score_daily_weather,
    score_distance,
    score_fairness,
    score_popularity,
)


def weather(**changes: object) -> DailyWeather:
    values: dict[str, object] = {
        "date": date(2026, 7, 20),
        "condition": "多云",
        "temp_min_c": 20,
        "temp_max_c": 27,
        "precipitation_mm": 0,
        "wind_speed_kmh": 10,
        "humidity_percent": 60,
        "visibility_km": 20,
        "uv_index": 5,
    }
    values.update(changes)
    return DailyWeather.model_validate(values)


def test_outdoor_rain_is_worse_than_museum_rain() -> None:
    rainy = weather(condition="中雨", precipitation_mm=8)
    outdoor = score_daily_weather(rainy, frozenset({SceneryType.MOUNTAIN}))
    indoor = score_daily_weather(rainy, frozenset({SceneryType.MUSEUM}))

    assert outdoor.score < indoor.score


def test_multi_day_formula_is_seventy_thirty() -> None:
    assert aggregate_weather([90, 85, 30]) == 56.83


def test_distance_and_fairness_are_bounded() -> None:
    assert score_distance(20, 100) == 80
    assert score_distance(100, 100) == 0
    assert score_fairness([30, 32, 29], 100) > score_fairness([10, 30, 90], 100)


def test_popularity_converts_rank() -> None:
    assert score_popularity(rank=1) == 100
    assert score_popularity(rank=25) == 4
