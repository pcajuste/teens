"""Global exception handlers: every 4xx/5xx response body is shaped
{"error": {"code": ..., "message": ...}}, regardless of whether it
originated from an HTTPException(detail={"code", "message"}) raised in
app code (e.g. app/core/security.py), FastAPI's request validation, or
an unhandled exception.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _error_response(status_code: int, code: str, message: str, extra: dict | None = None) -> JSONResponse:
    body = {"code": code, "message": message}
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status_code, content={"error": body})


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
            # Any keys beyond code/message pass through as-is -- e.g.
            # ftc_module_required's module_id, retake_cooldown's
            # available_at (Build Prompt 8H) -- so a route-specific
            # error can hand the frontend structured context without a
            # separate lookup, without every other route needing to
            # adopt the same shape.
            extra = {k: v for k, v in exc.detail.items() if k not in ("code", "message")}
            return _error_response(exc.status_code, exc.detail["code"], exc.detail["message"], extra)
        return _error_response(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "validation_error",
            "Request failed validation.",
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "An unexpected error occurred.",
        )
