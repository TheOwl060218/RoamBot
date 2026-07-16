from __future__ import annotations

from datetime import UTC, datetime

from roambot.domain.models import SourceKind
from roambot.providers.mock import MockProviderBundle
from roambot.services.recommendations import RecommendationService


def get_recommendation_service() -> RecommendationService:
    bundle = MockProviderBundle.default()
    return RecommendationService(
        geocoder=bundle.geocoder,
        places=bundle.places,
        distance=bundle.distance,
        weather=bundle.weather,
        explanations=bundle.explanations,
        source_kind=SourceKind.DEMO,
        clock=lambda: datetime.now(UTC),
    )
