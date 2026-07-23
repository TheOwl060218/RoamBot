from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from secrets import compare_digest
from threading import Lock

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from roambot.api.errors import error_response
from roambot.config import Settings
from roambot.domain.models import SourceKind
from roambot.persistence.database import (
    SessionFactory,
    create_engine_and_session_factory,
    initialize_schema,
)
from roambot.providers.budget import ProviderOperation
from roambot.providers.factory import ProviderBundle, build_provider_runtime
from roambot.security.sessions import hash_token
from roambot.services.auth import AuthenticatedSession, AuthService, InvalidSessionError
from roambot.services.personal_data import PersonalDataService
from roambot.services.recommendations import RecommendationService


def get_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        settings = Settings()
        request.app.state.settings = settings
    return settings


SETTINGS_DEPENDENCY = Depends(get_settings)


def get_provider_bundle(request: Request) -> ProviderBundle:
    runtime = getattr(request.app.state, "provider_runtime", None)
    if runtime is None:
        settings = get_settings(request)
        runtime = build_provider_runtime(settings, {}, cache_repository=None)
        request.app.state.provider_runtime = runtime
    return runtime.new_request_bundle()


PROVIDER_BUNDLE_DEPENDENCY = Depends(get_provider_bundle)


def get_recommendation_service(
    bundle: ProviderBundle = PROVIDER_BUNDLE_DEPENDENCY,
    settings: Settings = SETTINGS_DEPENDENCY,
) -> RecommendationService:
    source_kind = SourceKind.DEMO if "demo" in bundle.trace.events else SourceKind.LIVE
    return RecommendationService(
        geocoder=bundle.geocoder,
        places=bundle.places,
        distance=bundle.distance,
        weather=bundle.weather,
        explanations=bundle.explanations,
        source_kind=source_kind,
        clock=lambda: datetime.now(UTC),
        provider_limits={
            ProviderOperation.GEOCODE: settings.max_geocode_calls,
            ProviderOperation.POI_SEARCH: settings.max_poi_search_calls,
            ProviderOperation.WEATHER: settings.max_weather_calls,
            ProviderOperation.DISTANCE: settings.max_distance_calls,
            ProviderOperation.LLM: settings.max_llm_calls,
        },
        trace=bundle.trace,
    )


SESSION_COOKIE_NAME = "roambot_session"
_SESSION_FACTORY_LOCK = Lock()


class AuthApiError(Exception):
    def __init__(self, *, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True)
class RequestSession:
    session_token: str
    authenticated: AuthenticatedSession


def get_session_factory(
    request: Request,
    settings: Settings = SETTINGS_DEPENDENCY,
) -> SessionFactory:
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        with _SESSION_FACTORY_LOCK:
            session_factory = getattr(request.app.state, "session_factory", None)
            if session_factory is None:
                engine, session_factory = create_engine_and_session_factory(
                    settings.database_path
                )
                initialize_schema(engine)
                request.app.state.auth_engine = engine
                request.app.state.session_factory = session_factory
    return session_factory


SESSION_FACTORY_DEPENDENCY = Depends(get_session_factory)


def get_auth_service(
    request: Request,
    settings: Settings = SETTINGS_DEPENDENCY,
    session_factory: SessionFactory = SESSION_FACTORY_DEPENDENCY,
) -> AuthService:
    service = getattr(request.app.state, "auth_service", None)
    if service is None:
        service = AuthService(session_factory, session_hours=settings.session_hours)
        request.app.state.auth_service = service
    return service


AUTH_SERVICE_DEPENDENCY = Depends(get_auth_service)


def get_personal_data_service(
    session_factory: SessionFactory = SESSION_FACTORY_DEPENDENCY,
) -> PersonalDataService:
    return PersonalDataService(session_factory)


def get_optional_session(
    request: Request,
    service: AuthService = AUTH_SERVICE_DEPENDENCY,
) -> RequestSession | None:
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_token:
        return None
    try:
        authenticated = service.authenticate(session_token)
    except InvalidSessionError as exc:
        raise _authentication_required() from exc
    return RequestSession(session_token=session_token, authenticated=authenticated)


OPTIONAL_SESSION_DEPENDENCY = Depends(get_optional_session)


def require_session(
    session: RequestSession | None = OPTIONAL_SESSION_DEPENDENCY,
) -> RequestSession:
    if session is None:
        raise _authentication_required()
    return session


REQUIRED_SESSION_DEPENDENCY = Depends(require_session)


def require_csrf(
    request: Request,
    session: RequestSession = REQUIRED_SESSION_DEPENDENCY,
) -> RequestSession:
    _validate_csrf(request, session)
    return session


def require_optional_csrf(
    request: Request,
    session: RequestSession | None = OPTIONAL_SESSION_DEPENDENCY,
) -> RequestSession | None:
    if session is not None:
        _validate_csrf(request, session)
    return session


def _validate_csrf(request: Request, session: RequestSession) -> None:
    csrf_token = request.headers.get("X-CSRF-Token")
    if csrf_token is None or not compare_digest(
        hash_token(csrf_token),
        session.authenticated.csrf_hash,
    ):
        raise AuthApiError(
            status_code=403,
            code="csrf_invalid",
            message="CSRF token is invalid.",
        )


async def auth_api_exception_handler(
    request: Request,
    exc: AuthApiError,
) -> JSONResponse:
    del request
    return error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
    )


def _authentication_required() -> AuthApiError:
    return AuthApiError(
        status_code=401,
        code="authentication_required",
        message="Authentication is required.",
    )
