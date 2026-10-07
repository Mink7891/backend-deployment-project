from fastapi import APIRouter, Response

from app import usecases
from app.api.common import PositiveId
from app.api.dependencies import DispatcherDependency
from app.schemas import (
    CreateWatchlistRequest,
    RefreshResponse,
    SummaryResponse,
    WatchlistDetails,
    WatchlistResponse,
)
from app.utils.error_responses import get_error_responses

router = APIRouter()


@router.post(
    "/watchlists",
    response_model=WatchlistResponse,
    status_code=201,
    tags=["Watchlists"],
    operation_id="createWatchlist",
    summary="Создать список",
    description="Создание списка наблюдения общего аккаунта.",
    responses=get_error_responses(401, 422, 500, 503),
)
def create_watchlist(body: CreateWatchlistRequest, dispatcher: DispatcherDependency):
    return dispatcher.dispatch(usecases.CreateWatchlistUseCase(body))


@router.get(
    "/watchlists",
    response_model=list[WatchlistResponse],
    tags=["Watchlists"],
    operation_id="listWatchlists",
    summary="Списки наблюдения",
    description="Получение всех списков общего аккаунта.",
    responses=get_error_responses(401, 422, 500, 503),
)
def list_watchlists(dispatcher: DispatcherDependency):
    return dispatcher.dispatch(usecases.ListWatchlistsUseCase())


@router.get(
    "/watchlists/{watchlist_id}",
    response_model=WatchlistDetails,
    tags=["Watchlists"],
    operation_id="getWatchlist",
    summary="Содержимое списка",
    description="Получение списка с играми и текущими ценами.",
    responses=get_error_responses(401, 404, 422, 500, 503),
)
def get_watchlist(watchlist_id: PositiveId, dispatcher: DispatcherDependency):
    return dispatcher.dispatch(usecases.GetWatchlistUseCase(watchlist_id))


@router.delete(
    "/watchlists/{watchlist_id}",
    status_code=204,
    tags=["Watchlists"],
    operation_id="deleteWatchlist",
    summary="Удалить список",
    description="Удаление списка и его зависимых записей.",
    responses=get_error_responses(401, 404, 422, 500, 503),
)
def delete_watchlist(watchlist_id: PositiveId, dispatcher: DispatcherDependency):
    dispatcher.dispatch(usecases.DeleteWatchlistUseCase(watchlist_id))
    return Response(status_code=204)


@router.get(
    "/watchlists/{watchlist_id}/summary",
    response_model=SummaryResponse,
    tags=["Watchlists"],
    operation_id="getWatchlistSummary",
    summary="Сводка списка",
    description="Сумма доступных цен и количество достигших порога игр.",
    responses=get_error_responses(401, 404, 422, 500, 503),
)
def get_watchlist_summary(watchlist_id: PositiveId, dispatcher: DispatcherDependency):
    return dispatcher.dispatch(usecases.GetWatchlistSummaryUseCase(watchlist_id))


@router.post(
    "/watchlists/{watchlist_id}/refresh",
    response_model=RefreshResponse,
    tags=["Watchlists"],
    operation_id="refreshWatchlist",
    summary="Обновить цены",
    description="Обновление с учётом кеша; повторные уведомления не создаются до нового перехода.",
    responses=get_error_responses(401, 404, 422, 500, 503),
)
def refresh_watchlist(watchlist_id: PositiveId, dispatcher: DispatcherDependency):
    return dispatcher.dispatch(usecases.RefreshWatchlistUseCase(watchlist_id))
