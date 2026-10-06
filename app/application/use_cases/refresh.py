import logging
from collections.abc import Callable

from app.application.exceptions import GameNotFound, ProviderUnavailable
from app.application.ports import PriceProvider, UnitOfWork
from app.application.use_cases.shared import GameRefresher, require_watchlist
from app.domain.entities import RefreshResult
from app.domain.pricing import threshold_met

logger = logging.getLogger(__name__)


class RefreshWatchlist:
    def __init__(self, uow: UnitOfWork, provider: PriceProvider, cache_ttl_seconds: int):
        self.uow = uow
        self.refresher = GameRefresher(uow, provider, cache_ttl_seconds)

    def execute(self, watchlist_id: int) -> RefreshResult:
        watchlist = require_watchlist(self.uow, watchlist_id)
        refreshed = notifications_created = 0
        for game_id in sorted({item.game_id for item in watchlist.items}):
            _, updated, notifications = self.refresher.refresh(game_id)
            refreshed += updated
            notifications_created += sum(n.watchlist_id == watchlist_id for n in notifications)
        self.uow.commit()
        watchlist = require_watchlist(self.uow, watchlist_id)
        return RefreshResult(
            watchlist_id=watchlist_id,
            refreshed_games=refreshed,
            checked_items=len(watchlist.items),
            matched_count=sum(threshold_met(item) for item in watchlist.items),
            notifications_created=notifications_created,
        )


class RefreshAllWatchedGames:
    def __init__(
        self,
        uow: UnitOfWork,
        provider: PriceProvider,
        cache_ttl_seconds: int,
        should_stop: Callable[[], bool] | None = None,
    ):
        self.uow = uow
        self.refresher = GameRefresher(uow, provider, cache_ttl_seconds)
        self.failed_games = 0
        self.should_stop = should_stop or (lambda: False)

    def execute(self) -> RefreshResult:
        refreshed = checked = matched = notifications_created = 0
        self.failed_games = 0
        for game_id in self.uow.watchlists.watched_game_ids():
            if self.should_stop():
                break
            try:
                _, updated, notifications = self.refresher.refresh(game_id)
                items = self.uow.watchlists.items_for_game(game_id)
                self.uow.commit()
            except (ProviderUnavailable, GameNotFound):
                self.uow.rollback()
                self.failed_games += 1
                logger.warning("Could not refresh watched game %s", game_id)
                continue
            refreshed += updated
            checked += len(items)
            matched += sum(threshold_met(item) for item in items)
            notifications_created += len(notifications)
        return RefreshResult(refreshed, checked, matched, notifications_created)
