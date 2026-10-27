from datetime import date, timedelta

from roambot.domain.models import DailyWeather, SceneryType
from roambot.domain.weather_reminders import interval_reminders


def days(*changes):
    return [
        DailyWeather(
            date=date(2026, 10, 10) + timedelta(days=i),
            condition="多云",
            temp_min_c=18,
            temp_max_c=24,
            precipitation_mm=0,
            wind_speed_kmh=10,
            humidity_percent=60,
            visibility_km=20,
            uv_index=4,
        ).model_copy(update=change)
        for i, change in enumerate(changes)
    ]


def test_stable_days_have_no_filler():
    assert interval_reminders(days({}, {}, {}), frozenset({SceneryType.LAKE})) == ["", "", ""]


def test_light_rain_has_one_continuous_range_and_keeps_a_dry_day_empty():
    notes = interval_reminders(
        days({}, {"precipitation_mm": 0.2}, {"precipitation_mm": 1}),
        frozenset({SceneryType.PARK}),
    )
    assert notes[0] == notes[2] == ""
    assert "10月11日–10月12日" in notes[1]
    assert "雨具" in notes[1]


def test_rain_condition_with_zero_rounded_amount_still_warns_without_inventing_amount():
    notes = interval_reminders(days({"condition": "小雨转多云"}), frozenset({SceneryType.PARK}))
    assert "雨具" in notes[0]
    assert "毫米" not in notes[0]


def test_continuous_wind_is_one_range_with_place_specific_impact():
    notes = interval_reminders(
        days({"wind_speed_kmh": 32}, {"wind_speed_kmh": 34}, {}), frozenset({SceneryType.LAKE})
    )
    assert "10月10日–10月11日" in notes[0]
    assert "湖边" in notes[0]
    assert notes[1] == ""


def test_temperature_trend_is_not_repeated_on_following_stable_days():
    notes = interval_reminders(
        days({}, {"temp_max_c": 18, "temp_min_c": 12}, {"temp_max_c": 18, "temp_min_c": 12}),
        frozenset({SceneryType.PARK}),
    )
    assert "降温" in notes[1]
    assert notes[0] == notes[2] == ""


def test_rain_intensification_and_easing_are_distinct_events():
    notes = interval_reminders(
        days({"precipitation_mm": 4}, {"precipitation_mm": 15}, {}), frozenset({SceneryType.MUSEUM})
    )
    assert "往返" in notes[0]
    assert "增强" in notes[1]
    assert "减弱" in notes[2]


def test_visibility_only_mentions_distant_scenery_for_relevant_places():
    forecast = days({"visibility_km": 6})
    assert "远景" in interval_reminders(forecast, frozenset({SceneryType.MOUNTAIN}))[0]
    assert interval_reminders(forecast, frozenset({SceneryType.MUSEUM})) == [""]


def test_same_heat_and_visibility_impacts_do_not_repeat_at_internal_thresholds():
    notes = interval_reminders(
        days({"temp_max_c": 34, "visibility_km": 6}, {"temp_max_c": 36, "visibility_km": 4}),
        frozenset({SceneryType.LAKE}),
    )
    assert "10月10日–10月11日" in notes[0]
    assert notes[1] == ""


def test_sustained_cold_still_reports_a_later_significant_temperature_drop():
    notes = interval_reminders(
        days({"temp_min_c": 8}, {"temp_min_c": 2}),
        frozenset({SceneryType.PARK}),
    )
    assert "气温偏低" in notes[0]
    assert "降温" in notes[1]
    assert "气温偏低" not in notes[1]
