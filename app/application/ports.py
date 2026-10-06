from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol

from app.domain.entities import (
    Game,
    Notification,
    PriceSnapshot,
    ProviderGame,
    Watchlist,
    WatchlistItem,
)


class PriceProvider(Protocol):
    source: str

    def search(self, query: str, limit: int = 20) -> list[ProviderGame]: ...

    def get_game(self, game_id: str) -> ProviderGame: ...


class GameRepository(Protocol):
    def get(self, game_id: str, *, lock: bool = False) -> Game | None: ...

    def save_metadata(self, game: ProviderGame) -> Game: ...

    def save_observation(self, game: ProviderGame, observed_at: datetime) -> Game: ...

    def history(self, game_id: str, limit: int, offset: int) -> list[PriceSnapshot]: ...


class WatchlistRepository(Protocol):
    def create(self, name: str) -> Watchlist: ...

    def list(self) -> list[Watchlist]: ...

    def get(self, watchlist_id: int) -> Watchlist | None: ...

    def delete(self, watchlist_id: int) -> None: ...

    def find_item(
        self, watchlist_id: int, item_id: int, *, lock: bool = False
    ) -> WatchlistItem | None: ...

    def find_game_item(self, watchlist_id: int, game_id: str) -> WatchlistItem | None: ...

    def add_item(
        self, watchlist_id: int, game_id: str, target_price: Decimal, steam_only: bool
    ) -> WatchlistItem: ...

    def update_item(
        self, item_id: int, target_price: Decimal | None, steam_only: bool | None
    ) -> WatchlistItem: ...

    def delete_item(self, item_id: int) -> None: ...

    def items_for_game(self, game_id: str, *, lock: bool = False) -> list[WatchlistItem]: ...

    def watched_game_ids(self) -> list[str]: ...

    def set_alert_active(self, item_id: int, active: bool) -> None: ...

    def add_notification(self, item: WatchlistItem, observed_price: Decimal) -> Notification: ...

    def notifications(self, watchlist_id: int, limit: int, offset: int) -> list[Notification]: ...


class UnitOfWork(Protocol):
    games: GameRepository
    watchlists: WatchlistRepository

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
