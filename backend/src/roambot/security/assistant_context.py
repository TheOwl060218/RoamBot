"""Ephemeral, signed, strictly whitelisted facts. Not an authentication token."""
from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import Callable
from datetime import datetime, timedelta

from pydantic import Field

from roambot.domain.models import (
    DailyWeather,
    DistanceEstimate,
    DomainModel,
    GroupAccessibilityScore,
    PlaceEvaluationResponse,
    RecommendationResponse,
    ScoreBreakdown,
    SourceKind,
    TravelAdviceStatus,
)


class FactDestination(DomainModel):
    name: str = Field(max_length=200)
    city: str = Field(max_length=100)
    type_name: str = Field(max_length=200)
    scenery_tags: list[str] = Field(max_length=6)
    rating: float | None = Field(default=None, ge=0, le=5)


class FactSuitability(DomainModel):
    date: str
    score: float = Field(ge=0, le=100)
    status: TravelAdviceStatus | None


class FactCandidate(DomainModel):
    candidate_id: str = Field(max_length=200)
    destination: FactDestination
    distances: list[DistanceEstimate] = Field(max_length=3)
    weather: list[DailyWeather] = Field(max_length=7)
    daily_suitability: list[FactSuitability] = Field(max_length=7)
    group_accessibility: GroupAccessibilityScore
    score: ScoreBreakdown


class AssistantFacts(DomainModel):
    candidates: list[FactCandidate] = Field(max_length=7)
    source_state: SourceKind
    issued_at: datetime
    expires_at: datetime


class AssistantContextSigner:
    def __init__(self, secret: bytes, clock: Callable[[], datetime]):
        self._secret = secret
        self._clock = clock

    def issue(self, result: RecommendationResponse | PlaceEvaluationResponse) -> str:
        items = result.items if isinstance(result, RecommendationResponse) else [result.item]
        candidates = []
        for item in items:
            destination = item.destination
            candidates.append(FactCandidate(
                candidate_id=destination.provider_id,
                destination=FactDestination(
                    name=destination.name, city=destination.city,
                    type_name=destination.type_name,
                    scenery_tags=sorted(destination.scenery_tags), rating=destination.rating),
                distances=[distance.model_copy(update={
                    "origin_label": "主出发地" if i == 0 else f"同行{i}"
                }) for i, distance in enumerate(item.distances)],
                weather=item.weather,
                daily_suitability=[FactSuitability(date=d.date.isoformat(), score=d.score,
                                                   status=d.status)
                                   for d in item.daily_suitability],
                group_accessibility=item.group_accessibility, score=item.score,
            ))
        now = self._clock()
        facts = AssistantFacts(candidates=candidates, source_state=result.source_state.kind,
                               issued_at=now, expires_at=now + timedelta(minutes=30))
        raw = facts.model_dump_json().encode()
        if len(raw) > 32768:
            raise ValueError("facts too large")
        payload = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        signature = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}.{signature}"

    def verify(self, value: str) -> AssistantFacts:
        try:
            if len(value) > 65536:
                raise ValueError
            payload, signature = value.split(".")
            expected = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError
            raw = base64.b64decode(payload + "=" * (-len(payload) % 4),
                                   altchars=b"-_", validate=True)
            if len(raw) > 32768:
                raise ValueError
            facts = AssistantFacts.model_validate_json(raw)
            now = self._clock()
            if not facts.issued_at <= now < facts.expires_at:
                raise ValueError
            return facts
        except (ValueError, TypeError):
            raise ValueError("result context unavailable; update explicitly") from None
