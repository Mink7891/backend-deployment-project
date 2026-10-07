"""Хендлер GetGameUseCase."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.mapping.game_mapper import map_game_details
from game_radar.schemas.game_radar_api import GameDetails
from game_radar.services.game_refresh_service import GameRefreshService
from game_radar.usecases.games import GetGameUseCase


class GetGameHandler:
    """Возвращает предложения игры: из кеша или свежие от провайдера."""

    def __init__(self, refresh_service: GameRefreshService) -> None:
        self.refresh_service = refresh_service

    async def handle(self, usecase: GetGameUseCase, session: AsyncSession) -> GameDetails:
        async with session.begin():
            result = await self.refresh_service.refresh(session, usecase.game_id)

        return map_game_details(result.game)
