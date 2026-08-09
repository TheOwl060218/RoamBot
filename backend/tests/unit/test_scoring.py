from datetime import date

import pytest

import roambot.domain.scoring as scoring
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


def test_extreme_heat_penalty_distinguishes_outdoor_mixed_and_indoor() -> None:
    hot = weather(condition="Sunny", temp_max_c=36)

    outdoor = score_daily_weather(hot, frozenset({SceneryType.LAKE}))
    mixed = score_daily_weather(
        hot,
        frozenset({SceneryType.LAKE, SceneryType.MUSEUM}),
    )
    indoor = score_daily_weather(hot, frozenset({SceneryType.MUSEUM}))

    assert [outdoor.score, mixed.score, indoor.score] == [60, 70, 85]


@pytest.mark.parametrize(
    ("changes", "expected_scores"),
    [
        ({"precipitation_mm": 8}, [65, 75, 85]),
        ({"wind_speed_kmh": 35}, [75, 82, 90]),
        ({"uv_index": 9}, [90, 95, 100]),
    ],
)
def test_weather_factors_use_outdoor_mixed_indoor_penalty_matrix(
    changes: dict[str, float], expected_scores: list[float]
) -> None:
    day = weather(**changes)
    scores = [
        score_daily_weather(day, frozenset({SceneryType.PARK})).score,
        score_daily_weather(
            day,
            frozenset({SceneryType.PARK, SceneryType.MUSEUM}),
        ).score,
        score_daily_weather(day, frozenset({SceneryType.MUSEUM})).score,
    ]

    assert scores == expected_scores


@pytest.mark.parametrize(
    ("day", "tags", "expected_status"),
    [
        (weather(), frozenset({SceneryType.PARK}), "suitable"),
        (
            weather(condition="Sunny", temp_max_c=36),
            frozenset({SceneryType.LAKE}),
            "caution",
        ),
        (
            weather(condition="Heavy rain", precipitation_mm=20),
            frozenset({SceneryType.LAKE}),
            "not_recommended",
        ),
    ],
)
def test_daily_weather_exposes_explicit_travel_advice_status(
    day: DailyWeather,
    tags: frozenset[SceneryType],
    expected_status: str,
) -> None:
    result = score_daily_weather(day, tags)

    assert result.status == expected_status


def test_daily_weather_summary_uses_facts_and_hides_internal_penalties() -> None:
    result = score_daily_weather(
        weather(condition="Sunny", temp_max_c=36),
        frozenset({SceneryType.LAKE}),
    )

    assert "7月20日" in result.summary
    assert "最高温度预计达到36℃" in result.summary
    assert "户外" in result.summary
    assert "防暑" in result.summary
    assert "-40" not in result.summary
    assert all("-40" not in reason for reason in result.reasons)


def test_indoor_heat_summary_distinguishes_visit_from_travel_to_venue() -> None:
    result = score_daily_weather(
        weather(temp_min_c=28, temp_max_c=35),
        frozenset({SceneryType.MUSEUM}),
    )

    assert "室内参观受高温影响较小" not in result.summary
    assert "往返途中" in result.summary
    assert "防暑" in result.summary or "防晒" in result.summary
    assert "室内场景体感可能不舒适" not in result.summary


def test_multi_day_formula_is_seventy_thirty() -> None:
    assert aggregate_weather([90, 85, 30]) == 56.83


def test_distance_and_fairness_are_bounded() -> None:
    assert score_distance(20, 100) == 80
    assert score_distance(100, 100) == 0
    assert score_fairness([30, 32, 29], 100) > score_fairness([10, 30, 90], 100)


def test_fairness_uses_relative_burden_instead_of_absolute_trip_limit() -> None:
    assert score_fairness([20, 50], 100) == 40
    assert score_fairness([2, 5], 10) == 40


def test_fairness_combines_relative_time_and_distance_burden() -> None:
    assert score_fairness(
        [38.94, 15.06],
        50,
        durations_minutes=[71, 52],
    ) == 62.87


def test_popularity_converts_rank() -> None:
    assert score_popularity(rank=1) == 100
    assert score_popularity(rank=25) == 4


def test_rating_converts_five_point_value_to_internal_scale() -> None:
    assert scoring.score_rating(4.7) == 94

    with pytest.raises(ValueError):
        scoring.score_rating(5.1)


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
    assert score_fairness([0, 2], 3) == 0
    assert score_popularity(rank=2, local_bonus=0.125) == clamp(96.125)


def test_single_origin_fairness_uses_same_clamp_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[float] = []

    def fake_clamp(value: float) -> float:
        calls.append(value)
        return 88.88

    monkeypatch.setattr("roambot.domain.scoring.clamp", fake_clamp)

    assert score_fairness([42], 100) == 88.88
    assert calls == [100.0]
