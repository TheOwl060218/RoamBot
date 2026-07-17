from __future__ import annotations

import json
import re
from datetime import date, timedelta

from sqlalchemy import select

from roambot.api.dependencies import get_recommendation_service
from roambot.persistence.tables import HistoryTable, ShareTable
from roambot.providers.mock import DESTINATIONS, ORIGINS
from roambot.security.sessions import hash_token

HISTORY_URL = "/api/v1/history"
PASSWORD = "correct horse battery staple"
VALID_ORIGINS = list(ORIGINS)
VALID_CITY = VALID_ORIGINS[0][1]
VALID_ORIGIN = VALID_ORIGINS[0][0]
VALID_COMPANION = VALID_ORIGINS[1][0]


def register(client, username: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": PASSWORD},
    )
    assert response.status_code == 201
    return response.json()["csrf_token"]


def recommendation_payload(*, with_companion: bool = False) -> dict[str, object]:
    start = date.today() + timedelta(days=1)
    return {
        "city": VALID_CITY,
        "main_origin": VALID_ORIGIN,
        "companion_origins": [VALID_COMPANION] if with_companion else [],
        "max_distance_km": 80,
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=2)).isoformat(),
        "scenery_types": ["lake", "park"],
        "scenery_match_mode": "any",
    }


def create_history(client, csrf: str, *, with_companion: bool = False) -> str:
    before = set(history_ids(client))
    response = client.post(
        "/api/v1/recommendations",
        json=recommendation_payload(with_companion=with_companion),
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    created = set(history_ids(client)) - before
    assert len(created) == 1
    return created.pop()


def history_ids(client) -> list[str]:
    response = client.get(HISTORY_URL)
    assert response.status_code == 200
    return [item["id"] for item in response.json()["histories"]]


def create_share(client, csrf: str, history_id: str):
    return client.post(
        f"{HISTORY_URL}/{history_id}/share",
        headers={"X-CSRF-Token": csrf},
    )


def token_from_url(url: str) -> str:
    match = re.fullmatch(r"/share/([A-Za-z0-9_-]{43})", url)
    assert match is not None
    return match.group(1)


def public_url(url: str) -> str:
    return f"/api/v1/public/shares/{token_from_url(url)}"


def assert_error(response, status_code: int, code: str) -> None:
    assert response.status_code == status_code
    assert response.json()["error"]["code"] == code


def test_share_mutations_require_owner_session_and_csrf_and_replace_old_link(
    auth_api_fixture,
) -> None:
    client, _, session_factory = auth_api_fixture()

    assert_error(create_share(client, "missing", "missing"), 401, "authentication_required")
    assert_error(
        client.delete(
            "/api/v1/shares/missing",
            headers={"X-CSRF-Token": "missing"},
        ),
        401,
        "authentication_required",
    )

    alice_csrf = register(client, "alice_01")
    history_id = create_history(client, alice_csrf)
    assert_error(create_share(client, "", history_id), 403, "csrf_invalid")

    first = create_share(client, alice_csrf, history_id)
    assert first.status_code == 201
    assert set(first.json()) == {"share"}
    first_share = first.json()["share"]
    assert set(first_share) == {"id", "history_id", "url", "created_at"}
    assert first_share["history_id"] == history_id
    first_token = token_from_url(first_share["url"])

    with session_factory() as db:
        first_row = db.scalar(select(ShareTable))
        assert first_row is not None
        assert first_row.token_hash == hash_token(first_token)
        assert first_row.token_hash != first_token
        assert len(first_row.token_hash) == 64

    second = create_share(client, alice_csrf, history_id)
    assert second.status_code == 201
    second_share = second.json()["share"]
    second_token = token_from_url(second_share["url"])
    assert second_share["id"] != first_share["id"]
    assert second_token != first_token
    assert_error(
        client.get(public_url(first_share["url"])),
        404,
        "share_unavailable",
    )
    assert client.get(public_url(second_share["url"])).status_code == 200

    with session_factory() as db:
        rows = db.scalars(select(ShareTable).order_by(ShareTable.created_at)).all()
        assert len(rows) == 2
        by_id = {row.id: row for row in rows}
        assert by_id[first_share["id"]].revoked_at is not None
        assert by_id[second_share["id"]].revoked_at is None
        assert all(first_token != row.token_hash for row in rows)
        assert all(second_token != row.token_hash for row in rows)

    assert_error(
        client.delete(f"/api/v1/shares/{second_share['id']}"),
        403,
        "csrf_invalid",
    )
    revoked = client.delete(
        f"/api/v1/shares/{second_share['id']}",
        headers={"X-CSRF-Token": alice_csrf},
    )
    assert revoked.status_code == 204
    assert revoked.content == b""
    assert_error(client.get(public_url(second_share["url"])), 404, "share_unavailable")


def test_cross_user_share_create_and_revoke_are_uniform_resource_not_found(
    auth_api_fixture,
) -> None:
    client, _, _ = auth_api_fixture()
    alice_csrf = register(client, "alice_01")
    history_id = create_history(client, alice_csrf)
    share = create_share(client, alice_csrf, history_id).json()["share"]
    logout = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": alice_csrf},
    )
    assert logout.status_code == 204
    bob_csrf = register(client, "bob_01")

    assert_error(create_share(client, bob_csrf, history_id), 404, "resource_not_found")
    assert_error(
        client.delete(
            f"/api/v1/shares/{share['id']}",
            headers={"X-CSRF-Token": bob_csrf},
        ),
        404,
        "resource_not_found",
    )


def test_public_share_is_anonymous_fixed_deeply_sanitized_and_provider_free(
    auth_api_fixture,
) -> None:
    client, _, _ = auth_api_fixture()
    csrf = register(client, "alice_01")
    session_token = client.cookies.get("roambot_session")
    history_id = create_history(client, csrf, with_companion=True)
    private = client.get(f"{HISTORY_URL}/{history_id}").json()["history"]
    created = create_share(client, csrf, history_id).json()["share"]
    share_token = token_from_url(created["url"])

    class ProviderDependencyProbe:
        calls = 0

        def __call__(self):
            self.calls += 1
            raise AssertionError("public share must not resolve a provider")

    probe = ProviderDependencyProbe()
    client.app.dependency_overrides[get_recommendation_service] = probe
    client.cookies.clear()

    response = client.get(public_url(created["url"]))

    assert response.status_code == 200
    assert probe.calls == 0
    request = private["request"]
    result = private["result"]
    expected_items = [
        {
            "destination": {
                key: item["destination"][key]
                for key in ("name", "address", "city", "scenery_tags")
            },
            "weather": item["weather"],
            "daily_suitability": item["daily_suitability"],
            "score": item["score"],
            "explanation": item["explanation"],
        }
        for item in result["items"]
    ]
    expected = {
        "snapshot": {
            "mode": "recommendation",
            "city": request["city"],
            "companion_count": len(request["companion_origins"]),
            "start_date": request["start_date"],
            "end_date": request["end_date"],
            "items": expected_items,
            "generated_at": result["generated_at"],
        }
    }
    assert response.json() == expected

    serialized = json.dumps(response.json(), ensure_ascii=False)
    private_values = {
        request["main_origin"],
        *request["companion_origins"],
        "alice_01",
        history_id,
        created["id"],
        csrf,
        session_token,
        share_token,
    }
    assert all(value and value not in serialized for value in private_values)
    assert not {
        "main_origin",
        "companion_origins",
        "username",
        "user_id",
        "session",
        "csrf",
        "token",
        "id",
        "provider_id",
        "coordinate",
        "type_name",
        "type_code",
        "distances",
        "group_accessibility",
        "source_state",
    }.intersection(_recursive_keys(response.json()))


def test_public_share_removes_normalized_origin_labels_from_public_text(
    auth_api_fixture,
) -> None:
    client, _, session_factory = auth_api_fixture()
    csrf = register(client, "alice_01")
    history_id = create_history(client, csrf, with_companion=True)

    with session_factory.begin() as db:
        history = db.get(HistoryTable, history_id)
        assert history is not None
        result = json.loads(history.result_json)
        item = result["items"][0]
        item["distances"][0]["origin_label"] = "私密起点"
        item["distances"][1]["origin_label"] = "私密起点东门"
        item["explanation"] = "从私密起点东门出发比较方便。"
        item["daily_suitability"][0]["reasons"] = ["靠近私密起点东门"]
        history.result_json = json.dumps(result, ensure_ascii=False)

    share = create_share(client, csrf, history_id).json()["share"]
    response = client.get(public_url(share["url"]))

    assert response.status_code == 200
    serialized = json.dumps(response.json(), ensure_ascii=False)
    assert "私密起点" not in serialized
    assert "东门" not in serialized


def test_history_delete_and_clear_invalidate_shares_without_touching_favorites(
    auth_api_fixture,
) -> None:
    client, _, _ = auth_api_fixture()
    csrf = register(client, "alice_01")
    favorite = client.post(
        "/api/v1/favorites",
        json={
            "provider": "mock",
            "destination": DESTINATIONS[0].model_dump(mode="json"),
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert favorite.status_code == 201

    first_history_id = create_history(client, csrf)
    first_share = create_share(client, csrf, first_history_id).json()["share"]
    second_history_id = create_history(client, csrf)
    second_share = create_share(client, csrf, second_history_id).json()["share"]

    deleted = client.delete(
        f"{HISTORY_URL}/{first_history_id}",
        headers={"X-CSRF-Token": csrf},
    )
    assert deleted.status_code == 204
    first_unavailable = client.get(public_url(first_share["url"]))

    cleared = client.delete(HISTORY_URL, headers={"X-CSRF-Token": csrf})
    assert cleared.status_code == 204
    second_unavailable = client.get(public_url(second_share["url"]))

    for response in (first_unavailable, second_unavailable):
        assert_error(response, 404, "share_unavailable")
    assert len(client.get("/api/v1/favorites").json()["favorites"]) == 1


def _recursive_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(
            *(_recursive_keys(item) for item in value.values()),
        )
    if isinstance(value, list):
        return set().union(*(_recursive_keys(item) for item in value))
    return set()
