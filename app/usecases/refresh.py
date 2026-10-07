from dataclasses import dataclass


@dataclass(frozen=True)
class RefreshWatchlistUseCase:
    watchlist_id: int


@dataclass(frozen=True)
class RefreshAllWatchedGamesUseCase:
    pass
