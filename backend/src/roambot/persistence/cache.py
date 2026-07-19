from __future__ import annotations

from datetime import datetime

from roambot.persistence.database import SessionFactory
from roambot.persistence.repositories import CacheEntry, CacheRepository


class SessionCacheStore:
    """Give provider caches a committed transaction per short database operation."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def get_fresh(self, cache_key: str, now: datetime) -> CacheEntry | None:
        with self._session_factory() as db:
            return CacheRepository(db).get_fresh(cache_key, now)

    def put(
        self,
        cache_key: str,
        provider: str,
        operation: str,
        payload_json: dict[str, object],
        created_at: datetime,
        expires_at: datetime,
    ) -> None:
        with self._session_factory.begin() as db:
            CacheRepository(db).put(
                cache_key,
                provider,
                operation,
                payload_json,
                created_at,
                expires_at,
            )

    def delete(self, cache_key: str) -> None:
        with self._session_factory.begin() as db:
            CacheRepository(db).delete(cache_key)
