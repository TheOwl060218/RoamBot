from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta
from math import asin, cos, radians, sin, sqrt
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
from roambot.providers.budget import (
    ProviderBudget,
    ProviderBudgetExceeded,
    ProviderOperation,
)
from roambot.providers.protocols import (
    DistanceProvider,
    ExplanationProvider,
    Geocoder,
    PlaceProvider,
    ProviderError,
    WeatherProvider,
)
from roambot.providers.trace import ProviderEvent, ProviderTrace

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
DEFAULT_PROVIDER_LIMITS = {
    ProviderOperation.GEOCODE: 3,
    ProviderOperation.POI_SEARCH: 6,
    ProviderOperation.WEATHER: 5,
    ProviderOperation.DISTANCE: 5,
    ProviderOperation.LLM: 1,
}


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
        provider_limits: Mapping[ProviderOperation, int] | None = None,
        trace: ProviderTrace | None = None,
    ) -> None:
        self.geocoder = geocoder
        self.places = places
        self.distance = distance
        self.weather = weather
        self.explanations = explanations
        self.source_kind = source_kind
        self.clock = clock
        self.provider_limits = dict(provider_limits or DEFAULT_PROVIDER_LIMITS)
        self.trace = trace

    def recommend(self, request: RecommendationRequest) -> RecommendationResponse:
        budget = ProviderBudget(self.provider_limits)
        origins = self._resolve_origins(
            request.main_origin,
            request.companion_origins,
            request.city,
            budget,
        )
        weights = self._weights(request.weights, len(origins))
        budget.consume(ProviderOperation.POI_SEARCH)
        destinations = self.places.search(
            center=origins[0].coordinate,
            city=request.city,
            scenery_types=tuple(request.scenery_types),
            radius_km=request.max_distance_km,
        )

        eligible_destinations: list[tuple[Destination, float]] = []
        for destination in destinations:
            coverage_ratio = self._coverage_ratio(destination, request)
            if coverage_ratio is None:
                continue
            if (
                self._haversine_km(origins[0].coordinate, destination.coordinate)
                <= request.max_distance_km
            ):
                eligible_destinations.append((destination, coverage_ratio))
            if len(eligible_destinations) == 5:
                break

        notices: list[str] = []
        otherwise_eligible_count = 0
        items: list[RecommendationItem] = []
        for destination, coverage_ratio in eligible_destinations:
            try:
                budget.consume(ProviderOperation.DISTANCE)
                distances = self.distance.measure(origins, destination)
            except ProviderBudgetExceeded:
                raise
            except ProviderError:
                distances = self._straight_line_estimates(origins, destination)
                self._mark(ProviderEvent.STRAIGHT_LINE)
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
                budget=budget,
            )
            if item is None:
                notices.append(f"partial_weather:{destination.provider_id}")
                continue
            items.append(item)

        if not items and otherwise_eligible_count > 0 and notices:
            raise ProviderError(
                "unavailable",
                "全部候选天气数据暂时不可用",
            )

        items = sorted(items, key=self._sort_key)[:5]
        if not items:
            notices.append(NO_CANDIDATES_NOTICE)
        else:
            items, explanation_notice = self._attach_explanations(items, budget)
            if explanation_notice is not None:
                notices.append(explanation_notice)

        return RecommendationResponse(
            items=items,
            source_state=self._source_state(len(items), notices),
            generated_at=self.clock().isoformat(),
        )

    def evaluate(self, request: PlaceEvaluationRequest) -> PlaceEvaluationResponse:
        budget = ProviderBudget(self.provider_limits)
        origins = self._resolve_origins(
            request.main_origin,
            request.companion_origins,
            request.city,
            budget,
        )
        weights = self._weights(request.weights, len(origins))
        try:
            budget.consume(ProviderOperation.POI_SEARCH)
            destination = self.places.resolve(request.target_place, request.city)
        except ProviderError as exc:
            if exc.code == "not_found":
                raise PlaceNotFoundError from exc
            raise
        budget.consume(ProviderOperation.DISTANCE)
        try:
            distances = self.distance.measure(origins, destination)
        except ProviderBudgetExceeded:
            raise
        except ProviderError:
            distances = self._straight_line_estimates(origins, destination)
            self._mark(ProviderEvent.STRAIGHT_LINE)
        item = self._score_candidate(
            destination=destination,
            origins=origins,
            distances=distances,
            max_distance_km=request.max_distance_km,
            start_date=request.start_date,
            end_date=request.end_date,
            weights=weights,
            coverage_ratio=1,
            budget=budget,
        )
        if item is None:
            raise ProviderError(
                "unavailable",
                "指定地点天气数据暂时不可用",
            )

        items, explanation_notice = self._attach_explanations([item], budget)
        notices = [explanation_notice] if explanation_notice is not None else []

        return PlaceEvaluationResponse(
            item=items[0],
            source_state=self._source_state(3, notices),
            generated_at=self.clock().isoformat(),
        )

    def _resolve_origins(
        self,
        main_origin: str,
        companion_origins: list[str],
        city: str,
        budget: ProviderBudget,
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
                budget.consume(ProviderOperation.GEOCODE)
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
        budget: ProviderBudget,
    ) -> RecommendationItem | None:
        weather = self._complete_weather(destination, start_date, end_date, budget)
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
        budget: ProviderBudget,
    ) -> list[DailyWeather] | None:
        try:
            budget.consume(ProviderOperation.WEATHER)
            weather = self.weather.daily(destination.coordinate, start_date, end_date)
        except ProviderBudgetExceeded:
            raise
        except ProviderError:
            self._mark(ProviderEvent.WEATHER_EXCLUDED)
            return None

        by_date = {day.date: day for day in weather}
        required_dates = self._date_range(start_date, end_date)
        if any(day not in by_date for day in required_dates):
            return None
        return [by_date[day] for day in required_dates]

    def _attach_explanations(
        self,
        items: list[RecommendationItem],
        budget: ProviderBudget,
    ) -> tuple[list[RecommendationItem], str | None]:
        try:
            budget.consume(ProviderOperation.LLM)
            explanations = self.explanations.explain(items)
        except ProviderError:
            self._mark(ProviderEvent.TEMPLATE_EXPLANATION)
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

    def _straight_line_estimates(
        self,
        origins: list[Origin],
        destination: Destination,
    ) -> list[DistanceEstimate]:
        return [
            DistanceEstimate(
                origin_label=origin.label,
                distance_km=round(
                    self._haversine_km(origin.coordinate, destination.coordinate),
                    2,
                ),
                duration_minutes=None,
                estimated=True,
            )
            for origin in origins
        ]

    def _source_state(
        self,
        final_item_count: int,
        legacy_notices: list[str],
    ) -> SourceState:
        if self.trace is not None:
            return self.trace.to_source_state(final_item_count)
        return SourceState(kind=self.source_kind, notices=legacy_notices)

    def _mark(self, event: ProviderEvent) -> None:
        if self.trace is not None:
            self.trace.mark(event)

    @staticmethod
    def _haversine_km(left, right) -> float:
        earth_radius_km = 6371.0088
        left_latitude = radians(left.latitude)
        right_latitude = radians(right.latitude)
        latitude_delta = right_latitude - left_latitude
        longitude_delta = radians(right.longitude - left.longitude)
        haversine = sin(latitude_delta / 2) ** 2 + (
            cos(left_latitude) * cos(right_latitude) * sin(longitude_delta / 2) ** 2
        )
        return 2 * earth_radius_km * asin(sqrt(haversine))
