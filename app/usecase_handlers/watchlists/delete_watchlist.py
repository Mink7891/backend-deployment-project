from app import usecases
from app.services.game_refresh_service import require_watchlist
from app.usecase_handlers.base import DatabaseHandler


class DeleteWatchlistHandler(DatabaseHandler):
    def handle(self, usecase: usecases.DeleteWatchlistUseCase) -> None:
        with self.transaction() as repositories:
            require_watchlist(repositories, usecase.watchlist_id)
            repositories.watchlists.delete(usecase.watchlist_id)
