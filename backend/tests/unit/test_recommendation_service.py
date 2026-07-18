from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from roambot.domain.models import (
    Coordinate,
    DailyWeather,
    Destination,
    DistanceEstimate,
    Origin,
    PlaceEvaluationRequest,
    RecommendationItem,
    RecommendationRequest,
    SceneryMatchMode,
    SceneryType,
    SourceKind,
)
from roambot.providers.mock import WEATHER_BY_DATE, MockProviderBundle
from roambot.providers.protocols import ProviderError
from roambot.services.recommendations import RecommendationService

START = date(2026, 7, 20)
END = date(2026, 7, 22)
GENERATED_AT = datetime(2026, 7, 16, 8, 30, tzinfo=UTC)


def fixed_clock() -> datetime:
    return GENERATED_AT


def weather_range() -> list[DailyWeather]:
    return [WEATHER_BY_DATE[START], WEATHER_BY_DATE[date(2026, 7, 21)], WEATHER_BY_DATE[END]]


def origin(label: str, longitude: float = 120.0, latitude: float = 31.0) -> Origin:
    return Origin(
        label=label,
        address=label,
        coordinate=Coordinate(longitude=longitude, latitude=latitude),
    )


def destination(
    provider_id: str,
    name: str,
    tags: frozenset[SceneryType],
    rank: int = 1,
) -> Destination:
    return Destination(
        provider_id=provider_id,
        name=name,
        address=name,
        city="Suzhou",
        coordinate=Coordinate(longitude=120.05 + rank / 1000, latitude=31.02),
        type_name="test",
        type_code="test",
        scenery_tags=tags,
        popularity_rank=rank,
    )


class CountingGeocoder:
    def __init__(self, origins: dict[str, Origin]) -> None:
        self.origins = origins
        self.calls: list[tuple[str, str]] = []

    def geocode(self, address: str, city: str) -> Origin:
        self.calls.append((address, city))
        return self.origins[address]


class StaticPlaceProvider:
    def __init__(
        self,
        destinations: list[Destination],
        resolved: Destination | None = None,
    ) -> None:
        self.destinations = destinations
        self.resolved = resolved
        self.search_calls: list[tuple[Coordinate, str, tuple[SceneryType, ...], float]] = []
        self.resolve_calls: list[tuple[str, str]] = []

    def search(
        self,
        center: Coordinate,
        city: str,
        scenery_types: tuple[SceneryType, ...],
        radius_km: float,
    ) -> list[Destination]:
        self.search_calls.append((center, city, scenery_types, radius_km))
        return self.destinations

    def resolve(self, name: str, city: str) -> Destination:
        self.resolve_calls.append((name, city))
        if self.resolved is not None:
            return self.resolved
        for candidate in self.destinations:
            if candidate.name == name:
                return candidate
        raise ProviderError("not_found", "place not found")


class StaticDistanceProvider:
    def __init__(self, distances: dict[str, list[float]]) -> None:
        self.distances = distances
        self.calls: list[tuple[list[Origin], Destination]] = []

    def measure(self, origins: list[Origin], destination: Destination) -> list[DistanceEstimate]:
        self.calls.append((origins, destination))
        distances = self.distances[destination.provider_id]
        return [
            DistanceEstimate(
                origin_label=origin.label,
                distance_km=distance_km,
                duration_minutes=distance_km * 2,
                estimated=False,
            )
            for origin, distance_km in zip(origins, distances, strict=True)
        ]


class StaticWeatherProvider:
    def __init__(
        self,
        weather_by_id: dict[str, list[DailyWeather] | ProviderError],
        coordinate_ids: dict[Coordinate, str],
    ) -> None:
        self.weather_by_id = weather_by_id
        self.coordinate_ids = coordinate_ids
        self.calls: list[tuple[Coordinate, date, date]] = []

    def daily(self, coordinate: Coordinate, start: date, end: date) -> list[DailyWeather]:
        self.calls.append((coordinate, start, end))
        result = self.weather_by_id[self.coordinate_ids[coordinate]]
        if isinstance(result, ProviderError):
            raise result
        return result


class CountingExplanationProvider:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[list[RecommendationItem]] = []

    def explain(self, items: list[RecommendationItem]) -> list[str]:
        self.calls.append(items)
        if self.fail:
            raise ProviderError("llm_unavailable", "explanations unavailable")
        return [f"explained:{item.destination.provider_id}" for item in items]


def service(
    *,
    destinations: list[Destination],
    distances: dict[str, list[float]],
    weather_by_id: dict[str, list[DailyWeather] | ProviderError] | None = None,
    origins: dict[str, Origin] | None = None,
    explanations_fail: bool = False,
    resolved: Destination | None = None,
) -> tuple[
    RecommendationService,
    CountingGeocoder,
    StaticPlaceProvider,
    StaticDistanceProvider,
    StaticWeatherProvider,
    CountingExplanationProvider,
]:
    MockProviderBundle.default()
    origins = origins or {"main": origin("main"), "friend": origin("friend", 120.1)}
    geocoder = CountingGeocoder(origins)
    places = StaticPlaceProvider(destinations, resolved)
    distance = StaticDistanceProvider(distances)
    coordinate_ids = {candidate.coordinate: candidate.provider_id for candidate in destinations}
    if resolved is not None:
        coordinate_ids[resolved.coordinate] = resolved.provider_id
    weather = StaticWeatherProvider(
        weather_by_id
        or {candidate.provider_id: weather_range() for candidate in destinations}
        | ({resolved.provider_id: weather_range()} if resolved is not None else {}),
        coordinate_ids,
    )
    explanations = CountingExplanationProvider(fail=explanations_fail)
    recommendation_service = RecommendationService(
        geocoder=geocoder,
        places=places,
        distance=distance,
        weather=weather,
        explanations=explanations,
        source_kind=SourceKind.DEMO,
        clock=fixed_clock,
    )
    return recommendation_service, geocoder, places, distance, weather, explanations


def request(**changes: object) -> RecommendationRequest:
    values: dict[str, object] = {
        "city": "Suzhou",
        "main_origin": "main",
        "companion_origins": [],
        "max_distance_km": 50,
        "start_date": START,
        "end_date": END,
        "scenery_types": [SceneryType.LAKE],
        "scenery_match_mode": SceneryMatchMode.ANY,
    }
    values.update(changes)
    return RecommendationRequest.model_validate(values)


def evaluation_request(**changes: object) -> PlaceEvaluationRequest:
    values: dict[str, object] = {
        "city": "Suzhou",
        "main_origin": "main",
        "companion_origins": [],
        "max_distance_km": 50,
        "start_date": START,
        "end_date": END,
        "target_place": "Target",
    }
    values.update(changes)
    return PlaceEvaluationRequest.model_validate(values)


def test_recommend_filters_primary_origin_distance_and_sorts() -> None:
    alpha = destination("alpha", " Alpha", frozenset({SceneryType.LAKE}), rank=1)
    beta = destination("beta", "Beta", frozenset({SceneryType.LAKE}), rank=1)
    far = destination("far", "Far", frozenset({SceneryType.LAKE}), rank=1)
    recommendation_service, _, _, distance, weather, explanations = service(
        destinations=[far, beta, alpha],
        distances={"alpha": [10], "beta": [10], "far": [60]},
    )

    result = recommendation_service.recommend(request(max_distance_km=50))

    assert [item.destination.provider_id for item in result.items] == ["alpha", "beta"]
    assert result.source_state.kind == SourceKind.DEMO
    assert result.source_state.notices == []
    assert [item.explanation for item in result.items] == ["explained:alpha", "explained:beta"]
    assert len(distance.calls) == 3
    assert len(weather.calls) == 2
    assert len(explanations.calls) == 1


def test_multi_origin_uses_default_fairness_weight() -> None:
    fair = destination("fair", "Fair", frozenset({SceneryType.LAKE}), rank=1)
    spread = destination("spread", "Spread", frozenset({SceneryType.LAKE}), rank=1)
    recommendation_service, *_ = service(
        destinations=[spread, fair],
        distances={"fair": [20, 20], "spread": [10, 30]},
    )

    result = recommendation_service.recommend(
        request(companion_origins=["friend"], max_distance_km=50)
    )

    by_id = {item.destination.provider_id: item for item in result.items}
    assert by_id["fair"].score.distance == by_id["spread"].score.distance
    assert by_id["fair"].score.fairness > by_id["spread"].score.fairness
    assert by_id["fair"].score.total > by_id["spread"].score.total
    assert [item.destination.provider_id for item in result.items] == ["fair", "spread"]


def test_cover_all_applies_coverage_penalty() -> None:
    lake = destination("lake", "Lake", frozenset({SceneryType.LAKE}), rank=1)
    recommendation_service, *_ = service(destinations=[lake], distances={"lake": [10]})

    any_result = recommendation_service.recommend(
        request(
            scenery_types=[SceneryType.LAKE, SceneryType.MOUNTAIN],
            scenery_match_mode=SceneryMatchMode.ANY,
        )
    )
    cover_all_result = recommendation_service.recommend(
        request(
            scenery_types=[SceneryType.LAKE, SceneryType.MOUNTAIN],
            scenery_match_mode=SceneryMatchMode.COVER_ALL,
        )
    )

    assert any_result.items[0].score.coverage_penalty == 0
    assert cover_all_result.items[0].score.coverage_penalty == 10
    assert any_result.items[0].score.total - cover_all_result.items[0].score.total == 10


def test_evaluate_returns_only_requested_destination() -> None:
    target = destination("target", "Target", frozenset({SceneryType.MUSEUM}), rank=5)
    higher = destination("higher", "Higher", frozenset({SceneryType.LAKE}), rank=1)
    recommendation_service, _, places, distance, weather, explanations = service(
        destinations=[higher],
        resolved=target,
        distances={"target": [15], "higher": [1]},
    )

    result = recommendation_service.evaluate(evaluation_request(target_place="Target"))

    assert result.item.destination.provider_id == "target"
    assert result.source_state.kind == SourceKind.DEMO
    assert places.search_calls == []
    assert places.resolve_calls == [("Target", "Suzhou")]
    assert len(distance.calls) == 1
    assert len(weather.calls) == 1
    assert len(explanations.calls) == 1


def test_explanation_failure_uses_template_without_changing_score() -> None:
    alpha = destination("alpha", "Alpha", frozenset({SceneryType.LAKE}), rank=1)
    beta = destination("beta", "Beta", frozenset({SceneryType.LAKE}), rank=2)
    passing_service, *_ = service(
        destinations=[alpha, beta],
        distances={"alpha": [10], "beta": [20]},
    )
    degraded_service, *_, degraded_explanations = service(
        destinations=[alpha, beta],
        distances={"alpha": [10], "beta": [20]},
        explanations_fail=True,
    )

    passing = passing_service.recommend(request())
    degraded = degraded_service.recommend(request())

    assert [item.destination.provider_id for item in degraded.items] == [
        item.destination.provider_id for item in passing.items
    ]
    assert [item.score for item in degraded.items] == [item.score for item in passing.items]
    assert [item.explanation for item in degraded.items] != [
        item.explanation for item in passing.items
    ]
    assert degraded.items[0].explanation.startswith("Alpha scored ")
    assert degraded.source_state.notices == ["explanation_degraded"]
    assert len(degraded_explanations.calls) == 1


def test_no_candidates_returns_empty_items_with_notice() -> None:
    mountain = destination("mountain", "Mountain", frozenset({SceneryType.MOUNTAIN}), rank=1)
    recommendation_service, _, _, _, weather, explanations = service(
        destinations=[mountain],
        distances={"mountain": [10]},
    )

    result = recommendation_service.recommend(request(scenery_types=[SceneryType.LAKE]))

    assert result.items == []
    assert result.source_state.kind == SourceKind.DEMO
    assert result.source_state.notices == ["no_candidates"]
    assert weather.calls == []
    assert explanations.calls == []


def test_recommend_excludes_partial_weather_and_adds_notice() -> None:
    complete = destination("complete", "Complete", frozenset({SceneryType.LAKE}), rank=1)
    partial = destination("partial", "Partial", frozenset({SceneryType.LAKE}), rank=2)
    recommendation_service, *_ = service(
        destinations=[partial, complete],
        distances={"complete": [10], "partial": [5]},
        weather_by_id={
            "complete": weather_range(),
            "partial": weather_range()[:2],
        },
    )

    result = recommendation_service.recommend(request())

    assert [item.destination.provider_id for item in result.items] == ["complete"]
    assert result.source_state.notices == ["partial_weather:partial"]


@pytest.mark.parametrize("weather_value", [weather_range()[:2], ProviderError("down", "down")])
def test_recommend_fails_when_all_candidates_lost_to_weather(
    weather_value: list[DailyWeather] | ProviderError,
) -> None:
    partial = destination("partial", "Partial", frozenset({SceneryType.LAKE}), rank=1)
    recommendation_service, *_ = service(
        destinations=[partial],
        distances={"partial": [10]},
        weather_by_id={"partial": weather_value},
    )

    with pytest.raises(ProviderError) as exc_info:
        recommendation_service.recommend(request())

    assert exc_info.value.code == "unavailable"
    assert str(exc_info.value) == "全部候选天气数据暂时不可用"


def test_evaluate_fails_when_target_lacks_complete_weather() -> None:
    target = destination("target", "Target", frozenset({SceneryType.LAKE}), rank=1)
    recommendation_service, *_ = service(
        destinations=[],
        resolved=target,
        distances={"target": [10]},
        weather_by_id={"target": weather_range()[:2]},
    )

    with pytest.raises(ProviderError) as exc_info:
        recommendation_service.evaluate(evaluation_request())

    assert exc_info.value.code == "unavailable"
    assert str(exc_info.value) == "指定地点天气数据暂时不可用"
