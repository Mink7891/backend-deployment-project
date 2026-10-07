"""Эндпоинт готовности сервиса — /health (без API-ключа)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.database.session import get_db_session
from game_radar.dependencies.dispatcher_register import get_usecase_dispatcher
from game_radar.dispatcher import UseCaseDispatcher
from game_radar.schemas.game_radar_api import HealthResponse
from game_radar.usecases.health import GetHealthUseCase
from game_radar.utils.error_responses import get_error_responses

router = APIRouter(tags=["Operations"])


@router.get(
    "/health",
    response_model=HealthResponse,
    operation_id="health",
    summary="Готовность сервиса",
    description="Проверка подключения и наличия схемы БД; без API-ключа.",
    responses=get_error_responses(500),
)
async def health(
    session: AsyncSession = Depends(get_db_session),
    dispatcher: UseCaseDispatcher = Depends(get_usecase_dispatcher),
) -> HealthResponse:
    return await dispatcher.dispatch(GetHealthUseCase(), session)
