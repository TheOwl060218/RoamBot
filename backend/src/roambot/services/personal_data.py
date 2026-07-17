from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

from roambot.domain.models import (
    Destination,
    PlaceEvaluationRequest,
    RecommendationRequest,
)
from roambot.persistence.database import SessionFactory
from roambot.persistence.repositories import (
    FavoriteRecord,
    FavoriteRepository,
    HistoryRecord,
    HistoryRepository,
    PlaceRepository,
)
from roambot.services.recommendations import RecommendationService


class ResourceNotFoundError(RuntimeError):
    pass


HistoryMode = Literal["recommendation", "place_evaluation"]


@dataclass(frozen=True)
class HistorySnapshot:
    id: str
    mode: HistoryMode
    request: dict[str, object]
    result: dict[str, object]
    created_at: datetime


class PersonalDataService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def add_favorite(
        self,
        *,
        user_id: str,
        provider: str,
        destination: Destination,
    ) -> tuple[FavoriteRecord, bool]:
        now = self._now()
        with self._session_factory.begin() as db:
            place = PlaceRepository(db).upsert(
                provider=provider,
                destination=destination,
                updated_at=now,
            )
            return FavoriteRepository(db).create_or_get(
                user_id=user_id,
                place_id=place.id,
                created_at=now,
            )

    def list_favorites(self, user_id: str) -> list[FavoriteRecord]:
        with self._session_factory() as db:
            return FavoriteRepository(db).list_owned(user_id)

    def delete_favorite(self, *, user_id: str, favorite_id: str) -> None:
        with self._session_factory.begin() as db:
            if not FavoriteRepository(db).delete_owned(
                favorite_id=favorite_id,
                user_id=user_id,
            ):
                raise ResourceNotFoundError

    def capture_history(
        self,
        *,
        user_id: str,
        mode: HistoryMode,
        request: BaseModel,
        result: BaseModel,
    ) -> HistorySnapshot:
        request_json = _canonical_json(
            request.model_dump(mode="json", exclude_computed_fields=True)
        )
        result_json = _canonical_json(result.model_dump(mode="json"))
        with self._session_factory.begin() as db:
            record = HistoryRepository(db).create(
                user_id=user_id,
                mode=mode,
                request_json=request_json,
                result_json=result_json,
                created_at=self._now(),
            )
        return _snapshot(record)

    def list_histories(self, user_id: str) -> list[HistorySnapshot]:
        with self._session_factory() as db:
            records = HistoryRepository(db).list_owned(user_id)
        return [_snapshot(record) for record in records]

    def get_history(self, *, user_id: str, history_id: str) -> HistorySnapshot:
        with self._session_factory() as db:
            record = HistoryRepository(db).get_owned(
                history_id=history_id,
                user_id=user_id,
            )
        if record is None:
            raise ResourceNotFoundError
        return _snapshot(record)

    def rerun_history(
        self,
        *,
        user_id: str,
        history_id: str,
        recommendation_service: RecommendationService,
    ) -> HistorySnapshot:
        old = self.get_history(user_id=user_id, history_id=history_id)
        if old.mode == "recommendation":
            request = RecommendationRequest.model_validate(old.request)
            result = recommendation_service.recommend(request)
        else:
            request = PlaceEvaluationRequest.model_validate(old.request)
            result = recommendation_service.evaluate(request)
        return self.capture_history(
            user_id=user_id,
            mode=old.mode,
            request=request,
            result=result,
        )

    def delete_history(self, *, user_id: str, history_id: str) -> None:
        with self._session_factory.begin() as db:
            if not HistoryRepository(db).delete_owned(
                history_id=history_id,
                user_id=user_id,
            ):
                raise ResourceNotFoundError

    def clear_history(self, user_id: str) -> None:
        with self._session_factory.begin() as db:
            HistoryRepository(db).clear_owned(user_id)

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return now.astimezone(UTC)


def _canonical_json(value: dict[str, object]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _snapshot(record: HistoryRecord) -> HistorySnapshot:
    if record.mode not in {"recommendation", "place_evaluation"}:
        raise ValueError("unsupported history mode")
    return HistorySnapshot(
        id=record.id,
        mode=record.mode,
        request=json.loads(record.request_json),
        result=json.loads(record.result_json),
        created_at=record.created_at,
    )
