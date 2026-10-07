"""Хендлер GetWatchlistUseCase."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.errors import watchlist_not_found
from game_radar.mapping.watchlist_mapper import map_watchlist_details
from game_radar.repositories.database.watchlist_repository import WatchlistRepository
from game_radar.schemas.game_radar_api import WatchlistDetails
from game_radar.usecases.watchlists import GetWatchlistUseCase


class GetWatchlistHandler:
    """Возвращает список с играми и их текущими ценами."""

    def __init__(self, watchlist_repo: WatchlistRepository) -> None:
        self.watchlist_repo = watchlist_repo

    async def handle(self, usecase: GetWatchlistUseCase, session: AsyncSession) -> WatchlistDetails:
        async with session.begin():
            watchlist = await self.watchlist_repo.get(session, usecase.watchlist_id)
            if watchlist is None:
                raise watchlist_not_found()

        return map_watchlist_details(watchlist)
