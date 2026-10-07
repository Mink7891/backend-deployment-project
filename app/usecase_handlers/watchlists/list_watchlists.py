from app import usecases
from app.schemas import (
    WatchlistResponse,
)
from app.usecase_handlers.base import DatabaseHandler


class ListWatchlistsHandler(DatabaseHandler):
    def handle(self, usecase: usecases.ListWatchlistsUseCase) -> list[WatchlistResponse]:
        with self.transaction() as repositories:
            return [WatchlistResponse.model_validate(row) for row in repositories.watchlists.list()]
