import logging
from collections.abc import Callable

from app import usecases
from app.domain.pricing import threshold_met
from app.exceptions import GameNotFound, ProviderUnavailable
from app.schemas import RefreshBatchResponse
from app.usecase_handlers.base import DatabaseHandler

logger = logging.getLogger("gameradar.worker")


class RefreshAllWatchedGamesHandler(DatabaseHandler):
    def __init__(self, *args, should_stop: Callable[[], bool] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.should_stop = should_stop or (lambda: False)
        self.failed_games = 0

    def handle(self, usecase: usecases.RefreshAllWatchedGamesUseCase) -> RefreshBatchResponse:
        with self.transaction() as repositories:
            game_ids = repositories.watchlists.watched_game_ids()
        refreshed = checked = matched = notifications_created = 0
        self.failed_games = 0
        for game_id in game_ids:
            if self.should_stop():
                break
            try:
                # A provider failure rolls back this game's changes, not earlier games.
                with self.transaction() as repositories:
                    _, updated, notifications = self.refresh_service.refresh(repositories, game_id)
                    items = repositories.watchlists.items_for_game(game_id)
            except (ProviderUnavailable, GameNotFound):
                self.failed_games += 1
                logger.warning("Could not refresh watched game %s", game_id)
                continue
            refreshed += updated
            checked += len(items)
            matched += sum(threshold_met(item) for item in items)
            notifications_created += len(notifications)
        return RefreshBatchResponse(
            refreshed_games=refreshed,
            checked_items=checked,
            matched_count=matched,
            notifications_created=notifications_created,
            failed_games=self.failed_games,
        )
