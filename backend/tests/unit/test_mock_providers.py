from datetime import date

import pytest

from roambot.domain.models import (
    Coordinate,
    DailyWeather,
    Destination,
    DistanceEstimate,
    GroupAccessibilityScore,
    RecommendationItem,
    SceneryType,
    ScoreBreakdown,
)
from roambot.providers.mock import MockProviderBundle
from roambot.providers.protocols import (
    DistanceProvider,
    ExplanationProvider,
    Geocoder,
    PlaceProvider,
    ProviderError,
    WeatherProvider,
)


def make_item(destination: Destination) -> RecommendationItem:
    return RecommendationItem(
        destination=destination,
        distances=[
            DistanceEstimate(
                origin_label="苏州站",
                distance_km=12.3,
                duration_minutes=28,
                estimated=False,
            )
        ],
        group_accessibility=GroupAccessibilityScore(
            average_distance_km=12.3,
            max_distance_km=12.3,
            distance_variance=0,
            distance_stddev=0,
            fairness_score=100,
        ),
        weather=[
            DailyWeather(
                date=date(2026, 7, 20),
                condition="晴",
                temp_min_c=27,
                temp_max_c=33,
                precipitation_mm=0,
                wind_speed_kmh=16,
                humidity_percent=68,
                visibility_km=18,
                uv_index=8,
            )
        ],
        daily_suitability=[],
        score=ScoreBreakdown(
            weather=85,
            distance=78,
            fairness=100,
            popularity=82,
            coverage_penalty=0,
            total=86,
        ),
        explanation="",
    )


def test_mock_bundle_returns_suzhou_vertical_slice() -> None:
    providers = MockProviderBundle.default()

    geocoder: Geocoder = providers.geocoder
    places: PlaceProvider = providers.places
    weather_provider: WeatherProvider = providers.weather

    origin = geocoder.geocode("苏州站", "苏州")
    found_places = places.search(
        center=origin.coordinate,
        city="苏州",
        scenery_types=(SceneryType.LAKE,),
        radius_km=80,
    )
    weather = weather_provider.daily(
        found_places[0].coordinate,
        date(2026, 7, 20),
        date(2026, 7, 22),
    )

    assert origin.coordinate == Coordinate(longitude=120.617, latitude=31.335)
    assert found_places[0].name == "金鸡湖景区"
    assert len(weather) == 3


def test_mock_providers_return_deterministic_ordered_data() -> None:
    providers = MockProviderBundle.default()

    places = providers.places.search(
        center=Coordinate(longitude=120.617, latitude=31.335),
        city="苏州",
        scenery_types=(SceneryType.LAKE, SceneryType.OLD_TOWN, SceneryType.MUSEUM),
        radius_km=80,
    )
    distances = providers.distance.measure(
        origins=[
            providers.geocoder.geocode("苏州站", "苏州"),
            providers.geocoder.geocode("苏州园区站", "苏州"),
        ],
        destination=places[1],
    )
    explanations = providers.explanations.explain(
        [make_item(places[0]), make_item(places[1])]
    )

    assert [place.name for place in places] == ["金鸡湖景区", "同里古镇", "苏州博物馆"]
    assert [estimate.origin_label for estimate in distances] == ["苏州站", "苏州园区站"]
    assert all(estimate.distance_km >= 0 for estimate in distances)
    assert explanations == [
        "金鸡湖景区：湖景休闲取向，分数86.0，适合当前这组行程偏好。",
        "同里古镇：古镇漫游取向，分数86.0，适合当前这组行程偏好。",
    ]


def test_mock_place_resolve_and_weather_are_stable() -> None:
    providers = MockProviderBundle.default()

    place = providers.places.resolve("穹窿山", "苏州")
    weather = providers.weather.daily(
        place.coordinate,
        date(2026, 7, 21),
        date(2026, 7, 22),
    )

    assert place.coordinate == Coordinate(longitude=120.407, latitude=31.199)
    assert [entry.date for entry in weather] == [date(2026, 7, 21), date(2026, 7, 22)]
    assert [entry.condition for entry in weather] == ["多云", "阵雨"]


@pytest.mark.parametrize(
    ("operation", "expected_message"),
    [
        (
            lambda providers: providers.geocoder.geocode("未知出发地", "苏州"),
            "未找到出发地",
        ),
        (
            lambda providers: providers.places.resolve("未知景点", "苏州"),
            "未找到指定地点",
        ),
    ],
)
def test_unknown_mock_data_raises_not_found(
    operation, expected_message: str
) -> None:
    providers = MockProviderBundle.default()

    with pytest.raises(ProviderError) as exc_info:
        operation(providers)

    assert exc_info.value.code == "not_found"
    assert str(exc_info.value) == expected_message


def test_mock_bundle_fields_match_protocol_surface() -> None:
    providers = MockProviderBundle.default()

    assert isinstance(providers.geocoder, Geocoder)
    assert isinstance(providers.places, PlaceProvider)
    assert isinstance(providers.distance, DistanceProvider)
    assert isinstance(providers.weather, WeatherProvider)
    assert isinstance(providers.explanations, ExplanationProvider)
