from app import usecases
from app.exceptions import NotFound
from app.usecase_handlers.base import DatabaseHandler


class DeleteWatchlistItemHandler(DatabaseHandler):
    def handle(self, usecase: usecases.DeleteWatchlistItemUseCase) -> None:
        with self.transaction() as repositories:
            if (
                repositories.watchlists.find_item(usecase.watchlist_id, usecase.item_id, lock=True)
                is None
            ):
                raise NotFound("Watchlist item not found")
            repositories.watchlists.delete_item(usecase.item_id)
