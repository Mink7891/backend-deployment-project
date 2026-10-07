from dataclasses import dataclass

from app.schemas import AddItemRequest, CreateWatchlistRequest, UpdateItemRequest


@dataclass(frozen=True)
class CreateWatchlistUseCase:
    request: CreateWatchlistRequest


@dataclass(frozen=True)
class ListWatchlistsUseCase:
    pass


@dataclass(frozen=True)
class GetWatchlistUseCase:
    watchlist_id: int


@dataclass(frozen=True)
class DeleteWatchlistUseCase:
    watchlist_id: int


@dataclass(frozen=True)
class AddWatchlistItemUseCase:
    watchlist_id: int
    request: AddItemRequest


@dataclass(frozen=True)
class UpdateWatchlistItemUseCase:
    watchlist_id: int
    item_id: int
    request: UpdateItemRequest


@dataclass(frozen=True)
class DeleteWatchlistItemUseCase:
    watchlist_id: int
    item_id: int


@dataclass(frozen=True)
class GetWatchlistSummaryUseCase:
    watchlist_id: int


@dataclass(frozen=True)
class GetNotificationsUseCase:
    watchlist_id: int
    limit: int = 100
    offset: int = 0
