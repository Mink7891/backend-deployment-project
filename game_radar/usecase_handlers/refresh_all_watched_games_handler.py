"""Хендлер RefreshAllWatchedGamesUseCase."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.errors import ServiceError
from game_radar.repositories.database.watchlist_item_repository import WatchlistItemRepository
from game_radar.schemas.internal import RefreshBatchResponse
from game_radar.services.game_refresh_service import GameRefreshService
from game_radar.services.pricing import PricingActions
from game_radar.usecases.refresh import RefreshAllWatchedGamesUseCase

logger = logging.getLogger(__name__)


class RefreshAllWatchedGamesHandler:
    """Обновляет цены всех игр из всех списков; каждая игра — отдельная транзакция."""

    def __init__(
        self, item_repo: WatchlistItemRepository, refresh_service: GameRefreshService
    ) -> None:
        self.item_repo = item_repo
        self.refresh_service = refresh_service

    async def handle(
        self, usecase: RefreshAllWatchedGamesUseCase, session: AsyncSession
    ) -> RefreshBatchResponse:
        async with session.begin():
            game_ids = await self.item_repo.get_watched_game_ids(session)

        refreshed = checked = matched = notifications_created = failed = 0
        for game_id in game_ids:
            try:
                # Отказ провайдера откатывает только изменения этой игры.
                async with session.begin():
                    result = await self.refresh_service.refresh(session, game_id)
                    items = await self.item_repo.get_for_game(session, game_id)
            except ServiceError as exc:
                failed += 1
                logger.warning(
                    "Could not refresh watched game",
                    extra={"extra_fields": {"game_id": game_id, "error_code": exc.code}},
                )
                continue
            refreshed += result.refreshed
            checked += len(items)
            matched += sum(PricingActions.threshold_met(item) for item in items)
            notifications_created += len(result.notifications)

        return RefreshBatchResponse(
            refreshed_games=refreshed,
            checked_items=checked,
            matched_count=matched,
            notifications_created=notifications_created,
            failed_games=failed,
        )
