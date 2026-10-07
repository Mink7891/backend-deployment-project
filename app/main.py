from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import select, text
from sqlalchemy.engine import Connection

from app.adapters.providers import get_provider
from app.api.routes import router
from app.config import Settings, get_settings
from app.db import engine, get_connection
from app.dependencies.dispatcher_register import init_dispatcher
from app.log_config import configure_logging
from app.metrics import DATABASE_READY, MetricsMiddleware
from app.middleware.log_middleware import RequestLoggingMiddleware
from app.models import watchlists
from app.schemas import HealthResponse
from app.utils.error_responses import get_error_responses
from app.utils.errors_handlers import register_exception_handlers


@asynccontextmanager
async def lifespan(application: FastAPI):
    configure_logging()
    settings = get_settings()
    application.state.dispatcher = init_dispatcher(
        engine.connect, get_provider(), settings.refresh_min_interval_seconds
    )
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(
    title="GameRadar",
    version="0.2.0",
    lifespan=lifespan,
    description=(
        "Мониторинг цен на игры для общего аккаунта, доступ по X-API-Key. "
        "JSON-поля в camelCase, цены в USD возвращаются точными десятичными строками. "
        "PRICE_SOURCE=mock использует вымышленные офлайн-цены. История содержит "
        "собственные наблюдения сервиса. Уведомления хранятся в БД; Telegram будет позже."
    ),
)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RequestLoggingMiddleware)
register_exception_handlers(app)
app.include_router(router)


@app.get(
    "/health",
    tags=["Operations"],
    response_model=HealthResponse,
    operation_id="health",
    summary="Готовность сервиса",
    description="Проверка подключения и наличия схемы БД; без API-ключа.",
    responses=get_error_responses(422, 503, 500),
)
def health(
    connection: Annotated[Connection, Depends(get_connection)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    connection.execute(text("SELECT 1"))
    connection.execute(select(watchlists.c.id).limit(1))
    DATABASE_READY.set(1)
    return HealthResponse(
        status="ok",
        database="ready",
        price_source=settings.price_source,
        mock_prices_are_fictional=settings.price_source == "mock",
    )


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(content=generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})
