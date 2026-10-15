from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from roambot.api.dependencies import (
    RequestSession,
    get_assistant_context_signer,
    get_personal_data_service,
    get_recommendation_service,
    require_optional_csrf,
)
from roambot.api.errors import ErrorField, error_response
from roambot.domain.models import (
    PlaceEvaluationRequest,
    PlaceEvaluationResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from roambot.providers.protocols import ProviderError
from roambot.security.assistant_context import AssistantContextSigner
from roambot.services.personal_data import PersonalDataService
from roambot.services.recommendations import (
    OriginNotFoundError,
    PlaceNotFoundError,
    RecommendationService,
)

router = APIRouter(tags=["recommendations"])
RECOMMENDATION_SERVICE_DEPENDENCY = Depends(get_recommendation_service)
PERSONAL_DATA_DEPENDENCY = Depends(get_personal_data_service)
OPTIONAL_CSRF_DEPENDENCY = Depends(require_optional_csrf)
CONTEXT_DEPENDENCY = Depends(get_assistant_context_signer)


@router.post("/recommendations", response_model=RecommendationResponse)
def recommend(
    request: RecommendationRequest,
    service: RecommendationService = RECOMMENDATION_SERVICE_DEPENDENCY,
    session: RequestSession | None = OPTIONAL_CSRF_DEPENDENCY,
    personal_data: PersonalDataService = PERSONAL_DATA_DEPENDENCY,
    signer: AssistantContextSigner = CONTEXT_DEPENDENCY,
) -> RecommendationResponse | JSONResponse:
    try:
        result = service.recommend(request)
    except OriginNotFoundError as exc:
        return _origin_not_found(exc.field_path)
    except ProviderError:
        return _provider_unavailable()
    if session is not None:
        history = personal_data.capture_history(
            user_id=session.authenticated.user_id,
            mode="recommendation",
            request=request,
            result=result,
        )
        result = result.model_copy(update={"history_id": history.id})
    return result.model_copy(update={"assistant_context": _optional_context(signer, result)})


@router.post("/place-evaluations", response_model=PlaceEvaluationResponse)
def evaluate_place(
    request: PlaceEvaluationRequest,
    service: RecommendationService = RECOMMENDATION_SERVICE_DEPENDENCY,
    session: RequestSession | None = OPTIONAL_CSRF_DEPENDENCY,
    personal_data: PersonalDataService = PERSONAL_DATA_DEPENDENCY,
    signer: AssistantContextSigner = CONTEXT_DEPENDENCY,
) -> PlaceEvaluationResponse | JSONResponse:
    try:
        result = service.evaluate(request)
    except OriginNotFoundError as exc:
        return _origin_not_found(exc.field_path)
    except PlaceNotFoundError:
        return _place_not_found()
    except ProviderError:
        return _provider_unavailable()
    if session is not None:
        personal_data.capture_history(
            user_id=session.authenticated.user_id,
            mode="place_evaluation",
            request=request,
            result=result,
        )
    return result.model_copy(update={"assistant_context": _optional_context(signer, result)})


def _optional_context(signer: AssistantContextSigner,
                      result: RecommendationResponse | PlaceEvaluationResponse) -> str | None:
    try:
        return signer.issue(result)
    except ValueError:
        # Bounded AI facts are optional; an otherwise valid query must still succeed.
        return None


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
