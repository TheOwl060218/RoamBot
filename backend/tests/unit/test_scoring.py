from datetime import date

import pytest

from roambot.domain.models import DailyWeather, SceneryType
from roambot.domain.scoring import (
    aggregate_weather,
    clamp,
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


@pytest.mark.parametrize(
    ("scenery_tags", "precipitation_mm", "expected_score"),
    [
        (frozenset({SceneryType.PARK}), 0, 100),
        (frozenset({SceneryType.PARK}), 1, 90),
        (frozenset({SceneryType.PARK}), 1.01, 65),
        (frozenset({SceneryType.PARK}), 10, 65),
        (frozenset({SceneryType.PARK}), 10.01, 40),
        (frozenset({SceneryType.MUSEUM}), 0, 100),
        (frozenset({SceneryType.MUSEUM}), 1, 95),
        (frozenset({SceneryType.MUSEUM}), 1.01, 85),
        (frozenset({SceneryType.MUSEUM}), 10, 85),
        (frozenset({SceneryType.MUSEUM}), 10.01, 65),
    ],
)
def test_precipitation_thresholds_respect_boundaries_and_indoor_outdoor_behavior(
    scenery_tags: frozenset[SceneryType],
    precipitation_mm: float,
    expected_score: float,
) -> None:
    result = score_daily_weather(
        weather(precipitation_mm=precipitation_mm),
        scenery_tags,
    )

    assert result.score == expected_score


@pytest.mark.parametrize(
    ("changes", "expected_score"),
    [
        ({"temp_max_c": 28}, 100),
        ({"temp_max_c": 28.1}, 90),
        ({"temp_max_c": 32}, 90),
        ({"temp_max_c": 32.1}, 75),
        ({"temp_max_c": 35}, 75),
        ({"temp_max_c": 35.1}, 60),
        ({"temp_min_c": 18}, 100),
        ({"temp_min_c": 17.9}, 90),
        ({"temp_min_c": 10}, 90),
        ({"temp_min_c": 9.9}, 75),
        ({"temp_min_c": 0}, 75),
        ({"temp_min_c": -0.1}, 60),
    ],
)
def test_temperature_thresholds_bind_at_every_boundary(
    changes: dict[str, float], expected_score: float
) -> None:
    result = score_daily_weather(weather(**changes), frozenset({SceneryType.PARK}))

    assert result.score == expected_score


@pytest.mark.parametrize(
    ("scenery_tags", "wind_speed_kmh", "expected_score"),
    [
        (frozenset({SceneryType.PARK}), 20, 100),
        (frozenset({SceneryType.PARK}), 20.1, 90),
        (frozenset({SceneryType.PARK}), 30, 90),
        (frozenset({SceneryType.PARK}), 30.1, 75),
        (frozenset({SceneryType.PARK}), 40, 75),
        (frozenset({SceneryType.PARK}), 40.1, 60),
        (frozenset({SceneryType.MUSEUM}), 20, 100),
        (frozenset({SceneryType.MUSEUM}), 20.1, 100),
        (frozenset({SceneryType.MUSEUM}), 30, 100),
        (frozenset({SceneryType.MUSEUM}), 30.1, 90),
        (frozenset({SceneryType.MUSEUM}), 40, 90),
        (frozenset({SceneryType.MUSEUM}), 40.1, 80),
    ],
)
def test_wind_thresholds_respect_boundaries_and_indoor_outdoor_behavior(
    scenery_tags: frozenset[SceneryType],
    wind_speed_kmh: float,
    expected_score: float,
) -> None:
    result = score_daily_weather(
        weather(wind_speed_kmh=wind_speed_kmh),
        scenery_tags,
    )

    assert result.score == expected_score


@pytest.mark.parametrize(
    ("visibility_km", "expected_score"),
    [
        (10, 100),
        (9.9, 95),
        (5, 95),
        (4.9, 85),
        (2, 85),
        (1.9, 70),
    ],
)
def test_visibility_thresholds_bind_at_every_boundary(
    visibility_km: float, expected_score: float
) -> None:
    result = score_daily_weather(
        weather(visibility_km=visibility_km),
        frozenset({SceneryType.PARK}),
    )

    assert result.score == expected_score


@pytest.mark.parametrize(
    ("scenery_tags", "uv_index", "expected_score"),
    [
        (frozenset({SceneryType.PARK}), 8, 100),
        (frozenset({SceneryType.PARK}), 8.1, 90),
        (frozenset({SceneryType.MUSEUM}), 8, 100),
        (frozenset({SceneryType.MUSEUM}), 8.1, 100),
    ],
)
def test_uv_thresholds_only_affect_outdoor_scenery(
    scenery_tags: frozenset[SceneryType],
    uv_index: float,
    expected_score: float,
) -> None:
    result = score_daily_weather(weather(uv_index=uv_index), scenery_tags)

    assert result.score == expected_score


def test_score_function_exits_clamp_and_round_to_two_decimals() -> None:
    severe = weather(
        precipitation_mm=20,
        temp_max_c=36,
        wind_speed_kmh=45,
        visibility_km=1,
        uv_index=10,
    )

    assert score_daily_weather(severe, frozenset({SceneryType.PARK})).score == 0.0
    assert aggregate_weather([90, 85, 30]) == 56.83
    assert score_distance(33.333333, 100) == 66.67
    assert score_fairness([0, 2], 3) == 66.67
    assert score_popularity(rank=2, local_bonus=0.125) == clamp(96.125)


def test_single_origin_fairness_uses_same_clamp_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[float] = []

    def fake_clamp(value: float) -> float:
        calls.append(value)
        return 88.88

    monkeypatch.setattr("roambot.domain.scoring.clamp", fake_clamp)

    assert score_fairness([42], 100) == 88.88
    assert calls == [100.0]
