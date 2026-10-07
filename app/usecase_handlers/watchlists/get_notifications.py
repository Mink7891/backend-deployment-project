from app import usecases
from app.schemas import (
    NotificationResponse,
)
from app.services.game_refresh_service import require_watchlist
from app.usecase_handlers.base import DatabaseHandler


class GetNotificationsHandler(DatabaseHandler):
    def handle(self, usecase: usecases.GetNotificationsUseCase) -> list[NotificationResponse]:
        with self.transaction() as repositories:
            require_watchlist(repositories, usecase.watchlist_id)
            return [
                NotificationResponse.model_validate(row)
                for row in repositories.watchlists.notifications(
                    usecase.watchlist_id, usecase.limit, usecase.offset
                )
            ]
