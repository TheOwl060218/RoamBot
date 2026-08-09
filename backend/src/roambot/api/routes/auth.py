from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from roambot.api.dependencies import (
    SESSION_COOKIE_NAME,
    AuthApiError,
    RequestSession,
    get_auth_service,
    get_settings,
    require_csrf,
    require_session,
)
from roambot.api.errors import error_response
from roambot.config import Settings
from roambot.services.auth import (
    AuthService,
    DuplicateUsernameError,
    InvalidCredentialsError,
    InvalidSessionError,
    SessionGrant,
)

router = APIRouter(prefix="/auth", tags=["auth"])

Username = Annotated[str, Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")]
Password = Annotated[str, Field(min_length=8, max_length=128)]


class CredentialsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: Username
    password: Password


class UserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str


class AuthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: UserResponse
    csrf_token: str


AUTH_SERVICE_DEPENDENCY = Depends(get_auth_service)
SETTINGS_DEPENDENCY = Depends(get_settings)
SESSION_DEPENDENCY = Depends(require_session)
CSRF_DEPENDENCY = Depends(require_csrf)


@router.post("/register", status_code=201, response_model=AuthResponse)
def register(
    credentials: CredentialsRequest,
    response: Response,
    service: AuthService = AUTH_SERVICE_DEPENDENCY,
    settings: Settings = SETTINGS_DEPENDENCY,
) -> AuthResponse | JSONResponse:
    try:
        grant = service.register(credentials.username, credentials.password)
    except DuplicateUsernameError:
        return error_response(
            status_code=409,
            code="username_taken",
            message="Username is already taken.",
        )
    _set_session_cookie(response, grant, settings)
    _set_no_store(response)
    return _auth_response(grant.username, grant.csrf_token)


@router.post("/login", response_model=AuthResponse)
def login(
    credentials: CredentialsRequest,
    response: Response,
    service: AuthService = AUTH_SERVICE_DEPENDENCY,
    settings: Settings = SETTINGS_DEPENDENCY,
) -> AuthResponse | JSONResponse:
    try:
        grant = service.login(credentials.username, credentials.password)
    except InvalidCredentialsError:
        return error_response(
            status_code=401,
            code="invalid_credentials",
            message="Invalid username or password.",
        )
    _set_session_cookie(response, grant, settings)
    _set_no_store(response)
    return _auth_response(grant.username, grant.csrf_token)


@router.get("/me", response_model=AuthResponse)
def me(
    response: Response,
    session: RequestSession = SESSION_DEPENDENCY,
    service: AuthService = AUTH_SERVICE_DEPENDENCY,
) -> AuthResponse:
    try:
        csrf_token = service.rotate_csrf(session.session_token)
    except InvalidSessionError as exc:
        raise AuthApiError(
            status_code=401,
            code="authentication_required",
            message="Authentication is required.",
        ) from exc
    _set_no_store(response)
    return _auth_response(session.authenticated.username, csrf_token)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    session: RequestSession = CSRF_DEPENDENCY,
    service: AuthService = AUTH_SERVICE_DEPENDENCY,
    settings: Settings = SETTINGS_DEPENDENCY,
) -> Response:
    try:
        service.logout(session.session_token)
    except InvalidSessionError as exc:
        raise AuthApiError(
            status_code=401,
            code="authentication_required",
            message="Authentication is required.",
        ) from exc
    response.status_code = 204
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=settings.secure_cookies,
        httponly=True,
        samesite="lax",
    )
    _set_no_store(response)
    return response


def _set_session_cookie(response: Response, grant: SessionGrant, settings: Settings) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=grant.session_token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=settings.session_hours * 3600,
        path="/",
    )


def _set_no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def _auth_response(username: str, csrf_token: str) -> AuthResponse:
    return AuthResponse(user=UserResponse(username=username), csrf_token=csrf_token)
