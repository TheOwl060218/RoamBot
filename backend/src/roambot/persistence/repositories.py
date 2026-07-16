from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from roambot.persistence.tables import UserSessionTable, UserTable


class AuthError(Exception):
    pass


class DuplicateUsernameError(AuthError):
    pass


@dataclass(frozen=True)
class UserRecord:
    id: str
    username: str
    password_hash: str
    created_at: datetime


@dataclass(frozen=True)
class SessionRecord:
    id: str
    user_id: str
    csrf_hash: str
    expires_at: datetime
    revoked_at: datetime | None


class UserRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(
        self,
        *,
        username: str,
        password_hash: str,
        created_at: datetime,
    ) -> UserRecord:
        row = UserTable(
            id=str(uuid4()),
            username=username,
            password_hash=password_hash,
            created_at=_utc_for_write(created_at),
        )
        self._db.add(row)
        try:
            self._db.flush()
        except IntegrityError as exc:
            self._db.rollback()
            raise DuplicateUsernameError("username already exists") from exc
        return _user_record(row)

    def get_by_username(self, username: str) -> UserRecord | None:
        row = self._db.scalar(select(UserTable).where(UserTable.username == username))
        return _user_record(row) if row is not None else None

    def get_by_id(self, user_id: str) -> UserRecord | None:
        row = self._db.get(UserTable, user_id)
        return _user_record(row) if row is not None else None


class SessionRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(
        self,
        *,
        user_id: str,
        token_hash: str,
        csrf_hash: str,
        expires_at: datetime,
    ) -> SessionRecord:
        row = UserSessionTable(
            id=str(uuid4()),
            user_id=user_id,
            token_hash=token_hash,
            csrf_hash=csrf_hash,
            expires_at=_utc_for_write(expires_at),
            revoked_at=None,
        )
        self._db.add(row)
        self._db.flush()
        return _session_record(row)

    def get_active_by_hash(self, token_hash: str, now: datetime) -> SessionRecord | None:
        row = self._db.scalar(
            select(UserSessionTable).where(
                UserSessionTable.token_hash == token_hash,
                UserSessionTable.revoked_at.is_(None),
                UserSessionTable.expires_at > _utc_for_write(now),
            )
        )
        return _session_record(row) if row is not None else None

    def replace_csrf_hash(
        self,
        *,
        token_hash: str,
        csrf_hash: str,
        now: datetime,
    ) -> SessionRecord | None:
        row = self._db.execute(
            update(UserSessionTable)
            .where(
                UserSessionTable.token_hash == token_hash,
                UserSessionTable.revoked_at.is_(None),
                UserSessionTable.expires_at > _utc_for_write(now),
            )
            .values(csrf_hash=csrf_hash)
            .returning(UserSessionTable)
        ).scalar_one_or_none()
        return _session_record(row) if row is not None else None

    def revoke_by_hash(self, *, token_hash: str, revoked_at: datetime) -> bool:
        now = _utc_for_write(revoked_at)
        result = self._db.execute(
            update(UserSessionTable)
            .where(
                UserSessionTable.token_hash == token_hash,
                UserSessionTable.revoked_at.is_(None),
                UserSessionTable.expires_at > now,
            )
            .values(revoked_at=now)
        )
        return result.rowcount == 1


def _utc_for_write(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def _utc_from_database(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _user_record(row: UserTable) -> UserRecord:
    return UserRecord(
        id=row.id,
        username=row.username,
        password_hash=row.password_hash,
        created_at=_utc_from_database(row.created_at),
    )


def _session_record(row: UserSessionTable) -> SessionRecord:
    return SessionRecord(
        id=row.id,
        user_id=row.user_id,
        csrf_hash=row.csrf_hash,
        expires_at=_utc_from_database(row.expires_at),
        revoked_at=(
            _utc_from_database(row.revoked_at) if row.revoked_at is not None else None
        ),
    )
