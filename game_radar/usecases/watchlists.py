"""UseCase-датаклассы для списков наблюдения."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CreateWatchlistUseCase:
    """POST /watchlists — создать список."""

    name: str


@dataclass(frozen=True)
class ListWatchlistsUseCase:
    """GET /watchlists — все списки."""

    pass


@dataclass(frozen=True)
class GetWatchlistUseCase:
    """GET /watchlists/{watchlist_id} — список с играми и текущими ценами."""

    watchlist_id: int


@dataclass(frozen=True)
class DeleteWatchlistUseCase:
    """DELETE /watchlists/{watchlist_id} — удалить список."""

    watchlist_id: int


@dataclass(frozen=True)
class AddWatchlistItemUseCase:
    """POST /watchlists/{watchlist_id}/items — добавить игру с желаемой ценой."""

    watchlist_id: int
    game_id: str
    target_price: Decimal
    steam_only: bool = False


@dataclass(frozen=True)
class UpdateWatchlistItemUseCase:
    """PATCH /watchlists/{watchlist_id}/items/{item_id} — изменить порог/Steam-фильтр."""

    watchlist_id: int
    item_id: int
    target_price: Decimal | None = None
    steam_only: bool | None = None


@dataclass(frozen=True)
class DeleteWatchlistItemUseCase:
    """DELETE /watchlists/{watchlist_id}/items/{item_id} — убрать игру из списка."""

    watchlist_id: int
    item_id: int


@dataclass(frozen=True)
class GetWatchlistSummaryUseCase:
    """GET /watchlists/{watchlist_id}/summary — сводка стоимости списка."""

    watchlist_id: int


@dataclass(frozen=True)
class GetNotificationsUseCase:
    """GET /watchlists/{watchlist_id}/notifications — журнал срабатываний."""

    watchlist_id: int
    limit: int = 100
    offset: int = 0
