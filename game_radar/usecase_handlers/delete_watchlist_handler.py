"""Хендлер DeleteWatchlistUseCase."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.errors import watchlist_not_found
from game_radar.repositories.database.watchlist_repository import WatchlistRepository
from game_radar.usecases.watchlists import DeleteWatchlistUseCase


class DeleteWatchlistHandler:
    """Удаляет список вместе с его позициями и журналом."""

    def __init__(self, watchlist_repo: WatchlistRepository) -> None:
        self.watchlist_repo = watchlist_repo

    async def handle(self, usecase: DeleteWatchlistUseCase, session: AsyncSession) -> None:
        async with session.begin():
            if await self.watchlist_repo.get(session, usecase.watchlist_id) is None:
                raise watchlist_not_found()
            await self.watchlist_repo.delete(session, usecase.watchlist_id)
