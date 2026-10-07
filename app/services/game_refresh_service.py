from datetime import UTC, datetime

from app.adapters.ports import PriceProvider
from app.domain.entities import Game, Notification, Watchlist, WatchlistItem
from app.domain.pricing import best_price
from app.exceptions import NotFound
from app.repositories import RepositorySet


def require_watchlist(repositories: RepositorySet, watchlist_id: int) -> Watchlist:
    watchlist = repositories.watchlists.get(watchlist_id)
    if watchlist is None:
        raise NotFound("Watchlist not found")
    return watchlist


def evaluate_item(repositories: RepositorySet, item: WatchlistItem) -> Notification | None:
    price = best_price(item.game, item.steam_only)
    matched = price is not None and price <= item.target_price
    notification = None
    if matched and not item.alert_active:
        notification = repositories.watchlists.add_notification(item, price)
    if matched != item.alert_active:
        repositories.watchlists.set_alert_active(item.id, matched)
    return notification


class GameRefreshService:
    """Stateless shared pricing service; the caller owns its transaction."""

    def __init__(self, provider: PriceProvider, cache_ttl_seconds: int):
        self.provider = provider
        self.cache_ttl_seconds = cache_ttl_seconds

    def refresh(
        self, repositories: RepositorySet, game_id: str
    ) -> tuple[Game, bool, list[Notification]]:
        now = datetime.now(UTC)
        game = repositories.games.get(game_id, lock=True)
        cached = (
            game is not None
            and game.source == self.provider.source
            and game.last_refreshed_at is not None
            and (now - game.last_refreshed_at).total_seconds() < self.cache_ttl_seconds
        )
        if not cached:
            data = self.provider.get_game(game_id)
            game = repositories.games.save_observation(data, now)
        notifications = []
        for item in repositories.watchlists.items_for_game(game_id, lock=True):
            notification = evaluate_item(repositories, item)
            if notification:
                notifications.append(notification)
        return game, not cached, notifications
