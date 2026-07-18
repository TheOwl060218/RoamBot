from datetime import UTC, date, datetime

import pytest

from roambot.domain.models import (
    Coordinate,
    DailyWeather,
    Destination,
    DistanceEstimate,
    Origin,
    RecommendationRequest,
    SceneryType,
    SourceKind,
)
from roambot.providers.protocols import ProviderError
from roambot.providers.trace import ProviderEvent, ProviderTrace
from roambot.services.recommendations import RecommendationService

START = date(2026, 7, 20)
GENERATED = datetime(2026, 7, 18, 8, 0, tzinfo=UTC)


def place(index: int) -> Destination:
    return Destination(
        provider_id=f"poi-{index}",
        name=f"湖景 {index}",
        address="public place",
        city="苏州",
        coordinate=Coordinate(longitude=120.61 + index / 1000, latitude=31.33),
        type_name="湖泊景区",
        type_code="test",
        scenery_tags=frozenset({SceneryType.LAKE}),
        popularity_rank=index,
    )


class Geocoder:
    def geocode(self, address: str, city: str) -> Origin:
        return Origin(
            label=address,
            address=address,
            coordinate=Coordinate(longitude=120.61, latitude=31.33),
        )


class Places:
    def __init__(self, count: int) -> None:
        self.destinations = [place(index) for index in range(1, count + 1)]

    def search(self, center, city, scenery_types, radius_km):
        return self.destinations

    def resolve(self, name: str, city: str):
        return self.destinations[0]


class Distances:
    def __init__(self, *, fail: bool = False, distance_km: float = 10) -> None:
        self.fail = fail
        self.distance_km = distance_km
        self.calls = 0

    def measure(self, origins, destination):
        self.calls += 1
        if self.fail:
            raise ProviderError("unavailable", "distance down")
        return [
            DistanceEstimate(
                origin_label=origin.label,
                distance_km=self.distance_km,
                duration_minutes=20,
            )
            for origin in origins
        ]


class Weather:
    def __init__(self, failing_longitudes: set[float] | None = None) -> None:
        self.failing_longitudes = failing_longitudes or set()
        self.calls = 0

    def daily(self, coordinate, start, end):
        self.calls += 1
        if coordinate.longitude in self.failing_longitudes:
            raise ProviderError("unavailable", "weather down")
        return [
            DailyWeather(
                date=start,
                condition="晴",
                temp_min_c=24,
                temp_max_c=31,
                precipitation_mm=0,
                wind_speed_kmh=10,
                humidity_percent=60,
                visibility_km=20,
                uv_index=7,
            )
        ]


class Explanations:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def explain(self, items):
        if self.fail:
            raise ProviderError("unavailable", "llm down")
        return [f"推荐 {item.destination.name}" for item in items]


def request(max_distance_km: float = 50) -> RecommendationRequest:
    return RecommendationRequest(
        city="苏州",
        main_origin="苏州站",
        max_distance_km=max_distance_km,
        start_date=START,
        end_date=START,
        scenery_types=[SceneryType.LAKE],
    )


def service(
    *,
    count: int,
    distances: Distances | None = None,
    weather: Weather | None = None,
    explanations: Explanations | None = None,
) -> tuple[RecommendationService, ProviderTrace, Distances, Weather]:
    trace = ProviderTrace()
    distance_provider = distances or Distances()
    weather_provider = weather or Weather()
    return (
        RecommendationService(
            geocoder=Geocoder(),
            places=Places(count),
            distance=distance_provider,
            weather=weather_provider,
            explanations=explanations or Explanations(),
            source_kind=SourceKind.LIVE,
            clock=lambda: GENERATED,
            trace=trace,
        ),
        trace,
        distance_provider,
        weather_provider,
    )


def test_recommendation_processes_at_most_first_five_candidates() -> None:
    recommendation, _, distances, weather = service(count=7)
    result = recommendation.recommend(request())

    assert [item.destination.provider_id for item in result.items] == [
        "poi-1",
        "poi-2",
        "poi-3",
        "poi-4",
        "poi-5",
    ]
    assert distances.calls == 5
    assert weather.calls == 5
    assert result.source_state.kind is SourceKind.LIVE
    assert result.source_state.notices == []


def test_partial_weather_excludes_candidate_and_marks_degraded_state() -> None:
    failing = place(2).coordinate.longitude
    recommendation, _, _, weather = service(
        count=2,
        weather=Weather({failing}),
    )
    result = recommendation.recommend(request())

    assert weather.calls == 2
    assert [item.destination.provider_id for item in result.items] == ["poi-1"]
    assert result.source_state.kind is SourceKind.DEGRADED
    assert result.source_state.notices == [
        "部分候选因天气不可用已排除",
        "符合条件的候选不足 3 个",
    ]


def test_all_weather_failures_raise_stable_provider_error() -> None:
    failing = {place(1).coordinate.longitude, place(2).coordinate.longitude}
    recommendation, _, _, _ = service(count=2, weather=Weather(failing))

    with pytest.raises(ProviderError) as captured:
        recommendation.recommend(request())
    assert captured.value.code == "unavailable"
    assert str(captured.value) == "全部候选天气数据暂时不可用"


def test_distance_failure_uses_straight_line_estimate_and_notice() -> None:
    recommendation, _, distances, _ = service(count=1, distances=Distances(fail=True))
    result = recommendation.recommend(request())

    estimate = result.items[0].distances[0]
    assert distances.calls == 1
    assert estimate.estimated is True
    assert estimate.duration_minutes is None
    assert result.source_state.kind is SourceKind.DEGRADED
    assert result.source_state.notices == [
        "部分路程使用直线距离估算",
        "符合条件的候选不足 3 个",
    ]


def test_exact_over_distance_candidate_is_not_backfilled_or_sent_to_weather() -> None:
    recommendation, _, distances, weather = service(
        count=3,
        distances=Distances(distance_km=60),
    )
    result = recommendation.recommend(request(max_distance_km=50))

    assert distances.calls == 3
    assert weather.calls == 0
    assert result.items == []
    assert result.source_state.notices == ["符合条件的候选不足 3 个"]


def test_llm_failure_keeps_scores_and_marks_template_explanation() -> None:
    recommendation, _, _, _ = service(count=1, explanations=Explanations(fail=True))
    result = recommendation.recommend(request())

    assert result.items[0].score.total > 0
    assert result.items[0].explanation.endswith("for this trip.")
    assert result.source_state.notices == [
        "推荐理由由本地模板生成",
        "符合条件的候选不足 3 个",
    ]


def test_trace_notice_order_and_precedence_are_stable() -> None:
    trace = ProviderTrace()
    for event in (
        ProviderEvent.TEMPLATE_EXPLANATION,
        ProviderEvent.CACHE,
        ProviderEvent.DEMO,
        ProviderEvent.STRAIGHT_LINE,
    ):
        trace.mark(event)

    state = trace.to_source_state(final_item_count=2)
    assert state.kind is SourceKind.DEGRADED
    assert state.notices == [
        "使用未过期缓存结果",
        "使用内置苏州演示数据",
        "部分路程使用直线距离估算",
        "推荐理由由本地模板生成",
        "符合条件的候选不足 3 个",
    ]
