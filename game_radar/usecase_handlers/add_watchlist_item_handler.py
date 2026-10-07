"""Хендлер AddWatchlistItemUseCase."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.errors import game_already_in_watchlist, watchlist_not_found
from game_radar.mapping.watchlist_mapper import map_item_response
from game_radar.repositories.database.watchlist_item_repository import WatchlistItemRepository
from game_radar.repositories.database.watchlist_repository import WatchlistRepository
from game_radar.schemas.game_radar_api import ItemResponse
from game_radar.services.game_refresh_service import GameRefreshService
from game_radar.services.price_alert_service import PriceAlertService
from game_radar.usecases.watchlists import AddWatchlistItemUseCase


class AddWatchlistItemHandler:
    """Добавляет игру в список, получает её цены и сразу проверяет порог."""

    def __init__(
        self,
        watchlist_repo: WatchlistRepository,
        item_repo: WatchlistItemRepository,
        refresh_service: GameRefreshService,
        alert_service: PriceAlertService,
    ) -> None:
        self.watchlist_repo = watchlist_repo
        self.item_repo = item_repo
        self.refresh_service = refresh_service
        self.alert_service = alert_service

    async def handle(self, usecase: AddWatchlistItemUseCase, session: AsyncSession) -> ItemResponse:
        async with session.begin():
            # Проверяем локальное состояние до обращения к внешнему API.
            if await self.watchlist_repo.get(session, usecase.watchlist_id) is None:
                raise watchlist_not_found()
            if await self.item_repo.get_by_game(session, usecase.watchlist_id, usecase.game_id):
                raise game_already_in_watchlist()

            await self.refresh_service.refresh(session, usecase.game_id)
            item = await self.item_repo.create(
                session,
                usecase.watchlist_id,
                usecase.game_id,
                usecase.target_price,
                usecase.steam_only,
            )
            await self.alert_service.evaluate(session, item)
            item = await self.item_repo.get(session, usecase.watchlist_id, item.id)

        return map_item_response(item)
