from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from roambot.persistence.tables import UserSessionTable, UserTable
from roambot.providers.mock import DESTINATIONS, ORIGINS
from roambot.security.sessions import hash_token

AUTH_PREFIX = "/api/v1/auth"
USERNAME = "alice_01"
PASSWORD = "correct horse battery staple"


def credentials(
    username: str = USERNAME,
    password: str = PASSWORD,
) -> dict[str, str]:
    return {"username": username, "password": password}


def assert_error(response, status_code: int, code: str, message: str) -> None:
    assert response.status_code == status_code
    assert response.json() == {
        "error": {"code": code, "message": message, "fields": []}
    }


def assert_session_cookie(response, *, secure: bool = False, max_age: int = 86400) -> str:
    header = response.headers["set-cookie"]
    assert "roambot_session=" in header
    assert "HttpOnly" in header
    assert "SameSite=lax" in header
    assert "Path=/" in header
    assert f"Max-Age={max_age}" in header
    assert ("Secure" in header) is secure
    return response.cookies["roambot_session"]


def test_register_auto_logs_in_and_never_persists_or_returns_plaintext(
    auth_api_fixture,
) -> None:
    client, _, session_factory = auth_api_fixture()

    response = client.post(f"{AUTH_PREFIX}/register", json=credentials())

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "user": {"username": USERNAME},
        "csrf_token": body["csrf_token"],
    }
    assert body["csrf_token"]
    session_token = assert_session_cookie(response)
    assert response.headers["cache-control"] == "no-store"
    assert session_token not in response.text
    assert "session_token" not in response.text
    with session_factory() as db:
        user = db.scalar(select(UserTable))
        session = db.scalar(select(UserSessionTable))
        assert user is not None
        assert session is not None
        assert user.password_hash != PASSWORD
        assert PASSWORD not in user.password_hash
        assert session.token_hash == hash_token(session_token)
        assert session.csrf_hash == hash_token(body["csrf_token"])
        assert session_token not in session.token_hash
        assert body["csrf_token"] not in session.csrf_hash


def test_login_returns_generic_credentials_errors_and_sets_new_session(
    auth_api_fixture,
) -> None:
    client, _, _ = auth_api_fixture()
    client.post(f"{AUTH_PREFIX}/register", json=credentials())

    unknown = client.post(
        f"{AUTH_PREFIX}/login",
        json=credentials(username="unknown_01"),
    )
    wrong = client.post(
        f"{AUTH_PREFIX}/login",
        json=credentials(password="incorrect password"),
    )
    logged_in = client.post(f"{AUTH_PREFIX}/login", json=credentials())

    expected_error = {
        "error": {
            "code": "invalid_credentials",
            "message": "Invalid username or password.",
            "fields": [],
        }
    }
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json() == expected_error
    assert logged_in.status_code == 200
    assert logged_in.json()["user"] == {"username": USERNAME}
    token = assert_session_cookie(logged_in)
    assert token not in logged_in.text
    assert logged_in.headers["cache-control"] == "no-store"


def test_duplicate_registration_returns_stable_username_taken_envelope(
    auth_api_fixture,
) -> None:
    client, _, _ = auth_api_fixture()
    client.post(f"{AUTH_PREFIX}/register", json=credentials())

    response = client.post(f"{AUTH_PREFIX}/register", json=credentials())

    assert_error(response, 409, "username_taken", "Username is already taken.")


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        (credentials(username="ab"), "username"),
        (credentials(username="alice-smith"), "username"),
        (credentials(password="short7"), "password"),
        (credentials(password="x" * 129), "password"),
    ],
)
def test_auth_payload_validation_uses_stable_envelope(
    payload: dict[str, str],
    field: str,
    auth_api_fixture,
) -> None:
    client, _, _ = auth_api_fixture()

    response = client.post(f"{AUTH_PREFIX}/register", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["fields"][0]["path"] == field


def test_me_rotates_csrf_without_sliding_expiration_and_old_csrf_fails_logout(
    auth_api_fixture,
) -> None:
    now = datetime(2026, 7, 16, 8, 0, tzinfo=UTC)
    client, _, session_factory = auth_api_fixture(clock=lambda: now)
    registered = client.post(f"{AUTH_PREFIX}/register", json=credentials())
    old_csrf = registered.json()["csrf_token"]
    session_token = registered.cookies["roambot_session"]
    with session_factory() as db:
        expires_before = db.scalar(select(UserSessionTable.expires_at))

    response = client.get(f"{AUTH_PREFIX}/me")

    assert response.status_code == 200
    new_csrf = response.json()["csrf_token"]
    assert response.json() == {
        "user": {"username": USERNAME},
        "csrf_token": new_csrf,
    }
    assert new_csrf != old_csrf
    assert session_token not in response.text
    assert response.headers["cache-control"] == "no-store"
    with session_factory() as db:
        stored = db.scalar(select(UserSessionTable))
        assert stored is not None
        assert stored.csrf_hash == hash_token(new_csrf)
        assert stored.csrf_hash != hash_token(old_csrf)
        assert stored.expires_at == expires_before

    missing = client.post(f"{AUTH_PREFIX}/logout")
    old = client.post(
        f"{AUTH_PREFIX}/logout",
        headers={"X-CSRF-Token": old_csrf},
    )
    assert_error(missing, 403, "csrf_invalid", "CSRF token is invalid.")
    assert_error(old, 403, "csrf_invalid", "CSRF token is invalid.")

    logged_out = client.post(
        f"{AUTH_PREFIX}/logout",
        headers={"X-CSRF-Token": new_csrf},
    )
    assert logged_out.status_code == 204
    assert logged_out.content == b""
    assert logged_out.headers["cache-control"] == "no-store"
    clear_cookie = logged_out.headers["set-cookie"]
    assert "roambot_session=" in clear_cookie
    assert "Max-Age=0" in clear_cookie
    assert "HttpOnly" in clear_cookie
    assert "SameSite=lax" in clear_cookie
    assert "Path=/" in clear_cookie
    assert "Secure" not in clear_cookie

    assert_error(
        client.get(f"{AUTH_PREFIX}/me"),
        401,
        "authentication_required",
        "Authentication is required.",
    )
    with TestClient(client.app) as replay_client:
        replay_client.cookies.set("roambot_session", session_token)
        replay = replay_client.get(f"{AUTH_PREFIX}/me")
        assert_error(
            replay,
            401,
            "authentication_required",
            "Authentication is required.",
        )


def test_me_without_session_returns_authentication_required(auth_api_fixture) -> None:
    client, _, _ = auth_api_fixture()

    response = client.get(f"{AUTH_PREFIX}/me")

    assert_error(
        response,
        401,
        "authentication_required",
        "Authentication is required.",
    )


def test_secure_cookie_and_configured_max_age_are_used(auth_api_fixture) -> None:
    client, _, _ = auth_api_fixture(secure_cookies=True, session_hours=12)

    response = client.post(f"{AUTH_PREFIX}/register", json=credentials())

    assert_session_cookie(response, secure=True, max_age=43200)


def test_guest_health_recommendation_and_place_evaluation_remain_public(
    auth_api_fixture,
) -> None:
    client, _, _ = auth_api_fixture()
    city = next(iter(ORIGINS))[1]
    origin = next(iter(ORIGINS))[0]
    start = date.today() + timedelta(days=1)
    common = {
        "city": city,
        "main_origin": origin,
        "companion_origins": [],
        "max_distance_km": 80,
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=2)).isoformat(),
    }

    health = client.get("/api/v1/health")
    recommendations = client.post(
        "/api/v1/recommendations",
        json={
            **common,
            "scenery_types": ["lake", "park"],
            "scenery_match_mode": "any",
        },
    )
    evaluation = client.post(
        "/api/v1/place-evaluations",
        json={**common, "target_place": DESTINATIONS[0].name},
    )

    assert health.status_code == 200
    assert recommendations.status_code == 200
    assert evaluation.status_code == 200
