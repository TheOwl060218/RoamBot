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
from roambot.services.recommendations import (
    OriginNotFoundError,
    PlaceNotFoundError,
    RecommendationService,
)

router = APIRouter(tags=["recommendations"])
RECOMMENDATION_SERVICE_DEPENDENCY = Depends(get_recommendation_service)


@router.post("/recommendations", response_model=RecommendationResponse)
def recommend(
    request: RecommendationRequest,
    service: RecommendationService = RECOMMENDATION_SERVICE_DEPENDENCY,
) -> RecommendationResponse | JSONResponse:
    try:
        return service.recommend(request)
    except OriginNotFoundError as exc:
        return _origin_not_found(exc.field_path)
    except ProviderError:
        return _provider_unavailable()


@router.post("/place-evaluations", response_model=PlaceEvaluationResponse)
def evaluate_place(
    request: PlaceEvaluationRequest,
    service: RecommendationService = RECOMMENDATION_SERVICE_DEPENDENCY,
) -> PlaceEvaluationResponse | JSONResponse:
    try:
        return service.evaluate(request)
    except OriginNotFoundError as exc:
        return _origin_not_found(exc.field_path)
    except PlaceNotFoundError:
        return _place_not_found()
    except ProviderError:
        return _provider_unavailable()


def _origin_not_found(field_path: str) -> JSONResponse:
    return error_response(
        status_code=422,
        code="origin_not_found",
        message="Origin could not be resolved.",
        fields=[
            ErrorField(path=field_path, message="Origin could not be resolved."),
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
