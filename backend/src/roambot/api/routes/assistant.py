import logging

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError

from roambot.api.dependencies import get_assistant_service, require_optional_csrf
from roambot.api.errors import error_response
from roambot.domain.assistant import AssistantTurnRequest, AssistantTurnResponse
from roambot.providers.protocols import ProviderError
from roambot.services.assistant import AssistantService
from roambot.services.assistant_limits import AssistantLimitError

logger = logging.getLogger(__name__)
router = APIRouter(tags=["assistant"])
SERVICE = Depends(get_assistant_service)
CSRF = Depends(require_optional_csrf)


@router.post(
    "/assistant/turns", response_model=AssistantTurnResponse, response_model_exclude_unset=True
)
def turn(
    body: AssistantTurnRequest, request: Request, service: AssistantService = SERVICE, session=CSRF
):
    del session
    try:
        key = request.client.host if request.client else "unknown"
        with request.app.state.assistant_limiter.acquire(key):
            return service.turn(body)
    except AssistantLimitError:
        return error_response(
            status_code=429, code="assistant_busy", message="请求较多，请稍后再试。"
        )
    except ValidationError as exc:
        logger.error(
            "assistant_response_invalid detail=%s",
            [(e.get("loc"), e.get("type")) for e in exc.errors(include_url=False)],
        )
        raise
    except ValueError as exc:
        logger.info("assistant_turn_rejected reason=%s", exc)
        return error_response(
            status_code=409,
            code="assistant_context_expired",
            message="当前结果解读已失效，请确认更新推荐；条件仍可手动修改。",
        )
    except ProviderError as exc:
        if exc.code == "configuration_error":
            return error_response(
                status_code=503,
                code="assistant_configuration_error",
                message="当前模型未接通，请检查模型名称或可用通道。",
            )
        return error_response(
            status_code=429 if exc.code == "rate_limited" else 503,
            code="assistant_unavailable",
            message="AI暂不可用，可直接编辑条件继续查询。",
        )
