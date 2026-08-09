from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from roambot.api.dependencies import get_provider_bundle
from roambot.domain.models import PlaceSuggestion
from roambot.providers.factory import ProviderBundle
from roambot.providers.protocols import ProviderError

router = APIRouter(prefix="/places", tags=["places"])
PROVIDER_BUNDLE_DEPENDENCY = Depends(get_provider_bundle)


class PlaceSuggestionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggestions: list[PlaceSuggestion]


@router.get("/suggestions", response_model=PlaceSuggestionsResponse)
def suggestions(
    keywords: str = Query(min_length=2, max_length=80),
    city: str = Query(default="苏州", max_length=80),
    bundle: ProviderBundle = PROVIDER_BUNDLE_DEPENDENCY,
) -> PlaceSuggestionsResponse:
    try:
        values = bundle.places.suggest(keywords, city)
    except ProviderError:
        values = []
    return PlaceSuggestionsResponse(suggestions=values)
