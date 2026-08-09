from __future__ import annotations

from roambot.domain.models import RankingWeights
from roambot.domain.scoring import clamp


def normalize_weights(weights: RankingWeights) -> dict[str, float]:
    values = weights.model_dump()
    total = sum(values.values())
    return {name: value / total for name, value in values.items()}


def final_score(
    weather: float,
    distance: float,
    fairness: float,
    popularity: float | None,
    weights: RankingWeights,
    coverage_ratio: float,
) -> float:
    del coverage_ratio
    total_weight = sum(weights.model_dump().values())
    fairness_fraction = weights.fairness / total_weight
    base_fraction = 1 - fairness_fraction
    base_values = {
        "weather": weather,
        "distance": distance,
        "popularity": popularity,
    }
    available = {
        name: value
        for name, value in base_values.items()
        if value is not None and getattr(weights, name) > 0
    }
    available_weight = sum(getattr(weights, name) for name in available)
    weighted_base = 0.0
    if available_weight > 0:
        weighted_base = sum(
            value * getattr(weights, name) / available_weight
            for name, value in available.items()
        )
    return clamp(weighted_base * base_fraction + fairness * fairness_fraction)
