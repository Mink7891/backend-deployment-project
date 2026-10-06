from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.routes import router
from app.application.exceptions import Conflict, GameNotFound, NotFound, ProviderUnavailable
from app.config import Settings, get_settings
from app.db import get_session
from app.metrics import DATABASE_READY, MetricsMiddleware
from app.models import Watchlist

app = FastAPI(
    title="GameRadar",
    version="0.1.0",
    description=(
        "Game price monitoring for one shared account. All game and watchlist operations require "
        "the same X-API-Key. PRICE_SOURCE=mock uses fictional offline prices. "
        "Prices are USD decimal strings; history records this service's own observations. "
        "Notifications are a database journal; Telegram delivery is planned for later."
    ),
)
app.add_middleware(MetricsMiddleware)
app.include_router(router)


@app.exception_handler(NotFound)
@app.exception_handler(GameNotFound)
async def not_found_handler(request: Request, exc: Exception):
    detail = str(exc) if isinstance(exc, NotFound) else "Game not found"
    return JSONResponse(status_code=404, content={"detail": detail})


@app.exception_handler(Conflict)
@app.exception_handler(IntegrityError)
async def conflict_handler(request: Request, exc: Exception):
    detail = str(exc) if isinstance(exc, Conflict) else "Resource already exists or was removed"
    return JSONResponse(status_code=409, content={"detail": detail})


@app.exception_handler(ProviderUnavailable)
async def provider_unavailable_handler(request: Request, exc: ProviderUnavailable):
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc)},
        headers={"Retry-After": str(exc.retry_after)},
    )


@app.exception_handler(SQLAlchemyError)
async def database_unavailable_handler(request: Request, exc: SQLAlchemyError):
    DATABASE_READY.set(0)
    return JSONResponse(status_code=503, content={"detail": "Database is temporarily unavailable"})


@app.get("/health", tags=["Operations"])
def health(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        session.execute(text("SELECT 1"))
        session.execute(select(Watchlist.id).limit(1))
    except SQLAlchemyError:
        DATABASE_READY.set(0)
        return JSONResponse(
            status_code=503, content={"status": "unready", "database": "unavailable"}
        )
    DATABASE_READY.set(1)
    return {
        "status": "ok",
        "database": "ready",
        "price_source": settings.price_source,
        "mock_prices_are_fictional": settings.price_source == "mock",
    }


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(content=generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})
