"""Separate owner/public response contracts; public values use a strict field whitelist."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from roambot.domain.models import (
    DailySuitability,
    DailyWeather,
    GroupAccessibilityScore,
    ScoreBreakdown,
    SourceState,
)
from roambot.domain.discovery_snapshot import DiscoveryPlanSnapshot


class PublicDestination(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    address: str
    city: str
    scenery_tags: list[str]
    rating: float | None


class PlanSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")
    destination: PublicDestination
    weather: list[DailyWeather]
    daily_suitability: list[DailySuitability]
    score: ScoreBreakdown
    explanation: str
    overall_advice: str | None
    group_accessibility: GroupAccessibilityScore
    source_state: SourceState | None = None


class WeatherCheck(BaseModel):
    checked_at: datetime
    status: str
    source: str
    change: str
    risk: str | None
    weather: list[DailyWeather] | None
    daily_suitability: list[DailySuitability] = Field(default_factory=list)
    last_success_at: datetime | None


class PlanCandidate(BaseModel):
    id: str
    snapshot: PlanSnapshot | DiscoveryPlanSnapshot
    latest_weather: WeatherCheck | None


class Participant(BaseModel):
    id: str
    nickname: str
    role: Literal["owner", "guest"]
    voted: bool


class OwnVote(BaseModel):
    id: str
    nickname: str
    preferred_id: str | None
    acceptable_ids: list[str]


class CandidateTally(BaseModel):
    id: str
    preferred_count: int
    acceptable_count: int
    all_accept: bool


class VoteSummary(BaseModel):
    voted_count: int
    joined_count: int
    complete: bool
    candidates: list[CandidateTally]


class PublicPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    city: str
    start_date: str
    end_date: str
    expected_count: int
    status: Literal["voting", "closed", "decided"]
    final_candidate_id: str | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime
    ended: bool
    candidates: list[PlanCandidate]
    participants: list[Participant] | None
    summary: VoteSummary | None
    me: OwnVote | None
    next_weather_check_at: datetime | None


class OwnedPlan(PublicPlan):
    invite_active: bool


class OwnedEnvelope(BaseModel):
    plan: OwnedPlan


class PublicEnvelope(BaseModel):
    plan: PublicPlan
    anonymous_csrf: str | None = None


class PlanList(BaseModel):
    plans: list[OwnedPlan]
