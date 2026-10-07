"""Application entry point - FastAPI app with lifespan, middleware, exception handlers."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.exceptions import HTTPException

from game_radar.app.main_api import main_router
from game_radar.config import settings
from game_radar.database.session import close_db_session
from game_radar.dependencies.dispatcher_register import init_dispatcher
from game_radar.errors import ServiceError
from game_radar.middleware.logging import RequestLoggingMiddleware, configure_logging
from game_radar.utils.errors_handlers import (
    generic_exception_handler,
    http_exception_handler,
    not_found_handler,
    service_error_handler,
    validation_exception_handler,
    value_error_handler,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown.

    Схема БД создаётся миграциями (`alembic upgrade head`) до запуска приложения.
    """
    init_dispatcher()
    try:
        yield
    finally:
        await close_db_session()


configure_logging(settings.LOG_LEVEL)

app = FastAPI(
    title="Game Radar",
    version="0.2.0",
    description=(
        "Мониторинг цен на игры: поиск, wishlist с желаемой ценой, история цен "
        "и журнал достижения порога. Доступ по заголовку X-API-Key. "
        "Цены в USD возвращаются точными десятичными строками."
    ),
    lifespan=lifespan,
)

# Prometheus metrics: http_requests_total, http_request_duration_seconds и др.
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# Middleware
app.add_middleware(RequestLoggingMiddleware)

# Exception handlers (order matters: most specific first)
app.add_exception_handler(ServiceError, service_error_handler)
app.add_exception_handler(ValueError, value_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(404, not_found_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Router
app.include_router(main_router)
