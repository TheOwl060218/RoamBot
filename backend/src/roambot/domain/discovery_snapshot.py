"""Versioned actual discovery facts; no synthetic legacy scores or categories."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from roambot.domain.discovery import SearchContext
from roambot.domain.assistant import AssistantMessage
from roambot.domain.models import Coordinate, DailyWeather


class SnapshotModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class EvidenceSource(SnapshotModel):
    id: str
    kind: str
    title: str = ""
    url: str = ""
    excerpt: str = ""


class StoredPlace(SnapshotModel):
    id: str
    name: str
    address: str
    city: str
    coordinate: Coordinate
    map_type: str
    map_url: str
    facts: dict[str, str] = Field(default_factory=dict)


class Unavailable(SnapshotModel):
    unavailable: Literal[True]


class RouteFact(SnapshotModel):
    mode: Literal["walking", "bicycling", "driving"]
    distance_km: float
    duration_minutes: float


class StoredCard(SnapshotModel):
    place: StoredPlace
    experience: str
    reason: str
    sources: list[EvidenceSource] = Field(max_length=8)
    route: RouteFact | Unavailable | None = None
    weather: list[DailyWeather] | Unavailable | None = None


class DiscoveryArchiveRequest(SnapshotModel):
    message: str
    search_request: str | None = Field(default=None, max_length=200)
    context: SearchContext
    location: Coordinate | None = None
    conversation: list[AssistantMessage] = Field(default_factory=list, max_length=10)


class DiscoveryArchive(SnapshotModel):
    schema_version: Literal["discovery-v1"] = "discovery-v1"
    generated_at: datetime
    source: Literal["live", "demo"]
    status: Literal["completed", "partial"]
    cards: list[StoredCard] = Field(min_length=1, max_length=24)


class PublicPlace(SnapshotModel):
    name: str
    address: str
    city: str
    map_type: str


class PublicCard(SnapshotModel):
    place: PublicPlace
    experience: str
    reason: str
    sources: list[EvidenceSource]
    weather: list[DailyWeather] | None = None


class PublicDiscoverySnapshot(SnapshotModel):
    schema_version: Literal["discovery-v1"] = "discovery-v1"
    mode: Literal["discovery"] = "discovery"
    city: str
    start_date: str | None
    end_date: str | None
    generated_at: datetime
    cards: list[PublicCard]


class DiscoveryPlanSnapshot(SnapshotModel):
    schema_version: Literal["discovery-v1"] = "discovery-v1"
    destination: PublicPlace
    experience: str
    reason: str
    sources: list[EvidenceSource]
    weather: list[DailyWeather] = Field(default_factory=list)
    source: Literal["live", "demo"]
