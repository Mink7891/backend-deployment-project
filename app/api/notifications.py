from fastapi import APIRouter

from app import usecases
from app.api.common import PageLimit, PageOffset, PositiveId
from app.api.dependencies import DispatcherDependency
from app.schemas import NotificationResponse
from app.utils.error_responses import get_error_responses

router = APIRouter()


@router.get(
    "/watchlists/{watchlist_id}/notifications",
    response_model=list[NotificationResponse],
    tags=["Notifications"],
    operation_id="getNotifications",
    summary="Журнал уведомлений",
    description="Записи переходов через порог цены, новые первыми; limit/offset.",
    responses=get_error_responses(401, 404, 422, 500, 503),
)
def get_notifications(
    watchlist_id: PositiveId,
    dispatcher: DispatcherDependency,
    limit: PageLimit = 100,
    offset: PageOffset = 0,
):
    return dispatcher.dispatch(usecases.GetNotificationsUseCase(watchlist_id, limit, offset))
