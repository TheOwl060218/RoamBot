import pytest

from roambot.services.plans import plan_name, risk_change, weather_risk


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        ("stable", "stable", "stable"),
        ("stable", "caution", "attention"),
        ("stable", "high", "worsened"),
        ("high", "stable", "improved"),
        ("caution", "high", "worsened"),
    ],
)
def test_weather_change_has_deterministic_direction(before, after, expected):
    assert risk_change(before, after) == expected


def test_weather_risk_uses_worst_day_and_scenery_exposure():
    day = {
        "date": "2026-10-06",
        "condition": "晴",
        "temp_min_c": 20,
        "temp_max_c": 26,
        "precipitation_mm": 0,
        "wind_speed_kmh": 5,
        "humidity_percent": 60,
        "visibility_km": 15,
        "uv_index": 3,
    }
    rain = {**day, "precipitation_mm": 20}
    assert weather_risk([day], ["lake"]) == "stable"
    assert weather_risk([day, rain], ["lake"]) == "high"
    assert weather_risk([rain], ["museum"]) == "caution"


def test_default_plan_names_cover_single_range_and_future_year():
    assert plan_name("苏州", "2026-10-10", "2026-10-10", 2026) == "苏州 10.10 出行计划"
    assert plan_name("苏州", "2026-10-30", "2026-11-02", 2026) == "苏州 10.30–11.02 出行计划"
    assert plan_name("苏州", "2027-01-02", "2027-01-02", 2026) == "苏州 27.01.02 出行计划"
