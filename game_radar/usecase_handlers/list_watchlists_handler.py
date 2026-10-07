"""Хендлер ListWatchlistsUseCase."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.mapping.watchlist_mapper import map_watchlist_response
from game_radar.repositories.database.watchlist_repository import WatchlistRepository
from game_radar.schemas.game_radar_api import WatchlistResponse
from game_radar.usecases.watchlists import ListWatchlistsUseCase


class ListWatchlistsHandler:
    """Возвращает все списки наблюдения."""

    def __init__(self, watchlist_repo: WatchlistRepository) -> None:
        self.watchlist_repo = watchlist_repo

    async def handle(
        self, usecase: ListWatchlistsUseCase, session: AsyncSession
    ) -> list[WatchlistResponse]:
        async with session.begin():
            watchlists = await self.watchlist_repo.get_all(session)

        return [map_watchlist_response(watchlist) for watchlist in watchlists]
