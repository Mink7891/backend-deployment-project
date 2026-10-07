from app import usecases
from app.domain.pricing import summarize
from app.schemas import (
    SummaryResponse,
)
from app.services.game_refresh_service import require_watchlist
from app.usecase_handlers.base import DatabaseHandler


class GetWatchlistSummaryHandler(DatabaseHandler):
    def handle(self, usecase: usecases.GetWatchlistSummaryUseCase) -> SummaryResponse:
        with self.transaction() as repositories:
            watchlist = require_watchlist(repositories, usecase.watchlist_id)
            return SummaryResponse.model_validate(summarize(watchlist, self.provider.source))
