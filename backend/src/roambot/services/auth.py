from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError

from roambot.persistence.database import SessionFactory
from roambot.persistence.repositories import (
    AuthError,
    DuplicateUsernameError,
    SessionRepository,
    UserRepository,
)
from roambot.security.passwords import hash_password, verify_password
from roambot.security.sessions import SessionSecrets, hash_token, new_token

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,32}$")


class AuthValidationError(AuthError):
    pass


class InvalidCredentialsError(AuthError):
    pass


class InvalidSessionError(AuthError):
    pass


@dataclass(frozen=True)
class SessionGrant:
    user_id: str
    username: str
    session_token: str
    csrf_token: str
    expires_at: datetime


@dataclass(frozen=True)
class AuthenticatedSession:
    session_id: str
    user_id: str
    username: str
    csrf_hash: str
    expires_at: datetime


class AuthService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        session_hours: int = 24,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._session_hours = session_hours
        self._clock = clock or (lambda: datetime.now(UTC))

    def register(self, username: str, password: str) -> SessionGrant:
        _validate_registration(username, password)
        now = self._now()
        expires_at = now + timedelta(hours=self._session_hours)
        password_digest = hash_password(password)
        secrets = SessionSecrets.create()

        try:
            with self._session_factory.begin() as db:
                user = UserRepository(db).create(
                    username=username,
                    password_hash=password_digest,
                    created_at=now,
                )
                SessionRepository(db).create(
                    user_id=user.id,
                    token_hash=secrets.session_hash,
                    csrf_hash=secrets.csrf_hash,
                    expires_at=expires_at,
                )
        except DuplicateUsernameError:
            raise
        except IntegrityError as exc:
            raise InvalidSessionError("could not create session") from exc

        return SessionGrant(
            user_id=user.id,
            username=user.username,
            session_token=secrets.session_token,
            csrf_token=secrets.csrf_token,
            expires_at=expires_at,
        )

    def login(self, username: str, password: str) -> SessionGrant:
        if not USERNAME_PATTERN.fullmatch(username) or not 8 <= len(password) <= 128:
            raise InvalidCredentialsError("invalid credentials")

        with self._session_factory() as db:
            user = UserRepository(db).get_by_username(username)
        if user is None or not verify_password(user.password_hash, password):
            raise InvalidCredentialsError("invalid credentials")

        now = self._now()
        expires_at = now + timedelta(hours=self._session_hours)
        secrets = SessionSecrets.create()
        try:
            with self._session_factory.begin() as db:
                SessionRepository(db).create(
                    user_id=user.id,
                    token_hash=secrets.session_hash,
                    csrf_hash=secrets.csrf_hash,
                    expires_at=expires_at,
                )
        except IntegrityError as exc:
            raise InvalidSessionError("could not create session") from exc

        return SessionGrant(
            user_id=user.id,
            username=user.username,
            session_token=secrets.session_token,
            csrf_token=secrets.csrf_token,
            expires_at=expires_at,
        )

    def authenticate(self, session_token: str) -> AuthenticatedSession:
        now = self._now()
        token_hash = hash_token(session_token)
        with self._session_factory() as db:
            session = SessionRepository(db).get_active_by_hash(token_hash, now)
            if session is None:
                raise InvalidSessionError("invalid session")
            user = UserRepository(db).get_by_id(session.user_id)
            if user is None:
                raise InvalidSessionError("invalid session")

        return AuthenticatedSession(
            session_id=session.id,
            user_id=user.id,
            username=user.username,
            csrf_hash=session.csrf_hash,
            expires_at=session.expires_at,
        )

    def rotate_csrf(self, session_token: str) -> str:
        csrf_token = new_token()
        with self._session_factory.begin() as db:
            session = SessionRepository(db).replace_csrf_hash(
                token_hash=hash_token(session_token),
                csrf_hash=hash_token(csrf_token),
                now=self._now(),
            )
            if session is None:
                raise InvalidSessionError("invalid session")
        return csrf_token

    def logout(self, session_token: str) -> None:
        with self._session_factory.begin() as db:
            revoked = SessionRepository(db).revoke_by_hash(
                token_hash=hash_token(session_token),
                revoked_at=self._now(),
            )
            if not revoked:
                raise InvalidSessionError("invalid session")

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return value.astimezone(UTC)


def _validate_registration(username: str, password: str) -> None:
    if not USERNAME_PATTERN.fullmatch(username):
        raise AuthValidationError("invalid username")
    if not 8 <= len(password) <= 128:
        raise AuthValidationError("invalid password")
