"""Глобальные обработчики исключений FastAPI (RFC 9457 Problem Details)."""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from game_radar.errors import ServiceError
from game_radar.utils.error_responses import problem_from

logger = logging.getLogger("game_radar.errors")


def _log_extra(request: Request) -> dict[str, object]:
    """Контекст ошибки для JsonLogFormatter — связывает запись с trace_id запроса."""
    return {
        "extra_fields": {
            "trace_id": getattr(request.state, "trace_id", None),
            "path": request.url.path,
            "method": request.method,
        }
    }


async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    """Обрабатывает ServiceError в формате RFC 9457 problem details."""
    request.state.error_code = exc.code
    if exc.status >= 500:
        logger.error("service_error: %s", exc.code, extra=_log_extra(request))
    else:
        logger.warning("service_error: %s — %s", exc.code, exc.detail, extra=_log_extra(request))
    return JSONResponse(
        status_code=exc.status,
        content=problem_from(exc).model_dump(mode="json", by_alias=True, exclude_none=True),
    )


async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """Обрабатывает 404 Not Found."""
    return JSONResponse(
        status_code=404,
        content={
            "type": "urn:game-radar:error:NOT_FOUND",
            "title": "Not Found",
            "status": 404,
            "detail": "Requested resource not found",
        },
    )


async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Обрабатывает ValueError как 400 Bad Request."""
    logger.warning("value_error: %s", exc, extra=_log_extra(request))
    return JSONResponse(
        status_code=400,
        content={
            "type": "urn:game-radar:error:BAD_REQUEST",
            "title": "Bad Request",
            "status": 400,
            "detail": str(exc),
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Обрабатывает Starlette HTTPException."""
    logger.warning("http_exception: %s", exc.detail, extra=_log_extra(request))
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": "urn:game-radar:error:HTTP_ERROR",
            "title": "HTTP Error",
            "status": exc.status_code,
            "detail": exc.detail,
        },
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Обрабатывает ошибки валидации запроса."""
    errors = [
        {"loc": error.get("loc"), "msg": error.get("msg"), "type": error.get("type")}
        for error in exc.errors()
    ]
    logger.warning("validation_error: %s", errors, extra=_log_extra(request))
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            {
                "type": "urn:game-radar:error:VALIDATION_ERROR",
                "title": "Validation Error",
                "status": 422,
                "detail": "Request validation failed",
                "errors": errors,
            }
        ),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Обрабатывает непредвиденные исключения."""
    logger.error("unexpected_error", exc_info=exc, extra=_log_extra(request))
    return JSONResponse(
        status_code=500,
        content={
            "type": "urn:game-radar:error:INTERNAL_ERROR",
            "title": "Internal Server Error",
            "status": 500,
            "detail": "An unexpected error occurred",
        },
    )
