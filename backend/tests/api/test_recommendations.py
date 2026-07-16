from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from fastapi.testclient import TestClient

from roambot.main import create_app
from roambot.providers.mock import DESTINATIONS, ORIGINS, MockProviderBundle
from roambot.providers.protocols import ProviderError

VALID_CITY = next(iter(ORIGINS))[1]
VALID_ORIGIN = next(iter(ORIGINS))[0]
VALID_DESTINATION = DESTINATIONS[0]


def payload() -> dict[str, object]:
    start = date.today() + timedelta(days=1)
    return {
        "city": VALID_CITY,
        "main_origin": VALID_ORIGIN,
        "companion_origins": [],
        "max_distance_km": 80,
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=2)).isoformat(),
        "scenery_types": ["lake", "park"],
        "scenery_match_mode": "any",
    }


def evaluation_payload() -> dict[str, object]:
    request = payload()
    del request["scenery_types"]
    del request["scenery_match_mode"]
    request["target_place"] = VALID_DESTINATION.name
    return request


def test_guest_recommendation_returns_ranked_items() -> None:
    response = TestClient(create_app()).post("/api/v1/recommendations", json=payload())

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["destination"]["name"] == VALID_DESTINATION.name
    assert body["source_state"]["kind"] == "demo"


def test_guest_place_evaluation_returns_requested_item() -> None:
    response = TestClient(create_app()).post(
        "/api/v1/place-evaluations",
        json=evaluation_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["item"]["destination"]["name"] == VALID_DESTINATION.name
    assert body["source_state"]["kind"] == "demo"


def test_invalid_request_returns_stable_error() -> None:
    invalid = payload()
    invalid["max_distance_km"] = 0

    response = TestClient(create_app()).post("/api/v1/recommendations", json=invalid)

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "Request validation failed.",
            "fields": [
                {
                    "path": "max_distance_km",
                    "message": "Input should be greater than 0",
                }
            ],
        }
    }
    assert "traceback" not in response.text.lower()


def test_unknown_origin_returns_origin_not_found() -> None:
    request = payload()
    request["main_origin"] = "unknown origin"

    response = TestClient(create_app()).post("/api/v1/recommendations", json=request)

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "origin_not_found",
            "message": "Origin could not be resolved.",
            "fields": [{"path": "main_origin", "message": "Origin could not be resolved."}],
        }
    }


def test_unknown_target_place_returns_place_not_found() -> None:
    request = evaluation_payload()
    request["target_place"] = "unknown place"

    response = TestClient(create_app()).post("/api/v1/place-evaluations", json=request)

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "place_not_found",
            "message": "Place could not be found.",
            "fields": [{"path": "target_place", "message": "Place could not be found."}],
        }
    }


def test_weather_provider_failure_returns_stable_unavailable(
    monkeypatch,
) -> None:
    class FailingWeatherProvider:
        def daily(self, *args: object, **kwargs: object) -> object:
            raise ProviderError("weather_unavailable", "secret provider outage details")

    bundle = MockProviderBundle.default()
    failing_bundle = replace(bundle, weather=FailingWeatherProvider())
    monkeypatch.setattr(MockProviderBundle, "default", staticmethod(lambda: failing_bundle))

    response = TestClient(create_app()).post("/api/v1/recommendations", json=payload())

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "provider_unavailable",
            "message": "Provider is temporarily unavailable.",
            "fields": [],
        }
    }
    assert "secret provider outage details" not in response.text
    assert "traceback" not in response.text.lower()
