"""Хендлер RefreshWatchlistUseCase."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.errors import watchlist_not_found
from game_radar.repositories.database.watchlist_repository import WatchlistRepository
from game_radar.schemas.game_radar_api import RefreshResponse
from game_radar.services.game_refresh_service import GameRefreshService
from game_radar.services.pricing import PricingActions
from game_radar.usecases.refresh import RefreshWatchlistUseCase


class RefreshWatchlistHandler:
    """Обновляет цены всех игр списка с учётом кеша.

    Повторная запись в журнал не создаётся, пока цена не выйдет из порога и не вернётся.
    """

    def __init__(
        self, watchlist_repo: WatchlistRepository, refresh_service: GameRefreshService
    ) -> None:
        self.watchlist_repo = watchlist_repo
        self.refresh_service = refresh_service

    async def handle(
        self, usecase: RefreshWatchlistUseCase, session: AsyncSession
    ) -> RefreshResponse:
        async with session.begin():
            watchlist = await self.watchlist_repo.get(session, usecase.watchlist_id)
            if watchlist is None:
                raise watchlist_not_found()

            refreshed = notifications_created = 0
            for game_id in sorted({item.game_id for item in watchlist.items}):
                result = await self.refresh_service.refresh(session, game_id)
                refreshed += result.refreshed
                notifications_created += sum(
                    notification.watchlist_id == usecase.watchlist_id
                    for notification in result.notifications
                )
            watchlist = await self.watchlist_repo.get(session, usecase.watchlist_id)

        return RefreshResponse(
            watchlist_id=usecase.watchlist_id,
            refreshed_games=refreshed,
            checked_items=len(watchlist.items),
            matched_count=sum(PricingActions.threshold_met(item) for item in watchlist.items),
            notifications_created=notifications_created,
        )
