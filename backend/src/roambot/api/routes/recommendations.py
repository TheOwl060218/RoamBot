from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from roambot.api.dependencies import get_recommendation_service
from roambot.api.errors import ErrorField, error_response
from roambot.domain.models import (
    PlaceEvaluationRequest,
    PlaceEvaluationResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from roambot.providers.protocols import ProviderError
from roambot.services.recommendations import RecommendationService

router = APIRouter(tags=["recommendations"])
RECOMMENDATION_SERVICE_DEPENDENCY = Depends(get_recommendation_service)


@router.post("/recommendations", response_model=RecommendationResponse)
def recommend(
    request: RecommendationRequest,
    service: RecommendationService = RECOMMENDATION_SERVICE_DEPENDENCY,
) -> RecommendationResponse | JSONResponse:
    try:
        return service.recommend(request)
    except ProviderError as exc:
        if exc.code == "not_found":
            return _origin_not_found()
        return _provider_unavailable()


@router.post("/place-evaluations", response_model=PlaceEvaluationResponse)
def evaluate_place(
    request: PlaceEvaluationRequest,
    service: RecommendationService = RECOMMENDATION_SERVICE_DEPENDENCY,
) -> PlaceEvaluationResponse | JSONResponse:
    origin_error = _guard_origin_resolution(request, service)
    if origin_error is not None:
        return origin_error
    try:
        return service.evaluate(request)
    except ProviderError as exc:
        if exc.code == "not_found":
            return _place_not_found()
        return _provider_unavailable()


def _guard_origin_resolution(
    request: RecommendationRequest | PlaceEvaluationRequest,
    service: RecommendationService,
) -> JSONResponse | None:
    try:
        for origin in [request.main_origin, *request.companion_origins]:
            service.geocoder.geocode(origin, request.city)
    except ProviderError as exc:
        if exc.code == "not_found":
            return _origin_not_found()
        return _provider_unavailable()
    return None


def _origin_not_found() -> JSONResponse:
    return error_response(
        status_code=422,
        code="origin_not_found",
        message="Origin could not be resolved.",
        fields=[
            ErrorField(path="main_origin", message="Origin could not be resolved."),
        ],
    )


def _place_not_found() -> JSONResponse:
    return error_response(
        status_code=404,
        code="place_not_found",
        message="Place could not be found.",
        fields=[
            ErrorField(path="target_place", message="Place could not be found."),
        ],
    )


def _provider_unavailable() -> JSONResponse:
    return error_response(
        status_code=503,
        code="provider_unavailable",
        message="Provider is temporarily unavailable.",
    )
