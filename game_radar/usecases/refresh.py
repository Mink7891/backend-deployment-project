"""UseCase-датаклассы обновления цен."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RefreshWatchlistUseCase:
    """POST /watchlists/{watchlist_id}/refresh — обновить цены игр списка."""

    watchlist_id: int


@dataclass(frozen=True)
class RefreshAllWatchedGamesUseCase:
    """Фоновый worker — обновить цены всех отслеживаемых игр."""

    pass
