from datetime import UTC, datetime

from app.application.exceptions import NotFound
from app.application.ports import PriceProvider, UnitOfWork
from app.domain.entities import Game, Notification, Watchlist, WatchlistItem
from app.domain.pricing import best_price


def require_watchlist(uow: UnitOfWork, watchlist_id: int) -> Watchlist:
    watchlist = uow.watchlists.get(watchlist_id)
    if watchlist is None:
        raise NotFound("Watchlist not found")
    return watchlist


def evaluate_item(uow: UnitOfWork, item: WatchlistItem) -> Notification | None:
    price = best_price(item.game, item.steam_only)
    matched = price is not None and price <= item.target_price
    notification = None
    if matched and not item.alert_active:
        notification = uow.watchlists.add_notification(item, price)
    if matched != item.alert_active:
        uow.watchlists.set_alert_active(item.id, matched)
    return notification


class GameRefresher:
    def __init__(self, uow: UnitOfWork, provider: PriceProvider, cache_ttl_seconds: int):
        self.uow = uow
        self.provider = provider
        self.cache_ttl_seconds = cache_ttl_seconds

    def refresh(self, game_id: str) -> tuple[Game, bool, list[Notification]]:
        now = datetime.now(UTC)
        game = self.uow.games.get(game_id, lock=True)
        cached = (
            game is not None
            and game.source == self.provider.source
            and game.last_refreshed_at is not None
            and (now - game.last_refreshed_at).total_seconds() < self.cache_ttl_seconds
        )
        if not cached:
            data = self.provider.get_game(game_id)
            game = self.uow.games.save_observation(data, now)
        notifications = []
        for item in self.uow.watchlists.items_for_game(game_id, lock=True):
            notification = evaluate_item(self.uow, item)
            if notification:
                notifications.append(notification)
        return game, not cached, notifications
