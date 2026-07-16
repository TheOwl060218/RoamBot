import pytest

from roambot.domain.models import RankingWeights
from roambot.domain.ranking import final_score, normalize_weights


def test_weights_are_normalized() -> None:
    normalized = normalize_weights(
        RankingWeights(weather=4, distance=3, fairness=0, popularity=3)
    )

    assert normalized == {
        "weather": 0.4,
        "distance": 0.3,
        "fairness": 0.0,
        "popularity": 0.3,
    }


def test_coverage_penalty_reduces_total() -> None:
    weights = RankingWeights(weather=40, distance=30, fairness=0, popularity=30)

    full = final_score(80, 80, 100, 80, weights, coverage_ratio=1)
    partial = final_score(80, 80, 100, 80, weights, coverage_ratio=0.5)

    assert full == pytest.approx(80)
    assert partial == pytest.approx(70)
