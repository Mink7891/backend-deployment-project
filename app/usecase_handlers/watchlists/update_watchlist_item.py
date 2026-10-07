from app import usecases
from app.exceptions import NotFound
from app.mappers.responses import present_item
from app.schemas import (
    ItemResponse,
)
from app.services.game_refresh_service import evaluate_item
from app.usecase_handlers.base import DatabaseHandler


class UpdateWatchlistItemHandler(DatabaseHandler):
    def handle(self, usecase: usecases.UpdateWatchlistItemUseCase) -> ItemResponse:
        with self.transaction() as repositories:
            item = repositories.watchlists.find_item(usecase.watchlist_id, usecase.item_id)
            if item is None:
                raise NotFound("Watchlist item not found")
            # Game lock first, then item lock, exactly as in the refresh handler.
            self.refresh_service.refresh(repositories, item.game_id)
            if (
                repositories.watchlists.find_item(usecase.watchlist_id, usecase.item_id, lock=True)
                is None
            ):
                raise NotFound("Watchlist item not found")
            item = repositories.watchlists.update_item(
                usecase.item_id, usecase.request.target_price, usecase.request.steam_only
            )
            evaluate_item(repositories, item)
            return present_item(repositories.watchlists.find_item(usecase.watchlist_id, item.id))
