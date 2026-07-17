from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select

from roambot.api.dependencies import get_recommendation_service
from roambot.persistence.tables import FavoriteTable, HistoryTable
from roambot.providers.mock import DESTINATIONS, ORIGINS, MockProviderBundle
from roambot.providers.protocols import ProviderError
from roambot.services.recommendations import RecommendationService

HISTORY_URL = "/api/v1/history"
PASSWORD = "correct horse battery staple"
VALID_CITY = next(iter(ORIGINS))[1]
VALID_ORIGIN = next(iter(ORIGINS))[0]


def register(client, username: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": PASSWORD},
    )
    assert response.status_code == 201
    return response.json()["csrf_token"]


def recommendation_payload() -> dict[str, object]:
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
    payload = recommendation_payload()
    payload.pop("scenery_types")
    payload.pop("scenery_match_mode")
    payload["target_place"] = DESTINATIONS[0].name
    return payload


def favorite_payload() -> dict[str, object]:
    return {
        "provider": "mock",
        "destination": DESTINATIONS[0].model_dump(mode="json"),
    }


def history_ids(client) -> list[str]:
    response = client.get(HISTORY_URL)
    assert response.status_code == 200
    return [item["id"] for item in response.json()["histories"]]


class CountingService:
    def __init__(self, delegate: RecommendationService, *, fail: bool = False) -> None:
        self.delegate = delegate
        self.fail = fail
        self.calls = 0

    def recommend(self, request):
        self.calls += 1
        if self.fail:
            raise ProviderError("unavailable", "provider secret")
        return self.delegate.recommend(request)

    def evaluate(self, request):
        self.calls += 1
        if self.fail:
            raise ProviderError("unavailable", "provider secret")
        return self.delegate.evaluate(request)


def recommendation_service() -> RecommendationService:
    bundle = MockProviderBundle.default()
    return RecommendationService(
        geocoder=bundle.geocoder,
        places=bundle.places,
        distance=bundle.distance,
        weather=bundle.weather,
        explanations=bundle.explanations,
        source_kind="demo",
        clock=lambda: datetime.now(UTC),
    )


def test_guest_core_success_creates_no_history(auth_api_fixture) -> None:
    client, _, session_factory = auth_api_fixture()

    recommendation = client.post(
        "/api/v1/recommendations", json=recommendation_payload()
    )
    evaluation = client.post("/api/v1/place-evaluations", json=evaluation_payload())

    assert recommendation.status_code == evaluation.status_code == 200
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(HistoryTable)) == 0


def test_logged_in_success_captures_both_complete_canonical_snapshots(
    auth_api_fixture,
) -> None:
    client, _, session_factory = auth_api_fixture()
    csrf = register(client, "alice_01")

    recommendation = client.post(
        "/api/v1/recommendations",
        json=recommendation_payload(),
        headers={"X-CSRF-Token": csrf},
    )
    evaluation = client.post(
        "/api/v1/place-evaluations",
        json=evaluation_payload(),
        headers={"X-CSRF-Token": csrf},
    )
    listed = client.get(HISTORY_URL)

    assert recommendation.status_code == evaluation.status_code == 200
    assert listed.status_code == 200
    summaries = listed.json()["histories"]
    assert {summary["mode"] for summary in summaries} == {
        "recommendation",
        "place_evaluation",
    }
    assert all("request" not in summary and "result" not in summary for summary in summaries)
    details = [
        client.get(f"{HISTORY_URL}/{summary['id']}").json()["history"]
        for summary in summaries
    ]
    by_mode = {detail["mode"]: detail for detail in details}
    assert by_mode["recommendation"]["result"] == recommendation.json()
    assert by_mode["place_evaluation"]["result"] == evaluation.json()
    assert all(detail["snapshot"] is True for detail in details)
    serialized = json.dumps(details).lower()
    for secret in ("password", "cookie", "csrf", "token", "authorization", "raw_provider"):
        assert secret not in serialized
    with session_factory() as db:
        rows = db.scalars(select(HistoryTable)).all()
        assert all(
            row.request_json
            == json.dumps(
                json.loads(row.request_json),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            for row in rows
        )


def test_logged_in_missing_csrf_makes_zero_provider_calls(auth_api_fixture) -> None:
    client, _, session_factory = auth_api_fixture()
    register(client, "alice_01")
    service = CountingService(recommendation_service())
    client.app.dependency_overrides[get_recommendation_service] = lambda: service

    recommendation = client.post(
        "/api/v1/recommendations", json=recommendation_payload()
    )
    evaluation = client.post("/api/v1/place-evaluations", json=evaluation_payload())

    assert recommendation.status_code == evaluation.status_code == 403
    assert service.calls == 0
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(HistoryTable)) == 0


def test_provider_failure_creates_no_history(auth_api_fixture) -> None:
    client, _, session_factory = auth_api_fixture()
    csrf = register(client, "alice_01")
    service = CountingService(recommendation_service(), fail=True)
    client.app.dependency_overrides[get_recommendation_service] = lambda: service

    response = client.post(
        "/api/v1/recommendations",
        json=recommendation_payload(),
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 503
    assert service.calls == 1
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(HistoryTable)) == 0


def test_cross_user_read_delete_and_rerun_are_uniform_404(auth_api_fixture) -> None:
    client, _, _ = auth_api_fixture()
    alice_csrf = register(client, "alice_01")
    client.post(
        "/api/v1/recommendations",
        json=recommendation_payload(),
        headers={"X-CSRF-Token": alice_csrf},
    )
    history_id = history_ids(client)[0]
    client.post(
        "/api/v1/auth/logout", headers={"X-CSRF-Token": alice_csrf}
    )
    bob_csrf = register(client, "bob_01")
    service = CountingService(recommendation_service())
    client.app.dependency_overrides[get_recommendation_service] = lambda: service

    responses = [
        client.get(f"{HISTORY_URL}/{history_id}"),
        client.delete(
            f"{HISTORY_URL}/{history_id}",
            headers={"X-CSRF-Token": bob_csrf},
        ),
        client.post(
            f"{HISTORY_URL}/{history_id}/rerun",
            headers={"X-CSRF-Token": bob_csrf},
        ),
    ]

    assert [response.status_code for response in responses] == [404, 404, 404]
    assert all(response.json()["error"]["code"] == "resource_not_found" for response in responses)
    assert service.calls == 0


def test_rerun_creates_new_id_and_keeps_old_snapshot_immutable(
    auth_api_fixture,
) -> None:
    client, _, _ = auth_api_fixture()
    csrf = register(client, "alice_01")
    client.post(
        "/api/v1/recommendations",
        json=recommendation_payload(),
        headers={"X-CSRF-Token": csrf},
    )
    old_id = history_ids(client)[0]
    old_before = client.get(f"{HISTORY_URL}/{old_id}").json()["history"]

    rerun = client.post(
        f"{HISTORY_URL}/{old_id}/rerun",
        headers={"X-CSRF-Token": csrf},
    )

    assert rerun.status_code == 200
    new_id = rerun.json()["history"]["id"]
    assert new_id != old_id
    assert history_ids(client)[0] == new_id
    assert client.get(f"{HISTORY_URL}/{old_id}").json()["history"] == old_before


def test_single_delete_removes_only_owned_history(auth_api_fixture) -> None:
    client, _, _ = auth_api_fixture()
    csrf = register(client, "alice_01")
    client.post(
        "/api/v1/recommendations",
        json=recommendation_payload(),
        headers={"X-CSRF-Token": csrf},
    )
    history_id = history_ids(client)[0]

    deleted = client.delete(
        f"{HISTORY_URL}/{history_id}", headers={"X-CSRF-Token": csrf}
    )

    assert deleted.status_code == 204
    assert history_ids(client) == []


def test_clear_removes_only_histories_and_keeps_favorite(auth_api_fixture) -> None:
    client, _, session_factory = auth_api_fixture()
    csrf = register(client, "alice_01")
    favorite = client.post(
        "/api/v1/favorites",
        json=favorite_payload(),
        headers={"X-CSRF-Token": csrf},
    )
    client.post(
        "/api/v1/recommendations",
        json=recommendation_payload(),
        headers={"X-CSRF-Token": csrf},
    )

    cleared = client.delete(HISTORY_URL, headers={"X-CSRF-Token": csrf})

    assert favorite.status_code == 201
    assert cleared.status_code == 204
    assert history_ids(client) == []
    assert len(client.get("/api/v1/favorites").json()["favorites"]) == 1
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(FavoriteTable)) == 1
