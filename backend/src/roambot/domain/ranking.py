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
    popularity: float,
    weights: RankingWeights,
    coverage_ratio: float,
) -> float:
    normalized = normalize_weights(weights)
    weighted = (
        weather * normalized["weather"]
        + distance * normalized["distance"]
        + fairness * normalized["fairness"]
        + popularity * normalized["popularity"]
    )
    coverage_penalty = 20 * (1 - max(0.0, min(1.0, coverage_ratio)))
    return clamp(weighted - coverage_penalty)
