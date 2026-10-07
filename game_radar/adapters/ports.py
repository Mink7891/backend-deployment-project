"""Общий интерфейс источников цен: CheapShark API и офлайн-mock."""

from __future__ import annotations

from typing import Protocol

from game_radar.schemas.price_provider import ProviderGame


class PriceApi(Protocol):
    source: str

    async def search(self, query: str, limit: int = 20) -> list[ProviderGame]: ...

    async def get_game(self, game_id: str) -> ProviderGame: ...
