"""Эндпоинты списков наблюдения — /watchlists."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.api.common import PageLimit, PageOffset, PositiveId
from game_radar.auth.api_key import require_api_key
from game_radar.database.session import get_db_session
from game_radar.dependencies.dispatcher_register import get_usecase_dispatcher
from game_radar.dispatcher import UseCaseDispatcher
from game_radar.schemas.game_radar_api import (
    AddItemRequest,
    CreateWatchlistRequest,
    ItemResponse,
    NotificationResponse,
    RefreshResponse,
    SummaryResponse,
    UpdateItemRequest,
    WatchlistDetails,
    WatchlistResponse,
)
from game_radar.usecases.refresh import RefreshWatchlistUseCase
from game_radar.usecases.watchlists import (
    AddWatchlistItemUseCase,
    CreateWatchlistUseCase,
    DeleteWatchlistItemUseCase,
    DeleteWatchlistUseCase,
    GetNotificationsUseCase,
    GetWatchlistSummaryUseCase,
    GetWatchlistUseCase,
    ListWatchlistsUseCase,
    UpdateWatchlistItemUseCase,
)
from game_radar.utils.error_responses import get_error_responses

router = APIRouter(
    prefix="/watchlists", tags=["Watchlists"], dependencies=[Depends(require_api_key)]
)


@router.post(
    "",
    response_model=WatchlistResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="createWatchlist",
    summary="Создать список",
    responses=get_error_responses(401, 422),
)
async def create_watchlist(
    body: CreateWatchlistRequest,
    session: AsyncSession = Depends(get_db_session),
    dispatcher: UseCaseDispatcher = Depends(get_usecase_dispatcher),
) -> WatchlistResponse:
    usecase = CreateWatchlistUseCase(name=body.name)
    return await dispatcher.dispatch(usecase, session)


@router.get(
    "",
    response_model=list[WatchlistResponse],
    operation_id="listWatchlists",
    summary="Списки наблюдения",
    responses=get_error_responses(401),
)
async def list_watchlists(
    session: AsyncSession = Depends(get_db_session),
    dispatcher: UseCaseDispatcher = Depends(get_usecase_dispatcher),
) -> list[WatchlistResponse]:
    return await dispatcher.dispatch(ListWatchlistsUseCase(), session)


@router.get(
    "/{watchlist_id}",
    response_model=WatchlistDetails,
    operation_id="getWatchlist",
    summary="Содержимое списка",
    description="Получение списка с играми и текущими ценами.",
    responses=get_error_responses(401, 404, 422),
)
async def get_watchlist(
    watchlist_id: PositiveId,
    session: AsyncSession = Depends(get_db_session),
    dispatcher: UseCaseDispatcher = Depends(get_usecase_dispatcher),
) -> WatchlistDetails:
    usecase = GetWatchlistUseCase(watchlist_id=watchlist_id)
    return await dispatcher.dispatch(usecase, session)


@router.delete(
    "/{watchlist_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteWatchlist",
    summary="Удалить список",
    responses=get_error_responses(401, 404, 422),
)
async def delete_watchlist(
    watchlist_id: PositiveId,
    session: AsyncSession = Depends(get_db_session),
    dispatcher: UseCaseDispatcher = Depends(get_usecase_dispatcher),
) -> Response:
    usecase = DeleteWatchlistUseCase(watchlist_id=watchlist_id)
    await dispatcher.dispatch(usecase, session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{watchlist_id}/summary",
    response_model=SummaryResponse,
    operation_id="getWatchlistSummary",
    summary="Сводка списка",
    description="Сумма доступных цен и количество достигших порога игр.",
    responses=get_error_responses(401, 404, 422),
)
async def get_watchlist_summary(
    watchlist_id: PositiveId,
    session: AsyncSession = Depends(get_db_session),
    dispatcher: UseCaseDispatcher = Depends(get_usecase_dispatcher),
) -> SummaryResponse:
    usecase = GetWatchlistSummaryUseCase(watchlist_id=watchlist_id)
    return await dispatcher.dispatch(usecase, session)


@router.post(
    "/{watchlist_id}/refresh",
    response_model=RefreshResponse,
    operation_id="refreshWatchlist",
    summary="Обновить цены",
    description="Обновление с учётом кеша; повторные уведомления не создаются до нового перехода.",
    responses=get_error_responses(401, 404, 422, 503),
)
async def refresh_watchlist(
    watchlist_id: PositiveId,
    session: AsyncSession = Depends(get_db_session),
    dispatcher: UseCaseDispatcher = Depends(get_usecase_dispatcher),
) -> RefreshResponse:
    usecase = RefreshWatchlistUseCase(watchlist_id=watchlist_id)
    return await dispatcher.dispatch(usecase, session)


@router.post(
    "/{watchlist_id}/items",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Items"],
    operation_id="addWatchlistItem",
    summary="Добавить игру",
    description="Добавление уникальной игры в список и проверка порога цены.",
    responses=get_error_responses(401, 404, 409, 422, 503),
)
async def add_watchlist_item(
    watchlist_id: PositiveId,
    body: AddItemRequest,
    session: AsyncSession = Depends(get_db_session),
    dispatcher: UseCaseDispatcher = Depends(get_usecase_dispatcher),
) -> ItemResponse:
    usecase = AddWatchlistItemUseCase(
        watchlist_id=watchlist_id,
        game_id=body.game_id,
        target_price=body.target_price,
        steam_only=body.steam_only,
    )
    return await dispatcher.dispatch(usecase, session)


@router.patch(
    "/{watchlist_id}/items/{item_id}",
    response_model=ItemResponse,
    tags=["Items"],
    operation_id="updateWatchlistItem",
    summary="Изменить порог",
    description="Обновление targetPrice и/или steamOnly; пустое тело и null запрещены.",
    responses=get_error_responses(401, 404, 422, 503),
)
async def update_watchlist_item(
    watchlist_id: PositiveId,
    item_id: PositiveId,
    body: UpdateItemRequest,
    session: AsyncSession = Depends(get_db_session),
    dispatcher: UseCaseDispatcher = Depends(get_usecase_dispatcher),
) -> ItemResponse:
    usecase = UpdateWatchlistItemUseCase(
        watchlist_id=watchlist_id,
        item_id=item_id,
        target_price=body.target_price,
        steam_only=body.steam_only,
    )
    return await dispatcher.dispatch(usecase, session)


@router.delete(
    "/{watchlist_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Items"],
    operation_id="deleteWatchlistItem",
    summary="Удалить игру из списка",
    responses=get_error_responses(401, 404, 422),
)
async def delete_watchlist_item(
    watchlist_id: PositiveId,
    item_id: PositiveId,
    session: AsyncSession = Depends(get_db_session),
    dispatcher: UseCaseDispatcher = Depends(get_usecase_dispatcher),
) -> Response:
    usecase = DeleteWatchlistItemUseCase(watchlist_id=watchlist_id, item_id=item_id)
    await dispatcher.dispatch(usecase, session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{watchlist_id}/notifications",
    response_model=list[NotificationResponse],
    tags=["Notifications"],
    operation_id="getNotifications",
    summary="Журнал уведомлений",
    description="Записи переходов через порог цены, новые первыми; limit/offset.",
    responses=get_error_responses(401, 404, 422),
)
async def get_notifications(
    watchlist_id: PositiveId,
    limit: PageLimit = 100,
    offset: PageOffset = 0,
    session: AsyncSession = Depends(get_db_session),
    dispatcher: UseCaseDispatcher = Depends(get_usecase_dispatcher),
) -> list[NotificationResponse]:
    usecase = GetNotificationsUseCase(watchlist_id=watchlist_id, limit=limit, offset=offset)
    return await dispatcher.dispatch(usecase, session)
