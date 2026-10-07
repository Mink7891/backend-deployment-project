from app import usecases
from app.schemas import (
    WatchlistResponse,
)
from app.usecase_handlers.base import DatabaseHandler


class CreateWatchlistHandler(DatabaseHandler):
    def handle(self, usecase: usecases.CreateWatchlistUseCase) -> WatchlistResponse:
        with self.transaction() as repositories:
            return WatchlistResponse.model_validate(
                repositories.watchlists.create(usecase.request.name)
            )
