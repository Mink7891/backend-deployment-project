from app import usecases
from app.domain.pricing import threshold_met
from app.schemas import RefreshResponse
from app.services.game_refresh_service import require_watchlist
from app.usecase_handlers.base import DatabaseHandler


class RefreshWatchlistHandler(DatabaseHandler):
    def handle(self, usecase: usecases.RefreshWatchlistUseCase) -> RefreshResponse:
        with self.transaction() as repositories:
            watchlist = require_watchlist(repositories, usecase.watchlist_id)
            refreshed = notifications_created = 0
            refresher = self.refresh_service
            for game_id in sorted({item.game_id for item in watchlist.items}):
                _, updated, notifications = refresher.refresh(repositories, game_id)
                refreshed += updated
                notifications_created += sum(
                    notification.watchlist_id == usecase.watchlist_id
                    for notification in notifications
                )
            watchlist = require_watchlist(repositories, usecase.watchlist_id)
            return RefreshResponse(
                watchlist_id=usecase.watchlist_id,
                refreshed_games=refreshed,
                checked_items=len(watchlist.items),
                matched_count=sum(threshold_met(item) for item in watchlist.items),
                notifications_created=notifications_created,
            )
