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


def test_normalize_weights_keeps_full_precision() -> None:
    normalized = normalize_weights(
        RankingWeights(weather=1, distance=1, fairness=1, popularity=4)
    )

    assert normalized == pytest.approx(
        {
            "weather": 1 / 7,
            "distance": 1 / 7,
            "fairness": 1 / 7,
            "popularity": 4 / 7,
        }
    )
    assert sum(normalized.values()) == pytest.approx(1.0)


def test_final_score_clips_coverage_ratio_and_total_at_both_bounds() -> None:
    weights = RankingWeights(weather=1, distance=1, fairness=1, popularity=1)

    assert final_score(80, 80, 80, 80, weights, coverage_ratio=1.5) == 80
    assert final_score(80, 80, 80, 80, weights, coverage_ratio=-0.5) == 60
    assert final_score(120, 120, 120, 120, weights, coverage_ratio=5) == 100
    assert final_score(0, 0, 0, 0, weights, coverage_ratio=-5) == 0
