"""Эндпоинты игр и цен — /games."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.api.common import PageLimit, PageOffset
from game_radar.auth.api_key import require_api_key
from game_radar.database.session import get_db_session
from game_radar.dependencies.dispatcher_register import get_usecase_dispatcher
from game_radar.dispatcher import UseCaseDispatcher
from game_radar.schemas.game_radar_api import GameCard, GameDetails, SnapshotResponse
from game_radar.schemas.types import GameId
from game_radar.usecases.games import GetGameUseCase, GetPriceHistoryUseCase, SearchGamesUseCase
from game_radar.utils.error_responses import get_error_responses

router = APIRouter(prefix="/games", tags=["Games"], dependencies=[Depends(require_api_key)])


@router.get(
    "/search",
    response_model=list[GameCard],
    operation_id="searchGames",
    summary="Поиск игр",
    description="Поиск у провайдера и сохранение метаданных в локальный каталог.",
    responses=get_error_responses(401, 422, 503),
)
async def search_games(
    query: str = Query(min_length=1, max_length=100, pattern=r".*\S.*"),
    limit: int = Query(default=20, ge=1, le=60),
    session: AsyncSession = Depends(get_db_session),
    dispatcher: UseCaseDispatcher = Depends(get_usecase_dispatcher),
) -> list[GameCard]:
    usecase = SearchGamesUseCase(query=query.strip(), limit=limit)
    return await dispatcher.dispatch(usecase, session)


@router.get(
    "/{game_id}",
    response_model=GameDetails,
    operation_id="getGame",
    summary="Цены игры",
    description="Получение предложений с кешем и записью истории наблюдений.",
    responses=get_error_responses(401, 404, 422, 503),
)
async def get_game(
    game_id: GameId,
    session: AsyncSession = Depends(get_db_session),
    dispatcher: UseCaseDispatcher = Depends(get_usecase_dispatcher),
) -> GameDetails:
    usecase = GetGameUseCase(game_id=game_id)
    return await dispatcher.dispatch(usecase, session)


@router.get(
    "/{game_id}/history",
    response_model=list[SnapshotResponse],
    operation_id="getPriceHistory",
    summary="История цен",
    description="Список локальных наблюдений, новые первыми. limit/offset; возврат массива.",
    responses=get_error_responses(401, 404, 422),
)
async def get_price_history(
    game_id: GameId,
    limit: PageLimit = 100,
    offset: PageOffset = 0,
    session: AsyncSession = Depends(get_db_session),
    dispatcher: UseCaseDispatcher = Depends(get_usecase_dispatcher),
) -> list[SnapshotResponse]:
    usecase = GetPriceHistoryUseCase(game_id=game_id, limit=limit, offset=offset)
    return await dispatcher.dispatch(usecase, session)
