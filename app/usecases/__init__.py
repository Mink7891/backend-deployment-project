"""Immutable command/query contracts: no execution logic or dependencies."""

from app.usecases.games import GetGameUseCase, GetPriceHistoryUseCase, SearchGamesUseCase
from app.usecases.refresh import RefreshAllWatchedGamesUseCase, RefreshWatchlistUseCase
from app.usecases.watchlists import (
    AddWatchlistItemUseCase,
    CreateWatchlistUseCase,
    DeleteWatchlistItemUseCase,
    DeleteWatchlistUseCase,
    GetNotificationsUseCase,
    GetWatchlistSummaryUseCase,
    GetWatchlistUseCase,
    ListWatchlistsUseCase,
    UpdateWatchlistItemUseCase,
)

__all__ = [
    "AddWatchlistItemUseCase",
    "CreateWatchlistUseCase",
    "DeleteWatchlistUseCase",
    "DeleteWatchlistItemUseCase",
    "GetGameUseCase",
    "GetNotificationsUseCase",
    "GetPriceHistoryUseCase",
    "GetWatchlistUseCase",
    "GetWatchlistSummaryUseCase",
    "ListWatchlistsUseCase",
    "RefreshAllWatchedGamesUseCase",
    "RefreshWatchlistUseCase",
    "SearchGamesUseCase",
    "UpdateWatchlistItemUseCase",
]
