from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from typing import cast

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from roambot.persistence.repositories import CacheEntry, CacheRepository
from roambot.persistence.tables import ApiCacheTable

FIRST_KEY = "a" * 64
SECOND_KEY = "b" * 64
NOW = datetime(2026, 7, 17, 8, 0, tzinfo=UTC)


def canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def session_factory(auth_fixture):
    _, factory = auth_fixture(clock=lambda: NOW)
    return factory


def test_get_fresh_uses_strict_expiry_boundary_and_keeps_expired_row(
    auth_fixture,
) -> None:
    factory = session_factory(auth_fixture)
    payload = {
        "schema_version": 1,
        "model": "Origin",
        "value": {"city": "苏州", "labels": ["主出发地", "同行"]},
    }
    expires_at = NOW + timedelta(hours=1)
    with factory.begin() as db:
        CacheRepository(db).put(
            FIRST_KEY,
            "amap",
            "geocode",
            payload,
            NOW,
            expires_at,
        )

    with factory() as db:
        repository = CacheRepository(db)
        entry = repository.get_fresh(FIRST_KEY, expires_at - timedelta(microseconds=1))
        assert entry == CacheEntry(
            cache_key=FIRST_KEY,
            provider="amap",
            operation="geocode",
            payload_json=canonical_json(payload),
            created_at=NOW,
            expires_at=expires_at,
        )
        assert repository.get_fresh(FIRST_KEY, expires_at) is None
        assert repository.get_fresh(FIRST_KEY, expires_at + timedelta(seconds=1)) is None
        assert db.scalar(select(func.count()).select_from(ApiCacheTable)) == 1


def test_put_atomically_replaces_every_value_and_delete_is_key_isolated(
    auth_fixture,
) -> None:
    factory = session_factory(auth_fixture)
    old_payload = {"schema_version": 1, "model": "Origin", "value": {"old": True}}
    other_payload = {
        "schema_version": 1,
        "model": "DestinationList",
        "value": [],
    }
    new_created_at = NOW + timedelta(minutes=10)
    new_expires_at = NOW + timedelta(days=2)
    new_payload = {
        "schema_version": 1,
        "model": "DailyWeatherList",
        "value": [{"condition": "晴", "date": "2026-07-18"}],
    }

    with factory.begin() as db:
        repository = CacheRepository(db)
        repository.put(
            FIRST_KEY,
            "amap",
            "geocode",
            old_payload,
            NOW,
            NOW + timedelta(days=30),
        )
        repository.put(
            SECOND_KEY,
            "amap",
            "poi_search",
            other_payload,
            NOW,
            NOW + timedelta(days=7),
        )
        repository.put(
            FIRST_KEY,
            "qweather",
            "weather",
            new_payload,
            new_created_at,
            new_expires_at,
        )

    with factory.begin() as db:
        repository = CacheRepository(db)
        assert repository.get_fresh(FIRST_KEY, new_created_at) == CacheEntry(
            cache_key=FIRST_KEY,
            provider="qweather",
            operation="weather",
            payload_json=canonical_json(new_payload),
            created_at=new_created_at,
            expires_at=new_expires_at,
        )
        assert db.scalar(
            select(func.count()).select_from(ApiCacheTable).where(
                ApiCacheTable.cache_key == FIRST_KEY
            )
        ) == 1
        repository.delete(FIRST_KEY)
        assert repository.get_fresh(FIRST_KEY, new_created_at) is None
        assert repository.get_fresh(SECOND_KEY, new_created_at) is not None


def test_delete_expired_returns_count_and_does_not_delete_fresh_entries(
    auth_fixture,
) -> None:
    factory = session_factory(auth_fixture)
    payload = {"schema_version": 1, "model": "Origin", "value": {}}
    entries = (
        ("1" * 64, NOW - timedelta(seconds=1)),
        ("2" * 64, NOW),
        ("3" * 64, NOW + timedelta(microseconds=1)),
    )
    with factory.begin() as db:
        repository = CacheRepository(db)
        for cache_key, expires_at in entries:
            repository.put(
                cache_key,
                "amap",
                "geocode",
                payload,
                NOW - timedelta(days=1),
                expires_at,
            )
        assert repository.delete_expired(NOW) == 2

    with factory() as db:
        rows = db.scalars(select(ApiCacheTable)).all()
        assert [row.cache_key for row in rows] == ["3" * 64]
        assert CacheRepository(db).get_fresh("3" * 64, NOW) is not None


def test_cache_datetime_validation_rejects_naive_and_non_utc_before_sql() -> None:
    class SqlMustNotRun:
        def execute(self, *args, **kwargs):
            del args, kwargs
            raise AssertionError("datetime validation must happen before SQL")

    repository = CacheRepository(cast(Session, SqlMustNotRun()))
    naive = NOW.replace(tzinfo=None)
    non_utc = NOW.astimezone(timezone(timedelta(hours=8)))
    payload = {"schema_version": 1, "model": "Origin", "value": {}}

    for invalid in (naive, non_utc):
        with pytest.raises(ValueError, match="aware UTC"):
            repository.get_fresh(FIRST_KEY, invalid)
        with pytest.raises(ValueError, match="aware UTC"):
            repository.delete_expired(invalid)
        with pytest.raises(ValueError, match="aware UTC"):
            repository.put(
                FIRST_KEY,
                "amap",
                "geocode",
                payload,
                invalid,
                NOW,
            )
        with pytest.raises(ValueError, match="aware UTC"):
            repository.put(
                FIRST_KEY,
                "amap",
                "geocode",
                payload,
                NOW,
                invalid,
            )
