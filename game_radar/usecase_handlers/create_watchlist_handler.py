"""Хендлер CreateWatchlistUseCase."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.mapping.watchlist_mapper import map_watchlist_response
from game_radar.repositories.database.watchlist_repository import WatchlistRepository
from game_radar.schemas.game_radar_api import WatchlistResponse
from game_radar.usecases.watchlists import CreateWatchlistUseCase


class CreateWatchlistHandler:
    """Создаёт пустой список наблюдения."""

    def __init__(self, watchlist_repo: WatchlistRepository) -> None:
        self.watchlist_repo = watchlist_repo

    async def handle(
        self, usecase: CreateWatchlistUseCase, session: AsyncSession
    ) -> WatchlistResponse:
        async with session.begin():
            watchlist = await self.watchlist_repo.create(session, usecase.name)

        return map_watchlist_response(watchlist)
