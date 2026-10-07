from typing import Annotated

from fastapi import APIRouter, Query

from app import usecases
from app.api.common import PageLimit, PageOffset
from app.api.dependencies import DispatcherDependency
from app.schemas import (
    GameCard,
    GameDetails,
    GameId,
    SnapshotResponse,
)
from app.utils.error_responses import get_error_responses

router = APIRouter()


@router.get(
    "/games/search",
    response_model=list[GameCard],
    tags=["Games"],
    operation_id="searchGames",
    summary="Поиск игр",
    description="Поиск у провайдера и сохранение метаданных в локальный каталог.",
    responses=get_error_responses(401, 422, 500, 503),
)
def search_games(
    dispatcher: DispatcherDependency,
    query: Annotated[str, Query(min_length=1, max_length=100, pattern=".*\\S.*")],
    limit: Annotated[int, Query(ge=1, le=60)] = 20,
):
    return dispatcher.dispatch(usecases.SearchGamesUseCase(query.strip(), limit))


@router.get(
    "/games/{game_id}",
    response_model=GameDetails,
    tags=["Games"],
    operation_id="getGame",
    summary="Цены игры",
    description="Получение предложений с кешем и записью истории наблюдений.",
    responses=get_error_responses(401, 404, 422, 500, 503),
)
def get_game(game_id: GameId, dispatcher: DispatcherDependency):
    return dispatcher.dispatch(usecases.GetGameUseCase(game_id))


@router.get(
    "/games/{game_id}/history",
    response_model=list[SnapshotResponse],
    tags=["Games"],
    operation_id="getPriceHistory",
    summary="История цен",
    description="Список локальных наблюдений, новые первыми. limit/offset; возврат массива.",
    responses=get_error_responses(401, 404, 422, 500, 503),
)
def get_price_history(
    game_id: GameId,
    dispatcher: DispatcherDependency,
    limit: PageLimit = 100,
    offset: PageOffset = 0,
):
    return dispatcher.dispatch(usecases.GetPriceHistoryUseCase(game_id, limit, offset))
