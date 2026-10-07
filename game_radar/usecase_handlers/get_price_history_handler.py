"""Хендлер GetPriceHistoryUseCase."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.errors import game_not_in_catalog
from game_radar.mapping.game_mapper import map_snapshot_response
from game_radar.repositories.database.game_repository import GameRepository
from game_radar.repositories.database.price_snapshot_repository import PriceSnapshotRepository
from game_radar.schemas.game_radar_api import SnapshotResponse
from game_radar.usecases.games import GetPriceHistoryUseCase


class GetPriceHistoryHandler:
    """Возвращает собственные наблюдения цен игры, новые первыми."""

    def __init__(self, game_repo: GameRepository, snapshot_repo: PriceSnapshotRepository) -> None:
        self.game_repo = game_repo
        self.snapshot_repo = snapshot_repo

    async def handle(
        self, usecase: GetPriceHistoryUseCase, session: AsyncSession
    ) -> list[SnapshotResponse]:
        async with session.begin():
            if await self.game_repo.get(session, usecase.game_id) is None:
                raise game_not_in_catalog()
            snapshots = await self.snapshot_repo.get_by_game(
                session, usecase.game_id, usecase.limit, usecase.offset
            )

        return [map_snapshot_response(snapshot) for snapshot in snapshots]
