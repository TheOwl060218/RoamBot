from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict

from roambot.api.dependencies import (
    RequestSession,
    get_personal_data_service,
    get_recommendation_service,
    require_csrf,
    require_session,
)
from roambot.api.errors import error_response
from roambot.api.routes.recommendations import (
    _origin_not_found,
    _place_not_found,
    _provider_unavailable,
)
from roambot.providers.protocols import ProviderError
from roambot.services.personal_data import (
    HistorySnapshot,
    PersonalDataService,
    ResourceNotFoundError,
)
from roambot.services.recommendations import (
    OriginNotFoundError,
    PlaceNotFoundError,
    RecommendationService,
)

router = APIRouter(prefix="/history", tags=["history"])


class HistorySummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    mode: str
    city: str
    start_date: str
    end_date: str
    item_count: int
    generated_at: str
    created_at: str


class HistoryListEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    histories: list[HistorySummaryResponse]


class HistoryDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    mode: str
    request: dict[str, Any]
    result: dict[str, Any]
    created_at: str
    snapshot: bool = True


class HistoryEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    history: HistoryDetailResponse


PERSONAL_DATA_DEPENDENCY = Depends(get_personal_data_service)
RECOMMENDATION_SERVICE_DEPENDENCY = Depends(get_recommendation_service)
SESSION_DEPENDENCY = Depends(require_session)
CSRF_DEPENDENCY = Depends(require_csrf)


@router.get("", response_model=HistoryListEnvelope)
def list_history(
    session: RequestSession = SESSION_DEPENDENCY,
    service: PersonalDataService = PERSONAL_DATA_DEPENDENCY,
) -> HistoryListEnvelope:
    return HistoryListEnvelope(
        histories=[
            _summary(snapshot)
            for snapshot in service.list_histories(session.authenticated.user_id)
        ]
    )


@router.delete("", status_code=204)
def clear_history(
    session: RequestSession = CSRF_DEPENDENCY,
    service: PersonalDataService = PERSONAL_DATA_DEPENDENCY,
) -> Response:
    service.clear_history(session.authenticated.user_id)
    return Response(status_code=204)


@router.get("/{history_id}", response_model=HistoryEnvelope)
def get_history(
    history_id: str,
    session: RequestSession = SESSION_DEPENDENCY,
    service: PersonalDataService = PERSONAL_DATA_DEPENDENCY,
) -> HistoryEnvelope | Response:
    try:
        snapshot = service.get_history(
            user_id=session.authenticated.user_id,
            history_id=history_id,
        )
    except ResourceNotFoundError:
        return _resource_not_found()
    return HistoryEnvelope(history=_detail(snapshot))


@router.post("/{history_id}/rerun", response_model=HistoryEnvelope)
def rerun_history(
    history_id: str,
    session: RequestSession = CSRF_DEPENDENCY,
    service: PersonalDataService = PERSONAL_DATA_DEPENDENCY,
    recommendation_service: RecommendationService = RECOMMENDATION_SERVICE_DEPENDENCY,
) -> HistoryEnvelope | Response:
    try:
        snapshot = service.rerun_history(
            user_id=session.authenticated.user_id,
            history_id=history_id,
            recommendation_service=recommendation_service,
        )
    except ResourceNotFoundError:
        return _resource_not_found()
    except OriginNotFoundError as exc:
        return _origin_not_found(exc.field_path)
    except PlaceNotFoundError:
        return _place_not_found()
    except ProviderError:
        return _provider_unavailable()
    return HistoryEnvelope(history=_detail(snapshot))


@router.delete("/{history_id}", status_code=204)
def delete_history(
    history_id: str,
    session: RequestSession = CSRF_DEPENDENCY,
    service: PersonalDataService = PERSONAL_DATA_DEPENDENCY,
) -> Response:
    try:
        service.delete_history(
            user_id=session.authenticated.user_id,
            history_id=history_id,
        )
    except ResourceNotFoundError:
        return _resource_not_found()
    return Response(status_code=204)


def _summary(snapshot: HistorySnapshot) -> HistorySummaryResponse:
    result_items = snapshot.result.get("items")
    item_count = len(result_items) if isinstance(result_items, list) else 1
    return HistorySummaryResponse(
        id=snapshot.id,
        mode=snapshot.mode,
        city=str(snapshot.request["city"]),
        start_date=str(snapshot.request["start_date"]),
        end_date=str(snapshot.request["end_date"]),
        item_count=item_count,
        generated_at=str(snapshot.result["generated_at"]),
        created_at=snapshot.created_at.isoformat(),
    )


def _detail(snapshot: HistorySnapshot) -> HistoryDetailResponse:
    return HistoryDetailResponse(
        id=snapshot.id,
        mode=snapshot.mode,
        request=snapshot.request,
        result=snapshot.result,
        created_at=snapshot.created_at.isoformat(),
    )


def _resource_not_found() -> Response:
    return error_response(
        status_code=404,
        code="resource_not_found",
        message="Resource was not found.",
    )
