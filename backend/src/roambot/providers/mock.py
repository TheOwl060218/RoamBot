from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from math import asin, cos, radians, sin, sqrt

from roambot.domain.models import (
    Coordinate,
    DailyWeather,
    Destination,
    DistanceEstimate,
    Origin,
    RecommendationItem,
    SceneryType,
)
from roambot.providers.protocols import ProviderError


def _normalize_text(value: str) -> str:
    return value.strip()


def _haversine_km(start: Coordinate, end: Coordinate) -> float:
    earth_radius_km = 6371.0
    lon1 = radians(start.longitude)
    lat1 = radians(start.latitude)
    lon2 = radians(end.longitude)
    lat2 = radians(end.latitude)
    delta_lon = lon2 - lon1
    delta_lat = lat2 - lat1
    hav = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return 2 * earth_radius_km * asin(sqrt(hav))


ORIGINS: dict[tuple[str, str], Origin] = {
    ("苏州站", "苏州"): Origin(
        label="苏州站",
        address="苏州站",
        coordinate=Coordinate(longitude=120.617, latitude=31.335),
    ),
    ("苏州园区站", "苏州"): Origin(
        label="苏州园区站",
        address="苏州园区站",
        coordinate=Coordinate(longitude=120.706, latitude=31.374),
    ),
    ("苏州新区站", "苏州"): Origin(
        label="苏州新区站",
        address="苏州新区站",
        coordinate=Coordinate(longitude=120.543, latitude=31.328),
    ),
}

DESTINATIONS: tuple[Destination, ...] = (
    Destination(
        provider_id="mock:jinji-lake",
        name="金鸡湖景区",
        address="金鸡湖景区",
        city="苏州",
        coordinate=Coordinate(longitude=120.704, latitude=31.315),
        type_name="湖泊景区",
        type_code="lake",
        scenery_tags=frozenset({SceneryType.LAKE}),
        popularity_rank=1,
        rating=4.8,
    ),
    Destination(
        provider_id="mock:tongli",
        name="同里古镇",
        address="同里古镇",
        city="苏州",
        coordinate=Coordinate(longitude=120.717, latitude=31.159),
        type_name="古镇",
        type_code="old_town",
        scenery_tags=frozenset({SceneryType.OLD_TOWN}),
        popularity_rank=2,
        rating=4.7,
    ),
    Destination(
        provider_id="mock:suzhou-museum",
        name="苏州博物馆",
        address="苏州博物馆",
        city="苏州",
        coordinate=Coordinate(longitude=120.627, latitude=31.324),
        type_name="博物馆",
        type_code="museum",
        scenery_tags=frozenset({SceneryType.MUSEUM}),
        popularity_rank=3,
        rating=None,
    ),
    Destination(
        provider_id="mock:qionglong-mountain",
        name="穹窿山",
        address="穹窿山",
        city="苏州",
        coordinate=Coordinate(longitude=120.407, latitude=31.199),
        type_name="山岳景区",
        type_code="mountain",
        scenery_tags=frozenset({SceneryType.MOUNTAIN}),
        popularity_rank=4,
        rating=4.6,
    ),
)

WEATHER_BY_DATE: dict[date, DailyWeather] = {
    date(2026, 7, 20): DailyWeather(
        date=date(2026, 7, 20),
        condition="晴",
        temp_min_c=27,
        temp_max_c=33,
        precipitation_mm=0,
        wind_speed_kmh=16,
        humidity_percent=68,
        visibility_km=18,
        uv_index=8,
    ),
    date(2026, 7, 21): DailyWeather(
        date=date(2026, 7, 21),
        condition="多云",
        temp_min_c=26,
        temp_max_c=32,
        precipitation_mm=0.2,
        wind_speed_kmh=14,
        humidity_percent=71,
        visibility_km=16,
        uv_index=7,
    ),
    date(2026, 7, 22): DailyWeather(
        date=date(2026, 7, 22),
        condition="阵雨",
        temp_min_c=25,
        temp_max_c=30,
        precipitation_mm=4.5,
        wind_speed_kmh=18,
        humidity_percent=79,
        visibility_km=12,
        uv_index=5,
    ),
}

WEATHER_TEMPLATE_START = date(2026, 7, 20)
WEATHER_TEMPLATES: tuple[DailyWeather, ...] = tuple(
    WEATHER_BY_DATE[WEATHER_TEMPLATE_START + timedelta(days=offset)]
    for offset in range(len(WEATHER_BY_DATE))
)

SCENERY_LABELS: dict[SceneryType, str] = {
    SceneryType.LAKE: "湖景休闲",
    SceneryType.OLD_TOWN: "古镇漫游",
    SceneryType.MUSEUM: "馆藏人文",
    SceneryType.MOUNTAIN: "登高望远",
    SceneryType.PARK: "公园散步",
    SceneryType.SEA: "滨海观景",
}


class MockGeocoder:
    def geocode(self, address: str, city: str) -> Origin:
        key = (_normalize_text(address), _normalize_text(city))
        if key not in ORIGINS:
            raise ProviderError("not_found", "未找到出发地")
        return ORIGINS[key]


class MockPlaceProvider:
    def search(
        self,
        center: Coordinate,
        city: str,
        scenery_types: tuple[SceneryType, ...],
        radius_km: float,
    ) -> list[Destination]:
        normalized_city = _normalize_text(city)
        if not scenery_types:
            return []

        results: list[Destination] = []
        for scenery_type in scenery_types:
            for destination in DESTINATIONS:
                if destination.city != normalized_city:
                    continue
                if scenery_type not in destination.scenery_tags:
                    continue
                if _haversine_km(center, destination.coordinate) > radius_km:
                    continue
                if destination not in results:
                    results.append(destination)
        return results

    def resolve(self, name: str, city: str) -> Destination:
        normalized_name = _normalize_text(name)
        normalized_city = _normalize_text(city)
        for destination in DESTINATIONS:
            if destination.city == normalized_city and destination.name == normalized_name:
                return destination
        raise ProviderError("not_found", "未找到指定地点")


class MockDistanceProvider:
    def measure(self, origins: list[Origin], destination: Destination) -> list[DistanceEstimate]:
        estimates: list[DistanceEstimate] = []
        for origin in origins:
            distance_km = round(_haversine_km(origin.coordinate, destination.coordinate), 2)
            estimates.append(
                DistanceEstimate(
                    origin_label=origin.label,
                    distance_km=distance_km,
                    duration_minutes=round(distance_km / 32 * 60, 1),
                    estimated=False,
                )
            )
        return estimates


class MockWeatherProvider:
    def daily(self, coordinate: Coordinate, start: date, end: date) -> list[DailyWeather]:
        del coordinate

        days: list[DailyWeather] = []
        current = start
        while current <= end:
            template_index = (current - WEATHER_TEMPLATE_START).days % len(WEATHER_TEMPLATES)
            weather = WEATHER_TEMPLATES[template_index]
            days.append(weather.model_copy(update={"date": current}))
            current += timedelta(days=1)
        return days


class MockExplanationProvider:
    def explain(self, items: list[RecommendationItem]) -> list[str]:
        explanations: list[str] = []
        for item in items:
            ordered_tags = sorted(
                item.destination.scenery_tags,
                key=lambda tag: tag.value,
            )
            primary_tag = next(iter(ordered_tags), None)
            label = SCENERY_LABELS.get(primary_tag, "城市漫游")
            explanations.append(
                f"{item.destination.name}：{label}取向，分数{item.score.total:.1f}，适合当前这组行程偏好。"
            )
        return explanations


@dataclass(frozen=True)
class MockProviderBundle:
    geocoder: MockGeocoder
    places: MockPlaceProvider
    distance: MockDistanceProvider
    weather: MockWeatherProvider
    explanations: MockExplanationProvider

    @classmethod
    def default(cls) -> MockProviderBundle:
        return cls(
            geocoder=MockGeocoder(),
            places=MockPlaceProvider(),
            distance=MockDistanceProvider(),
            weather=MockWeatherProvider(),
            explanations=MockExplanationProvider(),
        )
