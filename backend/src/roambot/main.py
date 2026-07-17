from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from roambot.api.dependencies import AuthApiError, auth_api_exception_handler
from roambot.api.errors import (
    request_validation_exception_handler,
    unexpected_exception_handler,
)
from roambot.api.routes.auth import router as auth_router
from roambot.api.routes.favorites import router as favorites_router
from roambot.api.routes.health import router as health_router
from roambot.api.routes.history import router as history_router
from roambot.api.routes.recommendations import router as recommendations_router


def create_app() -> FastAPI:
    app = FastAPI(title="RoamBot API", version="0.1.0")
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(AuthApiError, auth_api_exception_handler)
    app.add_exception_handler(Exception, unexpected_exception_handler)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(recommendations_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(favorites_router, prefix="/api/v1")
    app.include_router(history_router, prefix="/api/v1")
    return app


app = create_app()
