"""Хендлер GetWatchlistSummaryUseCase."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.errors import watchlist_not_found
from game_radar.mapping.watchlist_mapper import map_summary_response
from game_radar.repositories.database.watchlist_repository import WatchlistRepository
from game_radar.schemas.game_radar_api import SummaryResponse
from game_radar.usecases.watchlists import GetWatchlistSummaryUseCase


class GetWatchlistSummaryHandler:
    """Считает сумму доступных цен и число игр с достигнутым порогом.

    Использует сохранённые цены и не обращается к провайдеру.
    """

    def __init__(self, watchlist_repo: WatchlistRepository, price_source: str) -> None:
        self.watchlist_repo = watchlist_repo
        self.price_source = price_source

    async def handle(
        self, usecase: GetWatchlistSummaryUseCase, session: AsyncSession
    ) -> SummaryResponse:
        async with session.begin():
            watchlist = await self.watchlist_repo.get(session, usecase.watchlist_id)
            if watchlist is None:
                raise watchlist_not_found()

        return map_summary_response(watchlist, self.price_source)
