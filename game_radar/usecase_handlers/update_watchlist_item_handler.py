"""Хендлер UpdateWatchlistItemUseCase."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.errors import watchlist_item_not_found
from game_radar.mapping.watchlist_mapper import map_item_response
from game_radar.repositories.database.watchlist_item_repository import WatchlistItemRepository
from game_radar.schemas.game_radar_api import ItemResponse
from game_radar.services.game_refresh_service import GameRefreshService
from game_radar.services.price_alert_service import PriceAlertService
from game_radar.usecases.watchlists import UpdateWatchlistItemUseCase


class UpdateWatchlistItemHandler:
    """Меняет порог и/или Steam-фильтр и пересчитывает достижение порога."""

    def __init__(
        self,
        item_repo: WatchlistItemRepository,
        refresh_service: GameRefreshService,
        alert_service: PriceAlertService,
    ) -> None:
        self.item_repo = item_repo
        self.refresh_service = refresh_service
        self.alert_service = alert_service

    async def handle(
        self, usecase: UpdateWatchlistItemUseCase, session: AsyncSession
    ) -> ItemResponse:
        async with session.begin():
            item = await self.item_repo.get(session, usecase.watchlist_id, usecase.item_id)
            if item is None:
                raise watchlist_item_not_found()

            # Сначала блокировка игры (внутри refresh), затем позиции — как в обновлении цен.
            await self.refresh_service.refresh(session, item.game_id)
            item = await self.item_repo.get(
                session, usecase.watchlist_id, usecase.item_id, for_update=True
            )
            if item is None:
                raise watchlist_item_not_found()

            await self.item_repo.update(session, item.id, usecase.target_price, usecase.steam_only)
            item = await self.item_repo.get(session, usecase.watchlist_id, item.id)
            await self.alert_service.evaluate(session, item)
            item = await self.item_repo.get(session, usecase.watchlist_id, item.id)

        return map_item_response(item)
