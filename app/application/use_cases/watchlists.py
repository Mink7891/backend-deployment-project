from decimal import Decimal

from app.application.exceptions import Conflict, NotFound
from app.application.ports import PriceProvider, UnitOfWork
from app.application.use_cases.shared import GameRefresher, evaluate_item, require_watchlist
from app.domain.entities import Notification, Watchlist, WatchlistItem, WatchlistSummary
from app.domain.pricing import summarize


class CreateWatchlist:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def execute(self, name: str) -> Watchlist:
        watchlist = self.uow.watchlists.create(name)
        self.uow.commit()
        return watchlist


class ListWatchlists:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def execute(self) -> list[Watchlist]:
        return self.uow.watchlists.list()


class GetWatchlist:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def execute(self, watchlist_id: int) -> Watchlist:
        return require_watchlist(self.uow, watchlist_id)


class DeleteWatchlist:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def execute(self, watchlist_id: int) -> None:
        require_watchlist(self.uow, watchlist_id)
        self.uow.watchlists.delete(watchlist_id)
        self.uow.commit()


class AddWatchlistItem:
    def __init__(self, uow: UnitOfWork, provider: PriceProvider, cache_ttl_seconds: int):
        self.uow = uow
        self.refresher = GameRefresher(uow, provider, cache_ttl_seconds)

    def execute(
        self, watchlist_id: int, game_id: str, target_price: Decimal, steam_only: bool = True
    ) -> WatchlistItem:
        require_watchlist(self.uow, watchlist_id)
        if self.uow.watchlists.find_game_item(watchlist_id, game_id):
            raise Conflict("Game is already in this watchlist")
        self.refresher.refresh(game_id)
        item = self.uow.watchlists.add_item(watchlist_id, game_id, target_price, steam_only)
        evaluate_item(self.uow, item)
        self.uow.commit()
        return self.uow.watchlists.find_item(watchlist_id, item.id)


class UpdateWatchlistItem:
    def __init__(self, uow: UnitOfWork, provider: PriceProvider, cache_ttl_seconds: int):
        self.uow = uow
        self.refresher = GameRefresher(uow, provider, cache_ttl_seconds)

    def execute(
        self,
        watchlist_id: int,
        item_id: int,
        target_price: Decimal | None = None,
        steam_only: bool | None = None,
    ) -> WatchlistItem:
        item = self.uow.watchlists.find_item(watchlist_id, item_id)
        if item is None:
            raise NotFound("Watchlist item not found")
        # Acquire the game lock before the item lock, consistently with refresh use cases.
        self.refresher.refresh(item.game_id)
        if self.uow.watchlists.find_item(watchlist_id, item_id, lock=True) is None:
            raise NotFound("Watchlist item not found")
        item = self.uow.watchlists.update_item(item_id, target_price, steam_only)
        evaluate_item(self.uow, item)
        self.uow.commit()
        return self.uow.watchlists.find_item(watchlist_id, item_id)


class DeleteWatchlistItem:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def execute(self, watchlist_id: int, item_id: int) -> None:
        if self.uow.watchlists.find_item(watchlist_id, item_id, lock=True) is None:
            raise NotFound("Watchlist item not found")
        self.uow.watchlists.delete_item(item_id)
        self.uow.commit()


class GetWatchlistSummary:
    def __init__(self, uow: UnitOfWork, source: str):
        self.uow = uow
        self.source = source

    def execute(self, watchlist_id: int) -> WatchlistSummary:
        return summarize(require_watchlist(self.uow, watchlist_id), self.source)


class GetNotifications:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def execute(self, watchlist_id: int, limit: int = 100, offset: int = 0) -> list[Notification]:
        require_watchlist(self.uow, watchlist_id)
        return self.uow.watchlists.notifications(watchlist_id, limit, offset)
