from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from roambot.domain.models import (
    PlaceEvaluationRequest,
    RankingWeights,
    RecommendationRequest,
    SceneryMatchMode,
    SceneryType,
)


def valid_dates() -> tuple[date, date]:
    start = datetime.now(timezone(timedelta(hours=8))).date() + timedelta(days=1)
    return start, start + timedelta(days=2)


def test_recommendation_accepts_three_origins_and_scenery() -> None:
    start, end = valid_dates()
    request = RecommendationRequest(
        city="苏州",
        main_origin="苏州站",
        companion_origins=["苏州园区站", "苏州新区站"],
        max_distance_km=80,
        start_date=start,
        end_date=end,
        scenery_types=[SceneryType.LAKE, SceneryType.PARK],
        scenery_match_mode=SceneryMatchMode.ANY,
    )

    assert request.origin_count == 3


def test_group_request_requires_fixed_twenty_percent_fairness() -> None:
    start, end = valid_dates()
    values = {
        "city": "苏州",
        "main_origin": "苏州站",
        "companion_origins": ["苏州园区站"],
        "max_distance_km": 80,
        "start_date": start,
        "end_date": end,
        "scenery_types": [SceneryType.LAKE],
    }

    request = RecommendationRequest.model_validate(
        {
            **values,
            "weights": RankingWeights(
                weather=32,
                distance=24,
                fairness=20,
                popularity=24,
            ),
        }
    )
    assert request.weights is not None
    assert request.weights.fairness == 20

    with pytest.raises(ValidationError):
        RecommendationRequest.model_validate(
            {
                **values,
                "weights": RankingWeights(
                    weather=40,
                    distance=20,
                    fairness=10,
                    popularity=30,
                ),
            }
        )


def test_explicit_weights_must_total_one_hundred() -> None:
    start, end = valid_dates()

    with pytest.raises(ValidationError):
        RecommendationRequest(
            city="苏州",
            main_origin="苏州站",
            max_distance_km=80,
            start_date=start,
            end_date=end,
            scenery_types=[SceneryType.LAKE],
            weights=RankingWeights(
                weather=4,
                distance=3,
                fairness=0,
                popularity=3,
            ),
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"main_origin": " "},
        {"companion_origins": ["a", "b", "c"]},
        {"max_distance_km": 0},
        {"scenery_types": []},
    ],
)
def test_recommendation_rejects_invalid_inputs(changes: dict[str, object]) -> None:
    start, end = valid_dates()
    values: dict[str, object] = {
        "city": "苏州",
        "main_origin": "苏州站",
        "companion_origins": [],
        "max_distance_km": 80,
        "start_date": start,
        "end_date": end,
        "scenery_types": [SceneryType.LAKE],
        "scenery_match_mode": SceneryMatchMode.ANY,
    }
    values.update(changes)

    with pytest.raises(ValidationError):
        RecommendationRequest.model_validate(values)


def test_place_evaluation_has_target_and_no_scenery_input() -> None:
    start, end = valid_dates()
    request = PlaceEvaluationRequest(
        city="苏州",
        main_origin="苏州站",
        target_place="金鸡湖",
        max_distance_km=80,
        start_date=start,
        end_date=end,
    )

    assert request.target_place == "金鸡湖"
    assert "scenery_types" not in type(request).model_fields


def test_date_window_is_today_through_six_days_later() -> None:
    today = datetime.now(timezone(timedelta(hours=8))).date()
    valid = {
        "city": "苏州",
        "main_origin": "苏州站",
        "max_distance_km": 80,
        "start_date": today,
        "end_date": today + timedelta(days=6),
        "scenery_types": [SceneryType.LAKE],
    }

    RecommendationRequest.model_validate(valid)
    with pytest.raises(ValidationError):
        RecommendationRequest.model_validate(
            {**valid, "end_date": today + timedelta(days=7)}
        )
