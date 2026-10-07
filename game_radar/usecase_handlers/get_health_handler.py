"""Хендлер GetHealthUseCase."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.repositories.database.health_repository import HealthRepository
from game_radar.schemas.game_radar_api import HealthResponse
from game_radar.usecases.health import GetHealthUseCase


class GetHealthHandler:
    """Проверяет подключение к БД и наличие схемы."""

    def __init__(self, health_repo: HealthRepository, price_source: str) -> None:
        self.health_repo = health_repo
        self.price_source = price_source

    async def handle(self, usecase: GetHealthUseCase, session: AsyncSession) -> HealthResponse:
        async with session.begin():
            await self.health_repo.check(session)

        return HealthResponse(
            status="ok",
            database="ready",
            price_source=self.price_source,
            mock_prices_are_fictional=self.price_source == "mock",
        )
