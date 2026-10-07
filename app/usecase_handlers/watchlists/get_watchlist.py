from app import usecases
from app.mappers.responses import present_watchlist
from app.schemas import (
    WatchlistDetails,
)
from app.services.game_refresh_service import require_watchlist
from app.usecase_handlers.base import DatabaseHandler


class GetWatchlistHandler(DatabaseHandler):
    def handle(self, usecase: usecases.GetWatchlistUseCase) -> WatchlistDetails:
        with self.transaction() as repositories:
            return present_watchlist(require_watchlist(repositories, usecase.watchlist_id))
