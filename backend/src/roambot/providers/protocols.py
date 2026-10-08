from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from roambot.domain.models import (
    Coordinate,
    DailyWeather,
    Destination,
    DistanceEstimate,
    ExplanationContext,
    Origin,
    PlaceSuggestion,
    RecommendationItem,
    SceneryType,
)


class ProviderError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class PlaceSearchResults(list[Destination]):
    """Request-local search metadata, without mutable state on shared providers."""

    def __init__(self, values=(), *, region_metadata_missing: bool = False):
        super().__init__(values)
        self.region_metadata_missing = region_metadata_missing


@runtime_checkable
class Geocoder(Protocol):
    def geocode(self, address: str, city: str) -> Origin:
        raise NotImplementedError


@runtime_checkable
class PlaceProvider(Protocol):
    def suggest(self, keywords: str, city: str) -> list[PlaceSuggestion]:
        raise NotImplementedError

    def search(
        self,
        center: Coordinate,
        city: str,
        scenery_types: tuple[SceneryType, ...],
        radius_km: float,
        destination_regions: tuple[str, ...] = (),
    ) -> list[Destination]:
        raise NotImplementedError

    def resolve(self, name: str, city: str) -> Destination:
        raise NotImplementedError


@runtime_checkable
class DistanceProvider(Protocol):
    def measure(self, origins: list[Origin], destination: Destination) -> list[DistanceEstimate]:
        raise NotImplementedError


@runtime_checkable
class WeatherProvider(Protocol):
    def daily(self, coordinate: Coordinate, start: date, end: date) -> list[DailyWeather]:
        raise NotImplementedError


@runtime_checkable
class ExplanationProvider(Protocol):
    def explain(
        self,
        items: list[RecommendationItem],
        context: ExplanationContext,
    ) -> list[str]:
        raise NotImplementedError
