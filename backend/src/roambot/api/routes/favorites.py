from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field

from roambot.api.dependencies import (
    RequestSession,
    get_personal_data_service,
    require_csrf,
    require_session,
)
from roambot.api.errors import error_response
from roambot.domain.models import Coordinate, Destination
from roambot.persistence.repositories import FavoriteRecord
from roambot.services.personal_data import PersonalDataService, ResourceNotFoundError

router = APIRouter(prefix="/favorites", tags=["favorites"])
ProviderName = Annotated[str, Field(min_length=1, max_length=32, pattern=r"^[a-z0-9_]+$")]


class FavoriteCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: ProviderName
    destination: Destination


class FavoritePlaceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    provider_place_id: str
    name: str
    address: str
    city: str
    coordinate: Coordinate
    type_name: str
    type_code: str
    scenery_tags: list[str]


class FavoriteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    place: FavoritePlaceResponse
    created_at: str


class FavoriteEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    favorite: FavoriteResponse


class FavoriteListEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    favorites: list[FavoriteResponse]


PERSONAL_DATA_DEPENDENCY = Depends(get_personal_data_service)
SESSION_DEPENDENCY = Depends(require_session)
CSRF_DEPENDENCY = Depends(require_csrf)


@router.get("", response_model=FavoriteListEnvelope)
def list_favorites(
    session: RequestSession = SESSION_DEPENDENCY,
    service: PersonalDataService = PERSONAL_DATA_DEPENDENCY,
) -> FavoriteListEnvelope:
    return FavoriteListEnvelope(
        favorites=[
            _favorite_response(record)
            for record in service.list_favorites(session.authenticated.user_id)
        ]
    )


@router.post("", response_model=FavoriteEnvelope)
def add_favorite(
    request: FavoriteCreateRequest,
    response: Response,
    session: RequestSession = CSRF_DEPENDENCY,
    service: PersonalDataService = PERSONAL_DATA_DEPENDENCY,
) -> FavoriteEnvelope:
    favorite, created = service.add_favorite(
        user_id=session.authenticated.user_id,
        provider=request.provider,
        destination=request.destination,
    )
    response.status_code = 201 if created else 200
    return FavoriteEnvelope(favorite=_favorite_response(favorite))


@router.delete("/{favorite_id}", status_code=204)
def delete_favorite(
    favorite_id: str,
    session: RequestSession = CSRF_DEPENDENCY,
    service: PersonalDataService = PERSONAL_DATA_DEPENDENCY,
) -> Response:
    try:
        service.delete_favorite(
            user_id=session.authenticated.user_id,
            favorite_id=favorite_id,
        )
    except ResourceNotFoundError:
        return error_response(
            status_code=404,
            code="resource_not_found",
            message="Resource was not found.",
        )
    return Response(status_code=204)


def _favorite_response(record: FavoriteRecord) -> FavoriteResponse:
    place = record.place
    return FavoriteResponse(
        id=record.id,
        place=FavoritePlaceResponse(
            provider=place.provider,
            provider_place_id=place.provider_place_id,
            name=place.name,
            address=place.address,
            city=place.city,
            coordinate=Coordinate(longitude=place.longitude, latitude=place.latitude),
            type_name=place.type_name,
            type_code=place.type_code,
            scenery_tags=list(place.scenery_tags),
        ),
        created_at=record.created_at.isoformat(),
    )
