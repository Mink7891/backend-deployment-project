"""UseCase-датаклассы для игр и цен."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchGamesUseCase:
    """GET /games/search — поиск игр у провайдера с сохранением в каталог."""

    query: str
    limit: int = 20


@dataclass(frozen=True)
class GetGameUseCase:
    """GET /games/{game_id} — текущие предложения игры с учётом кеша."""

    game_id: str


@dataclass(frozen=True)
class GetPriceHistoryUseCase:
    """GET /games/{game_id}/history — история наблюдавшихся цен."""

    game_id: str
    limit: int = 100
    offset: int = 0
