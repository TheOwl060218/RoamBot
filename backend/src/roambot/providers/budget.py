from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from roambot.providers.protocols import ProviderError


class ProviderOperation(StrEnum):
    GEOCODE = "geocode"
    POI_SEARCH = "poi_search"
    WEATHER = "weather"
    DISTANCE = "distance"
    LLM = "llm"


class ProviderBudgetExceeded(ProviderError):
    def __init__(self, operation: ProviderOperation, limit: int) -> None:
        super().__init__(
            "budget_exceeded",
            f"Provider call budget exceeded for {operation.value} (limit {limit}).",
        )
        self.operation = operation
        self.limit = limit


class ProviderBudget:
    def __init__(self, limits: Mapping[ProviderOperation, int]) -> None:
        if set(limits) != set(ProviderOperation):
            raise ValueError("limits must define every provider operation")
        if any(not isinstance(limit, int) or limit < 0 for limit in limits.values()):
            raise ValueError("provider limits must be non-negative integers")
        self.limits = dict(limits)
        self._counts = {operation: 0 for operation in ProviderOperation}

    def consume(self, operation: ProviderOperation) -> None:
        limit = self.limits[operation]
        if self._counts[operation] >= limit:
            raise ProviderBudgetExceeded(operation, limit)
        self._counts[operation] += 1

    def count(self, operation: ProviderOperation) -> int:
        return self._counts[operation]
