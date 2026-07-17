from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from roambot.domain.models import Destination
from roambot.persistence.tables import (
    FavoriteTable,
    HistoryTable,
    PlaceTable,
    UserSessionTable,
    UserTable,
)


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


@dataclass(frozen=True)
class PlaceRecord:
    id: str
    provider: str
    provider_place_id: str
    name: str
    address: str
    city: str
    longitude: float
    latitude: float
    type_name: str
    type_code: str
    scenery_tags: tuple[str, ...]


@dataclass(frozen=True)
class FavoriteRecord:
    id: str
    user_id: str
    place: PlaceRecord
    created_at: datetime


@dataclass(frozen=True)
class HistoryRecord:
    id: str
    user_id: str
    mode: str
    request_json: str
    result_json: str
    created_at: datetime


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


class PlaceRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def upsert(
        self,
        *,
        provider: str,
        destination: Destination,
        updated_at: datetime,
    ) -> PlaceRecord:
        values = {
            "id": str(uuid4()),
            "provider": provider,
            "provider_place_id": destination.provider_id,
            "name": destination.name,
            "address": destination.address,
            "city": destination.city,
            "longitude": destination.coordinate.longitude,
            "latitude": destination.coordinate.latitude,
            "type_name": destination.type_name,
            "type_code": destination.type_code,
            "scenery_tags_json": json.dumps(
                sorted(tag.value for tag in destination.scenery_tags),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "updated_at": _utc_for_write(updated_at),
        }
        statement = sqlite_insert(PlaceTable).values(**values)
        self._db.execute(
            statement.on_conflict_do_update(
                index_elements=[PlaceTable.provider, PlaceTable.provider_place_id],
                set_={
                    key: value
                    for key, value in values.items()
                    if key not in {"id", "provider", "provider_place_id"}
                },
            )
        )
        row = self._db.scalar(
            select(PlaceTable).where(
                PlaceTable.provider == provider,
                PlaceTable.provider_place_id == destination.provider_id,
            )
        )
        if row is None:
            raise RuntimeError("place upsert did not return a row")
        return _place_record(row)


class FavoriteRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create_or_get(
        self,
        *,
        user_id: str,
        place_id: str,
        created_at: datetime,
    ) -> tuple[FavoriteRecord, bool]:
        favorite_id = str(uuid4())
        result = self._db.execute(
            sqlite_insert(FavoriteTable)
            .values(
                id=favorite_id,
                user_id=user_id,
                place_id=place_id,
                created_at=_utc_for_write(created_at),
            )
            .on_conflict_do_nothing(
                index_elements=[FavoriteTable.user_id, FavoriteTable.place_id]
            )
        )
        created = result.rowcount == 1
        row = self._owned_row(
            user_id=user_id,
            favorite_id=favorite_id if created else None,
            place_id=None if created else place_id,
        )
        if row is None:
            raise RuntimeError("favorite insert did not return a row")
        return _favorite_record(*row), created

    def list_owned(self, user_id: str) -> list[FavoriteRecord]:
        rows = self._db.execute(
            select(FavoriteTable, PlaceTable)
            .join(PlaceTable, FavoriteTable.place_id == PlaceTable.id)
            .where(FavoriteTable.user_id == user_id)
            .order_by(FavoriteTable.created_at.desc(), FavoriteTable.id.desc())
        ).all()
        return [_favorite_record(favorite, place) for favorite, place in rows]

    def delete_owned(self, *, favorite_id: str, user_id: str) -> bool:
        result = self._db.execute(
            delete(FavoriteTable).where(
                FavoriteTable.id == favorite_id,
                FavoriteTable.user_id == user_id,
            )
        )
        return result.rowcount == 1

    def _owned_row(
        self,
        *,
        user_id: str,
        favorite_id: str | None,
        place_id: str | None,
    ) -> tuple[FavoriteTable, PlaceTable] | None:
        if (favorite_id is None) == (place_id is None):
            raise ValueError("exactly one favorite lookup key is required")
        statement = (
            select(FavoriteTable, PlaceTable)
            .join(PlaceTable, FavoriteTable.place_id == PlaceTable.id)
            .where(FavoriteTable.user_id == user_id)
        )
        if favorite_id is not None:
            statement = statement.where(FavoriteTable.id == favorite_id)
        else:
            statement = statement.where(FavoriteTable.place_id == place_id)
        row = self._db.execute(statement).one_or_none()
        return (row[0], row[1]) if row is not None else None


class HistoryRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(
        self,
        *,
        user_id: str,
        mode: str,
        request_json: str,
        result_json: str,
        created_at: datetime,
    ) -> HistoryRecord:
        row = HistoryTable(
            id=str(uuid4()),
            user_id=user_id,
            mode=mode,
            request_json=request_json,
            result_json=result_json,
            created_at=_utc_for_write(created_at),
        )
        self._db.add(row)
        self._db.flush()
        return _history_record(row)

    def list_owned(self, user_id: str) -> list[HistoryRecord]:
        rows = self._db.scalars(
            select(HistoryTable)
            .where(HistoryTable.user_id == user_id)
            .order_by(HistoryTable.created_at.desc(), HistoryTable.id.desc())
        ).all()
        return [_history_record(row) for row in rows]

    def get_owned(self, *, history_id: str, user_id: str) -> HistoryRecord | None:
        row = self._db.scalar(
            select(HistoryTable).where(
                HistoryTable.id == history_id,
                HistoryTable.user_id == user_id,
            )
        )
        return _history_record(row) if row is not None else None

    def delete_owned(self, *, history_id: str, user_id: str) -> bool:
        result = self._db.execute(
            delete(HistoryTable).where(
                HistoryTable.id == history_id,
                HistoryTable.user_id == user_id,
            )
        )
        return result.rowcount == 1

    def clear_owned(self, user_id: str) -> int:
        result = self._db.execute(
            delete(HistoryTable).where(HistoryTable.user_id == user_id)
        )
        return result.rowcount


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


def _place_record(row: PlaceTable) -> PlaceRecord:
    return PlaceRecord(
        id=row.id,
        provider=row.provider,
        provider_place_id=row.provider_place_id,
        name=row.name,
        address=row.address,
        city=row.city,
        longitude=row.longitude,
        latitude=row.latitude,
        type_name=row.type_name,
        type_code=row.type_code,
        scenery_tags=tuple(json.loads(row.scenery_tags_json)),
    )


def _favorite_record(row: FavoriteTable, place: PlaceTable) -> FavoriteRecord:
    return FavoriteRecord(
        id=row.id,
        user_id=row.user_id,
        place=_place_record(place),
        created_at=_utc_from_database(row.created_at),
    )


def _history_record(row: HistoryTable) -> HistoryRecord:
    return HistoryRecord(
        id=row.id,
        user_id=row.user_id,
        mode=row.mode,
        request_json=row.request_json,
        result_json=row.result_json,
        created_at=_utc_from_database(row.created_at),
    )
