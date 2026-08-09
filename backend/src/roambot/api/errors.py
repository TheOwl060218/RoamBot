from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict


class ErrorField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    message: str


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    fields: list[ErrorField]


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorBody


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    fields: list[ErrorField] | None = None,
) -> JSONResponse:
    envelope = ErrorEnvelope(
        error=ErrorBody(code=code, message=message, fields=fields or []),
    )
    return JSONResponse(status_code=status_code, content=envelope.model_dump())


async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    del request
    return error_response(
        status_code=422,
        code="validation_error",
        message="Request validation failed.",
        fields=[
            ErrorField(path=_field_path(error.get("loc", ())), message=str(error["msg"]))
            for error in exc.errors()
        ],
    )


async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    del request, exc
    return error_response(
        status_code=500,
        code="unexpected_error",
        message="Unexpected server error.",
    )


def _field_path(loc: Sequence[Any]) -> str:
    parts = list(loc)
    if parts and parts[0] in {"body", "query", "path"}:
        parts = parts[1:]
    if not parts:
        return ""

    path = ""
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
            continue
        if path:
            path += "."
        path += str(part)
    return path
