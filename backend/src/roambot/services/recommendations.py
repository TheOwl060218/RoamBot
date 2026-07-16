from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta
from math import sqrt
from statistics import fmean, pvariance
from unicodedata import normalize

from roambot.domain.models import (
    DailyWeather,
    Destination,
    DistanceEstimate,
    GroupAccessibilityScore,
    Origin,
    PlaceEvaluationRequest,
    PlaceEvaluationResponse,
    RankingWeights,
    RecommendationItem,
    RecommendationRequest,
    RecommendationResponse,
    SceneryMatchMode,
    ScoreBreakdown,
    SourceKind,
    SourceState,
)
from roambot.domain.ranking import final_score
from roambot.domain.scoring import (
    aggregate_weather,
    clamp,
    score_daily_weather,
    score_distance,
    score_fairness,
    score_popularity,
)
from roambot.providers.protocols import (
    DistanceProvider,
    ExplanationProvider,
    Geocoder,
    PlaceProvider,
    ProviderError,
    WeatherProvider,
)

SINGLE_ORIGIN_DEFAULT_WEIGHTS = RankingWeights(
    weather=40,
    distance=30,
    fairness=0,
    popularity=30,
)
MULTI_ORIGIN_DEFAULT_WEIGHTS = RankingWeights(
    weather=40,
    distance=0,
    fairness=40,
    popularity=20,
)
EXPLANATION_DEGRADED_NOTICE = "explanation_degraded"
NO_CANDIDATES_NOTICE = "no_candidates"
WEATHER_UNAVAILABLE_CODE = "weather_unavailable"


class OriginNotFoundError(RuntimeError):
    def __init__(self, field_path: str) -> None:
        super().__init__(field_path)
        self.field_path = field_path


class PlaceNotFoundError(RuntimeError):
    pass


class RecommendationService:
    def __init__(
        self,
        geocoder: Geocoder,
        places: PlaceProvider,
        distance: DistanceProvider,
        weather: WeatherProvider,
        explanations: ExplanationProvider,
        source_kind: SourceKind,
        clock: Callable[[], datetime],
    ) -> None:
        self.geocoder = geocoder
        self.places = places
        self.distance = distance
        self.weather = weather
        self.explanations = explanations
        self.source_kind = source_kind
        self.clock = clock

    def recommend(self, request: RecommendationRequest) -> RecommendationResponse:
        origins = self._resolve_origins(
            request.main_origin,
            request.companion_origins,
            request.city,
        )
        weights = self._weights(request.weights, len(origins))
        destinations = self.places.search(
            center=origins[0].coordinate,
            city=request.city,
            scenery_types=tuple(request.scenery_types),
            radius_km=request.max_distance_km,
        )

        notices: list[str] = []
        otherwise_eligible_count = 0
        items: list[RecommendationItem] = []
        for destination in destinations:
            coverage_ratio = self._coverage_ratio(destination, request)
            if coverage_ratio is None:
                continue

            distances = self.distance.measure(origins, destination)
            primary_distance = distances[0].distance_km
            if primary_distance > request.max_distance_km:
                continue

            otherwise_eligible_count += 1
            item = self._score_candidate(
                destination=destination,
                origins=origins,
                distances=distances,
                max_distance_km=request.max_distance_km,
                start_date=request.start_date,
                end_date=request.end_date,
                weights=weights,
                coverage_ratio=coverage_ratio,
            )
            if item is None:
                notices.append(f"partial_weather:{destination.provider_id}")
                continue
            items.append(item)

        if not items and otherwise_eligible_count > 0 and notices:
            raise ProviderError(
                WEATHER_UNAVAILABLE_CODE,
                "weather unavailable for all recommendation candidates",
            )

        items = sorted(items, key=self._sort_key)[:5]
        if not items:
            notices.append(NO_CANDIDATES_NOTICE)
        else:
            items, explanation_notice = self._attach_explanations(items)
            if explanation_notice is not None:
                notices.append(explanation_notice)

        return RecommendationResponse(
            items=items,
            source_state=SourceState(kind=self.source_kind, notices=notices),
            generated_at=self.clock().isoformat(),
        )

    def evaluate(self, request: PlaceEvaluationRequest) -> PlaceEvaluationResponse:
        origins = self._resolve_origins(
            request.main_origin,
            request.companion_origins,
            request.city,
        )
        weights = self._weights(request.weights, len(origins))
        try:
            destination = self.places.resolve(request.target_place, request.city)
        except ProviderError as exc:
            if exc.code == "not_found":
                raise PlaceNotFoundError from exc
            raise
        distances = self.distance.measure(origins, destination)
        item = self._score_candidate(
            destination=destination,
            origins=origins,
            distances=distances,
            max_distance_km=request.max_distance_km,
            start_date=request.start_date,
            end_date=request.end_date,
            weights=weights,
            coverage_ratio=1,
        )
        if item is None:
            raise ProviderError(
                WEATHER_UNAVAILABLE_CODE,
                "weather unavailable for target destination",
            )

        items, explanation_notice = self._attach_explanations([item])
        notices = [explanation_notice] if explanation_notice is not None else []

        return PlaceEvaluationResponse(
            item=items[0],
            source_state=SourceState(kind=self.source_kind, notices=notices),
            generated_at=self.clock().isoformat(),
        )

    def _resolve_origins(
        self,
        main_origin: str,
        companion_origins: list[str],
        city: str,
    ) -> list[Origin]:
        origins: list[Origin] = []
        addresses = [
            ("main_origin", main_origin),
            *(
                (f"companion_origins[{index}]", address)
                for index, address in enumerate(companion_origins)
            ),
        ]
        for field_path, address in addresses:
            try:
                origins.append(self.geocoder.geocode(address, city))
            except ProviderError as exc:
                if exc.code == "not_found":
                    raise OriginNotFoundError(field_path) from exc
                raise
        return origins

    def _weights(self, weights: RankingWeights | None, origin_count: int) -> RankingWeights:
        if weights is not None:
            return weights
        if origin_count == 1:
            return SINGLE_ORIGIN_DEFAULT_WEIGHTS
        return MULTI_ORIGIN_DEFAULT_WEIGHTS

    def _coverage_ratio(
        self,
        destination: Destination,
        request: RecommendationRequest,
    ) -> float | None:
        requested = frozenset(request.scenery_types)
        matched = destination.scenery_tags & requested
        if not matched:
            return None
        if request.scenery_match_mode == SceneryMatchMode.ANY:
            return 1
        return len(matched) / len(requested)

    def _score_candidate(
        self,
        *,
        destination: Destination,
        origins: list[Origin],
        distances: list[DistanceEstimate],
        max_distance_km: float,
        start_date: date,
        end_date: date,
        weights: RankingWeights,
        coverage_ratio: float,
    ) -> RecommendationItem | None:
        weather = self._complete_weather(destination, start_date, end_date)
        if weather is None:
            return None

        daily_suitability = [
            score_daily_weather(day, destination.scenery_tags) for day in weather
        ]
        weather_score = aggregate_weather([day.score for day in daily_suitability])
        distance_values = [estimate.distance_km for estimate in distances]
        average_distance = fmean(distance_values)
        max_distance = max(distance_values)
        distance_variance = pvariance(distance_values)
        distance_stddev = sqrt(distance_variance)
        fairness_score = score_fairness(distance_values, max_distance_km)
        distance_score = score_distance(average_distance, max_distance_km)
        popularity_score = score_popularity(destination.popularity_rank)
        coverage_penalty = clamp(20 * (1 - max(0.0, min(1.0, coverage_ratio))))
        total = final_score(
            weather=weather_score,
            distance=distance_score,
            fairness=fairness_score,
            popularity=popularity_score,
            weights=weights,
            coverage_ratio=coverage_ratio,
        )

        return RecommendationItem(
            destination=destination,
            distances=distances,
            group_accessibility=GroupAccessibilityScore(
                average_distance_km=round(average_distance, 2),
                max_distance_km=round(max_distance, 2),
                distance_variance=round(distance_variance, 2),
                distance_stddev=round(distance_stddev, 2),
                fairness_score=fairness_score,
            ),
            weather=weather,
            daily_suitability=daily_suitability,
            score=ScoreBreakdown(
                weather=weather_score,
                distance=distance_score,
                fairness=fairness_score,
                popularity=popularity_score,
                coverage_penalty=coverage_penalty,
                total=total,
            ),
            explanation="",
        )

    def _complete_weather(
        self,
        destination: Destination,
        start_date: date,
        end_date: date,
    ) -> list[DailyWeather] | None:
        try:
            weather = self.weather.daily(destination.coordinate, start_date, end_date)
        except ProviderError:
            return None

        by_date = {day.date: day for day in weather}
        required_dates = self._date_range(start_date, end_date)
        if any(day not in by_date for day in required_dates):
            return None
        return [by_date[day] for day in required_dates]

    def _attach_explanations(
        self,
        items: list[RecommendationItem],
    ) -> tuple[list[RecommendationItem], str | None]:
        try:
            explanations = self.explanations.explain(items)
        except ProviderError:
            return (
                [
                    item.model_copy(update={"explanation": self._template_explanation(item)})
                    for item in items
                ],
                EXPLANATION_DEGRADED_NOTICE,
            )

        return (
            [
                item.model_copy(update={"explanation": explanation})
                for item, explanation in zip(items, explanations, strict=True)
            ],
            None,
        )

    def _template_explanation(self, item: RecommendationItem) -> str:
        return f"{item.destination.name} scored {item.score.total:.2f} for this trip."

    def _sort_key(self, item: RecommendationItem) -> tuple[float, float, str, str]:
        return (
            -item.score.total,
            item.distances[0].distance_km,
            normalize("NFKC", item.destination.name).strip(),
            item.destination.provider_id,
        )

    def _date_range(self, start_date: date, end_date: date) -> list[date]:
        days: list[date] = []
        current = start_date
        while current <= end_date:
            days.append(current)
            current += timedelta(days=1)
        return days
