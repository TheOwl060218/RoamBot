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


def post_to_app(path: str, request: dict[str, object]):
    with TestClient(create_app()) as client:
        return client.post(path, json=request)


def test_guest_recommendation_returns_ranked_items() -> None:
    response = post_to_app("/api/v1/recommendations", payload())

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["destination"]["name"] == VALID_DESTINATION.name
    assert body["items"][0]["destination"]["rating"] == 4.8
    assert body["items"][0]["daily_suitability"][0]["status"] in {
        "suitable",
        "caution",
        "not_recommended",
    }
    assert body["items"][0]["daily_suitability"][0]["summary"]
    assert body["items"][0]["overall_advice"] in {
        "suitable",
        "some_dates_caution",
        "some_dates_not_recommended",
    }
    assert body["uncovered_scenery_types"] == []
    assert body["source_state"]["kind"] == "demo"


def test_guest_place_evaluation_returns_requested_item() -> None:
    response = post_to_app(
        "/api/v1/place-evaluations",
        evaluation_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["item"]["destination"]["name"] == VALID_DESTINATION.name
    assert body["source_state"]["kind"] == "demo"


def test_place_suggestions_return_limited_current_city_matches() -> None:
    with TestClient(create_app()) as client:
        response = client.get(
            "/api/v1/places/suggestions",
            params={"keywords": "苏州", "city": "苏州"},
        )

    assert response.status_code == 200
    assert len(response.json()["suggestions"]) <= 5


def test_invalid_request_returns_stable_error() -> None:
    invalid = payload()
    invalid["max_distance_km"] = 0

    response = post_to_app("/api/v1/recommendations", invalid)

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

    response = post_to_app("/api/v1/recommendations", request)

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

    response = post_to_app("/api/v1/place-evaluations", request)

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "place_not_found",
            "message": "Place could not be found.",
            "fields": [{"path": "target_place", "message": "Place could not be found."}],
        }
    }


def test_recommendation_place_search_not_found_returns_provider_unavailable(
    monkeypatch,
) -> None:
    class NotFoundPlaceSearchProvider:
        def search(self, *args: object, **kwargs: object) -> object:
            raise ProviderError("not_found", "provider-specific search details")

    bundle = MockProviderBundle.default()
    failing_bundle = replace(bundle, places=NotFoundPlaceSearchProvider())
    monkeypatch.setattr(MockProviderBundle, "default", staticmethod(lambda: failing_bundle))

    response = post_to_app("/api/v1/recommendations", payload())

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "provider_unavailable",
            "message": "Provider is temporarily unavailable.",
            "fields": [],
        }
    }
    assert "provider-specific search details" not in response.text


def test_place_evaluation_distance_failure_returns_straight_line_estimate(
    monkeypatch,
) -> None:
    class NotFoundDistanceProvider:
        def measure(self, *args: object, **kwargs: object) -> object:
            raise ProviderError("not_found", "provider-specific distance details")

    bundle = MockProviderBundle.default()
    failing_bundle = replace(bundle, distance=NotFoundDistanceProvider())
    monkeypatch.setattr(MockProviderBundle, "default", staticmethod(lambda: failing_bundle))

    response = post_to_app(
        "/api/v1/place-evaluations",
        evaluation_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["item"]["distances"][0]["estimated"] is True
    assert body["item"]["distances"][0]["duration_minutes"] is None
    assert body["source_state"] == {
        "kind": "degraded",
        "notices": ["使用内置苏州演示数据", "部分路程使用直线距离估算"],
    }
    assert "provider-specific distance details" not in response.text


def test_recommendation_unknown_companion_reports_actual_field_path() -> None:
    request = payload()
    request["companion_origins"] = ["unknown companion"]

    response = post_to_app("/api/v1/recommendations", request)

    assert response.status_code == 422
    assert response.json()["error"]["fields"] == [
        {
            "path": "companion_origins[0]",
            "message": "Origin could not be resolved.",
        }
    ]


def test_place_evaluation_unknown_companion_reports_actual_field_path() -> None:
    request = evaluation_payload()
    request["companion_origins"] = ["unknown companion"]

    response = post_to_app("/api/v1/place-evaluations", request)

    assert response.status_code == 422
    assert response.json()["error"]["fields"] == [
        {
            "path": "companion_origins[0]",
            "message": "Origin could not be resolved.",
        }
    ]


def test_place_evaluation_geocodes_origin_without_target_city_hint(monkeypatch) -> None:
    class CountingGeocoder:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def geocode(self, address: str, city: str) -> object:
            self.calls.append((address, city))
            return next(iter(ORIGINS.values()))

    bundle = MockProviderBundle.default()
    geocoder = CountingGeocoder()
    counting_bundle = replace(bundle, geocoder=geocoder)
    monkeypatch.setattr(MockProviderBundle, "default", staticmethod(lambda: counting_bundle))

    response = post_to_app(
        "/api/v1/place-evaluations",
        evaluation_payload(),
    )

    assert response.status_code == 200
    assert geocoder.calls == [(VALID_ORIGIN, "")]


def test_weather_provider_failure_returns_stable_unavailable(
    monkeypatch,
) -> None:
    class FailingWeatherProvider:
        def daily(self, *args: object, **kwargs: object) -> object:
            raise ProviderError("weather_unavailable", "secret provider outage details")

    bundle = MockProviderBundle.default()
    failing_bundle = replace(bundle, weather=FailingWeatherProvider())
    monkeypatch.setattr(MockProviderBundle, "default", staticmethod(lambda: failing_bundle))

    response = post_to_app("/api/v1/recommendations", payload())

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
