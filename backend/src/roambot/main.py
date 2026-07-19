from collections.abc import Mapping
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from roambot.api.dependencies import AuthApiError, auth_api_exception_handler
from roambot.api.errors import (
    error_response,
    request_validation_exception_handler,
    unexpected_exception_handler,
)
from roambot.api.routes.auth import router as auth_router
from roambot.api.routes.favorites import router as favorites_router
from roambot.api.routes.health import router as health_router
from roambot.api.routes.history import router as history_router
from roambot.api.routes.recommendations import router as recommendations_router
from roambot.api.routes.shares import router as shares_router
from roambot.config import ProviderMode, Settings
from roambot.persistence.cache import SessionCacheStore
from roambot.persistence.database import create_engine_and_session_factory, initialize_schema
from roambot.providers.factory import build_provider_runtime


def create_app(
    settings: Settings | None = None,
    frontend_dist: Path | None = None,
    provider_credentials: Mapping[str, str] | None = None,
) -> FastAPI:
    configured_settings = settings or Settings()
    pending_credentials = dict(provider_credentials or {})

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runtime = getattr(app.state, "provider_runtime", None)
        owned_engine = None
        if runtime is None:
            cache_repository = None
            if app.state.settings.provider_mode is ProviderMode.LIVE:
                session_factory = getattr(app.state, "session_factory", None)
                if session_factory is None:
                    owned_engine, session_factory = create_engine_and_session_factory(
                        app.state.settings.database_path
                    )
                    initialize_schema(owned_engine)
                    app.state.auth_engine = owned_engine
                    app.state.session_factory = session_factory
                cache_repository = SessionCacheStore(session_factory)
            try:
                runtime = build_provider_runtime(
                    app.state.settings,
                    pending_credentials,
                    cache_repository=cache_repository,
                )
            finally:
                pending_credentials.clear()
            app.state.provider_runtime = runtime
        else:
            pending_credentials.clear()
        try:
            yield
        finally:
            runtime.close()
            if owned_engine is not None:
                owned_engine.dispose()

    app = FastAPI(title="RoamBot API", version="0.1.0", lifespan=lifespan)
    app.state.settings = configured_settings
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(AuthApiError, auth_api_exception_handler)
    app.add_exception_handler(Exception, unexpected_exception_handler)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(recommendations_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(favorites_router, prefix="/api/v1")
    app.include_router(history_router, prefix="/api/v1")
    app.include_router(shares_router, prefix="/api/v1")
    if frontend_dist is not None:
        assets_dir = frontend_dist / "assets"
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
        index_path = frontend_dist / "index.html"

        @app.get("/{path:path}", include_in_schema=False)
        def serve_spa(path: str) -> Response:
            if path == "api" or path.startswith("api/") or Path(path).suffix:
                return error_response(
                    status_code=404,
                    code="not_found",
                    message="Resource was not found.",
                )
            return FileResponse(index_path)
    return app


app = create_app()
