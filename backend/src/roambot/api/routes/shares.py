from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict

from roambot.api.dependencies import (
    RequestSession,
    get_personal_data_service,
    require_csrf,
)
from roambot.api.errors import error_response
from roambot.domain.models import DailySuitability, DailyWeather, ScoreBreakdown
from roambot.services.personal_data import PersonalDataService, ResourceNotFoundError

router = APIRouter(tags=["shares"])


class ShareResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    history_id: str
    url: str
    created_at: str


class ShareEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    share: ShareResponse


class PublicDestinationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    address: str
    city: str
    scenery_tags: list[str]


class PublicItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: PublicDestinationResponse
    weather: list[DailyWeather]
    daily_suitability: list[DailySuitability]
    score: ScoreBreakdown
    explanation: str


class PublicSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["recommendation", "place_evaluation"]
    city: str
    companion_count: int
    start_date: str
    end_date: str
    items: list[PublicItemResponse]
    generated_at: str


class PublicShareEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: PublicSnapshotResponse


PERSONAL_DATA_DEPENDENCY = Depends(get_personal_data_service)
CSRF_DEPENDENCY = Depends(require_csrf)


@router.post(
    "/history/{history_id}/share",
    response_model=ShareEnvelope,
    status_code=201,
)
def create_share(
    history_id: str,
    session: RequestSession = CSRF_DEPENDENCY,
    service: PersonalDataService = PERSONAL_DATA_DEPENDENCY,
) -> ShareEnvelope | Response:
    try:
        share = service.create_share(
            user_id=session.authenticated.user_id,
            history_id=history_id,
        )
    except ResourceNotFoundError:
        return _resource_not_found()
    return ShareEnvelope(
        share=ShareResponse(
            id=share.id,
            history_id=share.history_id,
            url=share.url,
            created_at=share.created_at.isoformat(),
        )
    )


@router.delete("/shares/{share_id}", status_code=204)
def revoke_share(
    share_id: str,
    session: RequestSession = CSRF_DEPENDENCY,
    service: PersonalDataService = PERSONAL_DATA_DEPENDENCY,
) -> Response:
    try:
        service.revoke_share(
            user_id=session.authenticated.user_id,
            share_id=share_id,
        )
    except ResourceNotFoundError:
        return _resource_not_found()
    return Response(status_code=204)


@router.get("/public/shares/{token}", response_model=PublicShareEnvelope)
def get_public_share(
    token: str,
    service: PersonalDataService = PERSONAL_DATA_DEPENDENCY,
) -> PublicShareEnvelope | Response:
    try:
        snapshot = service.get_public_share(token)
    except ResourceNotFoundError:
        return _share_unavailable()
    return PublicShareEnvelope.model_validate({"snapshot": snapshot})


def _resource_not_found() -> Response:
    return error_response(
        status_code=404,
        code="resource_not_found",
        message="Resource was not found.",
    )


def _share_unavailable() -> Response:
    return error_response(
        status_code=404,
        code="share_unavailable",
        message="Share is unavailable.",
    )
