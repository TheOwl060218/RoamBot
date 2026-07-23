from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class SceneryType(StrEnum):
    LAKE = "lake"
    SEA = "sea"
    OLD_TOWN = "old_town"
    MUSEUM = "museum"
    PARK = "park"
    MOUNTAIN = "mountain"


class SceneryMatchMode(StrEnum):
    ANY = "any"
    COVER_ALL = "cover_all"


class SceneryExposure(StrEnum):
    INDOOR = "indoor"
    OUTDOOR = "outdoor"
    MIXED = "mixed"


class TravelAdviceStatus(StrEnum):
    SUITABLE = "suitable"
    CAUTION = "caution"
    NOT_RECOMMENDED = "not_recommended"


class OverallAdviceStatus(StrEnum):
    SUITABLE = "suitable"
    SOME_DATES_CAUTION = "some_dates_caution"
    SOME_DATES_NOT_RECOMMENDED = "some_dates_not_recommended"


class SourceKind(StrEnum):
    LIVE = "live"
    CACHE = "cache"
    DEMO = "demo"
    DEGRADED = "degraded"


class Coordinate(DomainModel):
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    system: str = "gcj02"


class RankingWeights(DomainModel):
    weather: float = Field(ge=0, le=100)
    distance: float = Field(ge=0, le=100)
    fairness: float = Field(ge=0, le=100)
    popularity: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def require_positive_total(self) -> RankingWeights:
        if self.weather + self.distance + self.fairness + self.popularity <= 0:
            raise ValueError("at least one ranking weight must be positive")
        return self


class TravelRequestBase(DomainModel):
    city: str = "苏州"
    main_origin: str = Field(min_length=1, max_length=200)
    companion_origins: list[str] = Field(default_factory=list, max_length=2)
    max_distance_km: float = Field(gt=0, le=500)
    start_date: date
    end_date: date
    weights: RankingWeights | None = None

    @field_validator("city")
    @classmethod
    def default_blank_city(cls, value: str) -> str:
        return value.strip() or "苏州"

    @field_validator("main_origin")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("companion_origins")
    @classmethod
    def strip_companions(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("companion origin must not be blank")
        return cleaned

    @model_validator(mode="after")
    def validate_dates(self) -> TravelRequestBase:
        china_time = timezone(timedelta(hours=8))
        today = datetime.now(china_time).date()
        if self.start_date < today or self.end_date < self.start_date:
            raise ValueError("date range must start today or later")
        if (self.end_date - today).days > 6:
            raise ValueError("date range must stay within the next 7 days")
        if self.weights is not None:
            total = sum(self.weights.model_dump().values())
            if abs(total - 100) > 1e-6:
                raise ValueError("explicit ranking weights must total 100")
            if self.origin_count == 1 and self.weights.fairness != 0:
                raise ValueError("single-origin fairness weight must be zero")
            if self.origin_count > 1 and self.weights.fairness != 20:
                raise ValueError("multi-origin fairness weight must be 20")
        return self

    @computed_field
    @property
    def origin_count(self) -> int:
        return 1 + len(self.companion_origins)


class RecommendationRequest(TravelRequestBase):
    scenery_types: list[SceneryType] = Field(min_length=1)
    scenery_match_mode: SceneryMatchMode = SceneryMatchMode.ANY


class ExplanationContext(DomainModel):
    requested_scenery_types: tuple[SceneryType, ...]
    scenery_match_mode: SceneryMatchMode
    display_weights: RankingWeights


class PlaceEvaluationRequest(TravelRequestBase):
    target_place: str = Field(min_length=1, max_length=200)

    @field_validator("target_place")
    @classmethod
    def strip_target(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("target place must not be blank")
        return value


class Origin(DomainModel):
    label: str
    address: str
    coordinate: Coordinate


class Destination(DomainModel):
    provider_id: str
    name: str
    address: str
    city: str
    coordinate: Coordinate
    type_name: str
    type_code: str
    scenery_tags: frozenset[SceneryType] = frozenset()
    popularity_rank: int = Field(ge=1)
    rating: float | None = Field(default=None, ge=0, le=5)


class DailyWeather(DomainModel):
    date: date
    condition: str
    temp_min_c: float
    temp_max_c: float
    precipitation_mm: float = Field(ge=0)
    wind_speed_kmh: float = Field(ge=0)
    humidity_percent: float = Field(ge=0, le=100)
    visibility_km: float = Field(ge=0)
    uv_index: float = Field(ge=0)


class DailySuitability(DomainModel):
    date: date
    score: float = Field(ge=0, le=100)
    reasons: list[str] = Field(min_length=1)
    status: TravelAdviceStatus | None = None
    summary: str | None = None


class DistanceEstimate(DomainModel):
    origin_label: str
    distance_km: float = Field(ge=0)
    duration_minutes: float | None = Field(default=None, ge=0)
    estimated: bool = False


class GroupAccessibilityScore(DomainModel):
    average_distance_km: float = Field(ge=0)
    max_distance_km: float = Field(ge=0)
    distance_variance: float = Field(ge=0)
    distance_stddev: float = Field(ge=0)
    fairness_score: float = Field(ge=0, le=100)


class ScoreBreakdown(DomainModel):
    weather: float = Field(ge=0, le=100)
    distance: float = Field(ge=0, le=100)
    fairness: float = Field(ge=0, le=100)
    popularity: float | None = Field(ge=0, le=100)
    coverage_penalty: float = Field(ge=0, le=100)
    total: float = Field(ge=0, le=100)


class SourceState(DomainModel):
    kind: SourceKind
    notices: list[str] = Field(default_factory=list)


class RecommendationItem(DomainModel):
    destination: Destination
    distances: list[DistanceEstimate]
    group_accessibility: GroupAccessibilityScore
    weather: list[DailyWeather]
    daily_suitability: list[DailySuitability]
    score: ScoreBreakdown
    explanation: str
    overall_advice: OverallAdviceStatus | None = None


class RecommendationResponse(DomainModel):
    items: list[RecommendationItem]
    source_state: SourceState
    generated_at: str
    uncovered_scenery_types: list[SceneryType] = Field(default_factory=list)


class PlaceEvaluationResponse(DomainModel):
    item: RecommendationItem
    source_state: SourceState
    generated_at: str
