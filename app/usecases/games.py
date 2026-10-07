from dataclasses import dataclass


@dataclass(frozen=True)
class SearchGamesUseCase:
    query: str
    limit: int = 20


@dataclass(frozen=True)
class GetGameUseCase:
    game_id: str


@dataclass(frozen=True)
class GetPriceHistoryUseCase:
    game_id: str
    limit: int = 100
    offset: int = 0
