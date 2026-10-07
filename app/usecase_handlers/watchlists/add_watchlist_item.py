from app import usecases
from app.exceptions import Conflict
from app.mappers.responses import present_item
from app.schemas import (
    ItemResponse,
)
from app.services.game_refresh_service import evaluate_item, require_watchlist
from app.usecase_handlers.base import DatabaseHandler


class AddWatchlistItemHandler(DatabaseHandler):
    def handle(self, usecase: usecases.AddWatchlistItemUseCase) -> ItemResponse:
        with self.transaction() as repositories:
            require_watchlist(repositories, usecase.watchlist_id)
            if repositories.watchlists.find_game_item(
                usecase.watchlist_id, usecase.request.game_id
            ):
                raise Conflict("Game is already in this watchlist")
            self.refresh_service.refresh(repositories, usecase.request.game_id)
            item = repositories.watchlists.add_item(
                usecase.watchlist_id,
                usecase.request.game_id,
                usecase.request.target_price,
                usecase.request.steam_only,
            )
            evaluate_item(repositories, item)
            return present_item(repositories.watchlists.find_item(usecase.watchlist_id, item.id))
