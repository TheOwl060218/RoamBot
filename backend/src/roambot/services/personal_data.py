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
    PublicShareRecord,
    ShareRepository,
)
from roambot.security.sessions import hash_token, new_token
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


@dataclass(frozen=True)
class ShareLink:
    id: str
    history_id: str
    url: str
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
            histories = HistoryRepository(db)
            if histories.get_owned(
                history_id=history_id,
                user_id=user_id,
            ) is None:
                raise ResourceNotFoundError
            ShareRepository(db).revoke_for_history(history_id, self._now())
            if not histories.delete_owned(history_id=history_id, user_id=user_id):
                raise ResourceNotFoundError

    def clear_history(self, user_id: str) -> None:
        with self._session_factory.begin() as db:
            histories = HistoryRepository(db)
            shares = ShareRepository(db)
            now = self._now()
            for history in histories.list_owned(user_id):
                shares.revoke_for_history(history.id, now)
            histories.clear_owned(user_id)

    def create_share(self, *, user_id: str, history_id: str) -> ShareLink:
        now = self._now()
        with self._session_factory.begin() as db:
            if HistoryRepository(db).get_owned(
                history_id=history_id,
                user_id=user_id,
            ) is None:
                raise ResourceNotFoundError
            token = new_token()
            share = ShareRepository(db).create_replacing_active(
                user_id,
                history_id,
                hash_token(token),
                now,
            )
        return ShareLink(
            id=share.id,
            history_id=share.history_id,
            url=f"/share/{token}",
            created_at=share.created_at,
        )

    def revoke_share(self, *, user_id: str, share_id: str) -> None:
        with self._session_factory.begin() as db:
            if not ShareRepository(db).revoke_owned(
                share_id,
                user_id,
                self._now(),
            ):
                raise ResourceNotFoundError

    def get_public_share(self, token: str) -> dict[str, object]:
        with self._session_factory() as db:
            record = ShareRepository(db).get_public_by_token_hash(hash_token(token))
        if record is None:
            raise ResourceNotFoundError
        return _public_snapshot(record)

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


_DESTINATION_FIELDS = ("name", "address", "city", "scenery_tags")
_WEATHER_FIELDS = (
    "date",
    "condition",
    "temp_min_c",
    "temp_max_c",
    "precipitation_mm",
    "wind_speed_kmh",
    "humidity_percent",
    "visibility_km",
    "uv_index",
)
_SUITABILITY_FIELDS = ("date", "score", "reasons")
_SCORE_FIELDS = (
    "weather",
    "distance",
    "fairness",
    "popularity",
    "coverage_penalty",
    "total",
)


def _public_snapshot(record: PublicShareRecord) -> dict[str, object]:
    history = record.history
    request = _mapping(json.loads(history.request_json))
    result = _mapping(json.loads(history.result_json))
    companions = request["companion_origins"]
    if not isinstance(companions, list):
        raise ValueError("history companion origins must be a list")
    raw_items = result.get("items")
    if raw_items is None:
        raw_items = [result["item"]]
    if not isinstance(raw_items, list):
        raise ValueError("history result items must be a list")
    snapshot: dict[str, object] = {
        "mode": history.mode,
        "city": request["city"],
        "companion_count": len(companions),
        "start_date": request["start_date"],
        "end_date": request["end_date"],
        "items": [_public_item(_mapping(item)) for item in raw_items],
        "generated_at": result["generated_at"],
        "uncovered_scenery_types": result.get("uncovered_scenery_types", []),
    }
    private_strings = {
        str(request["main_origin"]),
        *(str(companion) for companion in companions),
        history.user_id,
        *_origin_labels(raw_items),
    }
    ordered_private_strings = tuple(
        sorted((value for value in private_strings if value), key=len, reverse=True)
    )
    return _remove_private_strings(snapshot, ordered_private_strings)


def _public_item(item: dict[str, object]) -> dict[str, object]:
    weather = item["weather"]
    suitability = item["daily_suitability"]
    if not isinstance(weather, list) or not isinstance(suitability, list):
        raise ValueError("history daily values must be lists")
    destination = _mapping(item["destination"])
    public_destination = _project(destination, _DESTINATION_FIELDS)
    public_destination["rating"] = destination.get("rating")
    public_suitability = [
        _public_suitability(_mapping(day))
        for day in suitability
    ]
    return {
        "destination": public_destination,
        "weather": [
            _project(_mapping(day), _WEATHER_FIELDS)
            for day in weather
        ],
        "daily_suitability": public_suitability,
        "score": _project(_mapping(item["score"]), _SCORE_FIELDS),
        "explanation": item["explanation"],
        "overall_advice": item.get(
            "overall_advice",
            _derive_legacy_overall_advice(public_suitability),
        ),
    }


def _public_suitability(day: dict[str, object]) -> dict[str, object]:
    public = _project(day, _SUITABILITY_FIELDS)
    status = day.get("status") or _derive_legacy_daily_status(day)
    public["status"] = status
    public["summary"] = day.get("summary") or _legacy_daily_summary(status)
    return public


def _derive_legacy_daily_status(day: dict[str, object]) -> str:
    score = day["score"]
    if not isinstance(score, int | float) or isinstance(score, bool):
        raise ValueError("history suitability score must be numeric")
    if score >= 75:
        return "suitable"
    if score >= 50:
        return "caution"
    return "not_recommended"


def _legacy_daily_summary(status: object) -> str:
    summaries = {
        "suitable": "该日期天气条件适合前往",
        "caution": "该日期天气条件一般，建议关注天气变化",
        "not_recommended": "该日期不建议前往，请考虑调整日期",
    }
    if status not in summaries:
        raise ValueError("history suitability status is invalid")
    return summaries[status]


def _derive_legacy_overall_advice(
    suitability: list[dict[str, object]],
) -> str:
    statuses = {day["status"] for day in suitability}
    if "not_recommended" in statuses:
        return "some_dates_not_recommended"
    if "caution" in statuses:
        return "some_dates_caution"
    return "suitable"


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise ValueError("history value must be an object")
    return value


def _project(
    value: dict[str, object],
    fields: tuple[str, ...],
) -> dict[str, object]:
    return {field: value[field] for field in fields}


def _origin_labels(items: list[object]) -> set[str]:
    labels: set[str] = set()
    for item in items:
        distances = _mapping(item).get("distances", [])
        if not isinstance(distances, list):
            continue
        for distance in distances:
            if not isinstance(distance, dict):
                continue
            label = distance.get("origin_label")
            if isinstance(label, str) and label:
                labels.add(label)
    return labels


def _remove_private_strings(value: object, private_strings: tuple[str, ...]) -> object:
    if isinstance(value, str):
        for private in private_strings:
            if private:
                value = value.replace(private, "")
        return value
    if isinstance(value, list):
        return [_remove_private_strings(item, private_strings) for item in value]
    if isinstance(value, dict):
        return {
            key: _remove_private_strings(item, private_strings)
            for key, item in value.items()
        }
    return value
