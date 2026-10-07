"""Хендлер DeleteWatchlistItemUseCase."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.errors import watchlist_item_not_found
from game_radar.repositories.database.watchlist_item_repository import WatchlistItemRepository
from game_radar.usecases.watchlists import DeleteWatchlistItemUseCase


class DeleteWatchlistItemHandler:
    """Убирает игру из списка."""

    def __init__(self, item_repo: WatchlistItemRepository) -> None:
        self.item_repo = item_repo

    async def handle(self, usecase: DeleteWatchlistItemUseCase, session: AsyncSession) -> None:
        async with session.begin():
            item = await self.item_repo.get(
                session, usecase.watchlist_id, usecase.item_id, for_update=True
            )
            if item is None:
                raise watchlist_item_not_found()
            await self.item_repo.delete(session, usecase.item_id)
