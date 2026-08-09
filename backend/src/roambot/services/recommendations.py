from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from statistics import fmean, pvariance
from unicodedata import normalize

from roambot.domain.models import (
    Coordinate,
    DailyWeather,
    Destination,
    DistanceEstimate,
    ExplanationContext,
    GroupAccessibilityScore,
    Origin,
    OverallAdviceStatus,
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
    TravelAdviceStatus,
)
from roambot.domain.ranking import final_score
from roambot.domain.scoring import (
    aggregate_weather,
    score_daily_weather,
    score_distance,
    score_fairness,
    score_rating,
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
    weather=32,
    distance=24,
    fairness=20,
    popularity=24,
)
EXPLANATION_DEGRADED_NOTICE = "explanation_degraded"
NO_CANDIDATES_NOTICE = "no_candidates"
DEFAULT_PROVIDER_LIMITS = {
    ProviderOperation.GEOCODE: 3,
    ProviderOperation.POI_SEARCH: 6,
    ProviderOperation.WEATHER: 7,
    ProviderOperation.DISTANCE: 7,
    ProviderOperation.LLM: 8,
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
            request.main_origin_coordinate,
            request.companion_origin_coordinates,
        )
        weights = self._weights(request.weights, len(origins))
        budget.consume(ProviderOperation.POI_SEARCH)
        destinations = self.places.search(
            center=origins[0].coordinate,
            city=request.city,
            scenery_types=tuple(request.scenery_types),
            radius_km=request.max_distance_km,
        )

        matching_destinations = [
            destination
            for destination in destinations
            if destination.scenery_tags & frozenset(request.scenery_types)
            and self._haversine_km(origins[0].coordinate, destination.coordinate)
            <= request.max_distance_km
        ]
        target_count = self._target_count(request)
        eligible_destinations = self._preselect_candidates(
            matching_destinations,
            request,
            origins[0].coordinate,
            target_count,
        )

        notices: list[str] = []
        otherwise_eligible_count = 0
        items: list[RecommendationItem] = []
        for destination in eligible_destinations:
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
                coverage_ratio=1,
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

        items = sorted(items, key=self._sort_key)[:target_count]
        if not items:
            notices.append(NO_CANDIDATES_NOTICE)
        else:
            context = ExplanationContext(
                requested_scenery_types=tuple(request.scenery_types),
                scenery_match_mode=request.scenery_match_mode,
                display_weights=weights,
            )
            items, explanation_notice = self._attach_explanations(
                items,
                budget,
                context,
            )
            if explanation_notice is not None:
                notices.append(explanation_notice)

        uncovered_scenery_types = self._uncovered_types(items, request)
        return RecommendationResponse(
            items=items,
            source_state=self._source_state(len(items), notices),
            generated_at=self.clock().isoformat(),
            uncovered_scenery_types=uncovered_scenery_types,
        )

    def evaluate(self, request: PlaceEvaluationRequest) -> PlaceEvaluationResponse:
        budget = ProviderBudget(self.provider_limits)
        origins = self._resolve_origins(
            request.main_origin,
            request.companion_origins,
            request.city,
            budget,
            request.main_origin_coordinate,
            request.companion_origin_coordinates,
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

        context = ExplanationContext(
            requested_scenery_types=tuple(sorted(destination.scenery_tags)),
            scenery_match_mode=SceneryMatchMode.ANY,
            display_weights=weights,
        )
        items, explanation_notice = self._attach_explanations(
            [item],
            budget,
            context,
        )
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
        main_origin_coordinate: Coordinate | None = None,
        companion_origin_coordinates: list[Coordinate | None] | None = None,
    ) -> list[Origin]:
        origins: list[Origin] = []
        companion_coordinates = companion_origin_coordinates or []
        addresses = [
            ("main_origin", main_origin, main_origin_coordinate),
            *(
                (
                    f"companion_origins[{index}]",
                    address,
                    companion_coordinates[index]
                    if index < len(companion_coordinates)
                    else None,
                )
                for index, address in enumerate(companion_origins)
            ),
        ]
        for field_path, address, coordinate in addresses:
            if coordinate is not None:
                origins.append(Origin(label=address, address=address, coordinate=coordinate))
                continue
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

    def _target_count(self, request: RecommendationRequest) -> int:
        if request.scenery_match_mode == SceneryMatchMode.ANY:
            return 5
        return max(5, min(7, len(set(request.scenery_types)) + 1))

    def _preselect_candidates(
        self,
        destinations: list[Destination],
        request: RecommendationRequest,
        center,
        target_count: int,
    ) -> list[Destination]:
        ordered = sorted(
            destinations,
            key=lambda destination: self._preview_key(destination, center),
        )
        if request.scenery_match_mode == SceneryMatchMode.ANY:
            return ordered[:target_count]

        selected: list[Destination] = []
        selected_ids: set[str] = set()
        for scenery_type in dict.fromkeys(request.scenery_types):
            representative = next(
                (
                    destination
                    for destination in ordered
                    if destination.provider_id not in selected_ids
                    and scenery_type in destination.scenery_tags
                ),
                None,
            )
            if representative is not None:
                selected.append(representative)
                selected_ids.add(representative.provider_id)

        for destination in ordered:
            if len(selected) >= target_count:
                break
            if destination.provider_id not in selected_ids:
                selected.append(destination)
                selected_ids.add(destination.provider_id)
        return selected[:target_count]

    def _preview_key(self, destination: Destination, center) -> tuple[object, ...]:
        return (
            destination.rating is None,
            -(destination.rating or 0),
            self._haversine_km(center, destination.coordinate),
            destination.popularity_rank,
            destination.provider_id,
        )

    def _uncovered_types(
        self,
        items: list[RecommendationItem],
        request: RecommendationRequest,
    ) -> list:
        if request.scenery_match_mode != SceneryMatchMode.COVER_ALL:
            return []
        covered = (
            set().union(*(item.destination.scenery_tags for item in items))
            if items
            else set()
        )
        return [
            scenery_type
            for scenery_type in dict.fromkeys(request.scenery_types)
            if scenery_type not in covered
        ]

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
        duration_values = [estimate.duration_minutes for estimate in distances]
        complete_durations = (
            [float(duration) for duration in duration_values if duration is not None]
            if all(duration is not None for duration in duration_values)
            else None
        )
        fairness_score = score_fairness(
            distance_values,
            max_distance_km,
            durations_minutes=complete_durations,
        )
        distance_score = score_distance(average_distance, max_distance_km)
        popularity_score = (
            score_rating(destination.rating) if destination.rating is not None else None
        )
        coverage_penalty = 0.0
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
            overall_advice=self._overall_advice(daily_suitability),
        )

    def _overall_advice(self, days) -> OverallAdviceStatus:
        statuses = {day.status for day in days}
        if TravelAdviceStatus.NOT_RECOMMENDED in statuses:
            return OverallAdviceStatus.SOME_DATES_NOT_RECOMMENDED
        if TravelAdviceStatus.CAUTION in statuses:
            return OverallAdviceStatus.SOME_DATES_CAUTION
        return OverallAdviceStatus.SUITABLE

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
        context: ExplanationContext,
    ) -> tuple[list[RecommendationItem], str | None]:
        coverage_ids = self._coverage_representative_ids(items, context)
        explained = [
            item.model_copy(
                update={
                    "explanation": self._local_explanation(
                        item,
                        context,
                        item.destination.provider_id in coverage_ids,
                    )
                }
            )
            for item in items
        ]
        degraded = False
        for start in range(0, len(explained), 2):
            group = explained[start : start + 2]
            polished: list[str] | None = None
            for _attempt in range(2):
                try:
                    budget.consume(ProviderOperation.LLM)
                    polished = self.explanations.explain(group, context)
                    break
                except (ProviderError, ProviderBudgetExceeded):
                    continue
            if polished is None:
                degraded = True
                continue
            explained[start : start + 2] = [
                item.model_copy(update={"explanation": explanation})
                for item, explanation in zip(group, polished, strict=True)
            ]

        if degraded:
            self._mark(ProviderEvent.TEMPLATE_EXPLANATION)
            return explained, EXPLANATION_DEGRADED_NOTICE
        return explained, None

    def _local_explanation(
        self,
        item: RecommendationItem,
        context: ExplanationContext,
        coverage_kept: bool,
    ) -> str:
        labels = {
            "lake": "湖景",
            "sea": "海景",
            "old_town": "古镇/历史街区",
            "museum": "博物馆",
            "park": "公园/绿地/湿地",
            "mountain": "山地/徒步",
        }
        matched = [
            labels[tag.value]
            for tag in context.requested_scenery_types
            if tag in item.destination.scenery_tags
        ]
        matched_text = "、".join(matched) or "风景类型"
        advice = {
            OverallAdviceStatus.SUITABLE: "所选日期均适合前往",
            OverallAdviceStatus.SOME_DATES_CAUTION: (
                "部分日期天气条件一般，建议关注逐日提示"
            ),
            OverallAdviceStatus.SOME_DATES_NOT_RECOMMENDED: (
                "部分日期不建议前往，请根据逐日提示调整日期"
            ),
        }.get(item.overall_advice, "请结合逐日天气提示安排出行")
        rating = (
            f"高德评分 {item.destination.rating:.1f} / 5"
            if item.destination.rating is not None
            else "高德暂未提供评分"
        )
        coverage = "，并补足了本次类型覆盖" if coverage_kept else ""
        distance = item.group_accessibility.average_distance_km
        distance_label = "路程约" if len(item.distances) == 1 else "平均路程约"
        return (
            f"该地点符合你选择的{matched_text}{coverage}，"
            f"{distance_label} {distance:.2f} 公里；{advice}；{rating}。"
        )

    def _coverage_representative_ids(
        self,
        items: list[RecommendationItem],
        context: ExplanationContext,
    ) -> set[str]:
        if context.scenery_match_mode != SceneryMatchMode.COVER_ALL:
            return set()
        representatives: set[str] = set()
        for scenery_type in context.requested_scenery_types:
            representative = next(
                (
                    item
                    for item in items
                    if scenery_type in item.destination.scenery_tags
                ),
                None,
            )
            if representative is not None:
                representatives.add(representative.destination.provider_id)
        return representatives

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
