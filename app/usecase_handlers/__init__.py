"""Business logic and transaction ownership for use case contracts."""

from app.usecase_handlers.games import GetGameHandler, GetPriceHistoryHandler, SearchGamesHandler
from app.usecase_handlers.refresh import RefreshAllWatchedGamesHandler, RefreshWatchlistHandler
from app.usecase_handlers.watchlists import (
    AddWatchlistItemHandler,
    CreateWatchlistHandler,
    DeleteWatchlistHandler,
    DeleteWatchlistItemHandler,
    GetNotificationsHandler,
    GetWatchlistHandler,
    GetWatchlistSummaryHandler,
    ListWatchlistsHandler,
    UpdateWatchlistItemHandler,
)

__all__ = [
    "AddWatchlistItemHandler",
    "CreateWatchlistHandler",
    "DeleteWatchlistHandler",
    "DeleteWatchlistItemHandler",
    "GetGameHandler",
    "GetNotificationsHandler",
    "GetPriceHistoryHandler",
    "GetWatchlistHandler",
    "GetWatchlistSummaryHandler",
    "ListWatchlistsHandler",
    "RefreshAllWatchedGamesHandler",
    "RefreshWatchlistHandler",
    "SearchGamesHandler",
    "UpdateWatchlistItemHandler",
]
