from fastapi import APIRouter, Response

from app import usecases
from app.api.common import PositiveId
from app.api.dependencies import DispatcherDependency
from app.schemas import AddItemRequest, ItemResponse, UpdateItemRequest
from app.utils.error_responses import get_error_responses

router = APIRouter()


@router.post(
    "/watchlists/{watchlist_id}/items",
    response_model=ItemResponse,
    status_code=201,
    tags=["Items"],
    operation_id="addWatchlistItem",
    summary="Добавить игру",
    description="Добавление уникальной игры в список и проверка порога цены.",
    responses=get_error_responses(401, 404, 409, 422, 500, 503),
)
def add_watchlist_item(
    watchlist_id: PositiveId, body: AddItemRequest, dispatcher: DispatcherDependency
):
    return dispatcher.dispatch(usecases.AddWatchlistItemUseCase(watchlist_id, body))


@router.patch(
    "/watchlists/{watchlist_id}/items/{item_id}",
    response_model=ItemResponse,
    tags=["Items"],
    operation_id="updateWatchlistItem",
    summary="Изменить порог",
    description="Обновление targetPrice и/или steamOnly; пустое тело и null запрещены.",
    responses=get_error_responses(401, 404, 409, 422, 500, 503),
)
def update_watchlist_item(
    watchlist_id: PositiveId,
    item_id: PositiveId,
    body: UpdateItemRequest,
    dispatcher: DispatcherDependency,
):
    return dispatcher.dispatch(usecases.UpdateWatchlistItemUseCase(watchlist_id, item_id, body))


@router.delete(
    "/watchlists/{watchlist_id}/items/{item_id}",
    status_code=204,
    tags=["Items"],
    operation_id="deleteWatchlistItem",
    summary="Удалить игру из списка",
    description="Удаление позиции указанного списка.",
    responses=get_error_responses(401, 404, 422, 500, 503),
)
def delete_watchlist_item(
    watchlist_id: PositiveId, item_id: PositiveId, dispatcher: DispatcherDependency
):
    dispatcher.dispatch(usecases.DeleteWatchlistItemUseCase(watchlist_id, item_id))
    return Response(status_code=204)
