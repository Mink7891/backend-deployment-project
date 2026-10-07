"""Хендлер SearchGamesUseCase."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.adapters.ports import PriceApi
from game_radar.mapping.game_mapper import map_game_card
from game_radar.repositories.database.game_repository import GameRepository
from game_radar.schemas.game_radar_api import GameCard
from game_radar.usecases.games import SearchGamesUseCase


class SearchGamesHandler:
    """Ищет игры у провайдера и сохраняет их метаданные в локальный каталог."""

    def __init__(self, price_api: PriceApi, game_repo: GameRepository) -> None:
        self.price_api = price_api
        self.game_repo = game_repo

    async def handle(self, usecase: SearchGamesUseCase, session: AsyncSession) -> list[GameCard]:
        found = await self.price_api.search(usecase.query, usecase.limit)

        async with session.begin():
            # Сохраняем в порядке ID — так же, как refresh, чтобы не было взаимных блокировок.
            saved = {}
            for game in sorted(found, key=lambda game: game.id):
                saved[game.id] = await self.game_repo.save_metadata(session, game)

        return [map_game_card(saved[game.id]) for game in found]
