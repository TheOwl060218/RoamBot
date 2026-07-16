from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from inspect import signature
from uuid import UUID

import pytest
from sqlalchemy import select

from roambot.persistence.repositories import SessionRepository
from roambot.persistence.tables import UserSessionTable, UserTable
from roambot.security.sessions import SessionSecrets, hash_token
from roambot.services.auth import (
    AuthError,
    AuthValidationError,
    DuplicateUsernameError,
    InvalidCredentialsError,
    InvalidSessionError,
)


def test_register_creates_user_and_fixed_session_without_plaintext(
    auth_fixture,
) -> None:
    now = datetime(2026, 7, 16, 3, 4, 5, tzinfo=UTC)
    service, session_factory = auth_fixture(clock=lambda: now)

    grant = service.register("alice_01", "correct horse battery staple")

    assert grant.username == "alice_01"
    assert grant.expires_at == now + timedelta(hours=24)
    assert grant.expires_at.tzinfo is UTC
    assert grant.user_id == str(UUID(grant.user_id))
    assert grant.user_id == grant.user_id.lower()
    with session_factory() as db:
        user = db.get(UserTable, grant.user_id)
        session = db.scalar(select(UserSessionTable))
        assert user is not None
        assert session is not None
        assert user.password_hash != "correct horse battery staple"
        assert "correct horse battery staple" not in user.password_hash
        assert session.token_hash == hash_token(grant.session_token)
        assert session.csrf_hash == hash_token(grant.csrf_token)
        assert grant.session_token not in session.token_hash
        assert grant.csrf_token not in session.csrf_hash
        assert session.id == str(UUID(session.id))
        assert session.id == session.id.lower()


@pytest.mark.parametrize("username", ["ab", "alice-smith", "a" * 33, "名字_01"])
def test_register_rejects_invalid_username(username: str, auth_fixture) -> None:
    service, _ = auth_fixture()

    with pytest.raises(AuthValidationError, match="invalid username"):
        service.register(username, "valid password")


@pytest.mark.parametrize("password", ["short7", "x" * 129])
def test_register_rejects_password_outside_length_bounds(
    password: str,
    auth_fixture,
) -> None:
    service, _ = auth_fixture()

    with pytest.raises(AuthValidationError, match="invalid password"):
        service.register("alice_01", password)


def test_duplicate_username_raises_stable_business_exception(auth_fixture) -> None:
    service, _ = auth_fixture()
    service.register("alice_01", "correct horse battery staple")

    with pytest.raises(AuthError, match="username already exists") as exc_info:
        service.register("alice_01", "another valid password")
    assert isinstance(exc_info.value, DuplicateUsernameError)


def test_register_rolls_back_user_when_session_integrity_fails(
    auth_fixture,
    monkeypatch,
) -> None:
    service, session_factory = auth_fixture()
    existing = service.register("alice_01", "correct horse battery staple")
    collision = SessionSecrets(
        session_token=existing.session_token,
        session_hash=hash_token(existing.session_token),
        csrf_token=existing.csrf_token,
        csrf_hash=hash_token(existing.csrf_token),
    )
    monkeypatch.setattr(SessionSecrets, "create", classmethod(lambda cls: collision))

    with pytest.raises(InvalidSessionError, match="could not create session"):
        service.register("bob_01", "correct horse battery staple")

    with session_factory() as db:
        assert db.scalar(select(UserTable).where(UserTable.username == "bob_01")) is None
        assert db.scalar(select(UserTable).where(UserTable.username == "alice_01")) is not None


def test_unknown_username_and_wrong_password_are_indistinguishable(auth_fixture) -> None:
    service, _ = auth_fixture()
    service.register("alice_01", "correct horse battery staple")

    failures = []
    for username, password in (
        ("unknown_01", "correct horse battery staple"),
        ("alice_01", "incorrect password"),
    ):
        with pytest.raises(InvalidCredentialsError) as exc_info:
            service.login(username, password)
        failures.append((type(exc_info.value), str(exc_info.value), exc_info.value.args))

    assert failures[0] == failures[1]
    assert failures[0][1] == "invalid credentials"


def test_login_authenticate_rotate_and_logout_session(auth_fixture) -> None:
    now = datetime(2026, 7, 16, 8, 0, tzinfo=UTC)
    service, _ = auth_fixture(clock=lambda: now)
    service.register("alice_01", "correct horse battery staple")

    grant = service.login("alice_01", "correct horse battery staple")
    before = service.authenticate(grant.session_token)
    new_csrf = service.rotate_csrf(grant.session_token)
    after = service.authenticate(grant.session_token)

    assert before.username == "alice_01"
    assert before.expires_at == grant.expires_at
    assert before.expires_at.tzinfo is UTC
    assert after.csrf_hash == hash_token(new_csrf)
    assert after.csrf_hash != before.csrf_hash
    assert after.expires_at == before.expires_at
    assert "session_token" not in asdict(after)
    assert "csrf_token" not in asdict(after)
    assert grant.session_token not in asdict(after).values()
    assert grant.csrf_token not in asdict(after).values()

    service.logout(grant.session_token)
    with pytest.raises(InvalidSessionError, match="invalid session"):
        service.authenticate(grant.session_token)


def test_expired_and_unknown_sessions_are_rejected(auth_fixture) -> None:
    current = [datetime(2026, 7, 16, 8, 0, tzinfo=UTC)]
    service, _ = auth_fixture(clock=lambda: current[0], session_hours=24)
    grant = service.register("alice_01", "correct horse battery staple")

    current[0] = grant.expires_at

    with pytest.raises(InvalidSessionError, match="invalid session"):
        service.authenticate(grant.session_token)
    with pytest.raises(InvalidSessionError, match="invalid session"):
        service.rotate_csrf(grant.session_token)
    with pytest.raises(InvalidSessionError, match="invalid session"):
        service.authenticate("unknown session token")


def test_repository_session_write_boundary_accepts_hashes_only() -> None:
    parameters = signature(SessionRepository.create).parameters

    assert "token_hash" in parameters
    assert "csrf_hash" in parameters
    assert "session_token" not in parameters
    assert "csrf_token" not in parameters
