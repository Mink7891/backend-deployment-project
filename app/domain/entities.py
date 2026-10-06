from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class ProviderOffer:
    deal_id: str
    store_id: str
    price: Decimal
    retail_price: Decimal
    savings: Decimal


@dataclass(frozen=True)
class ProviderGame:
    id: str
    title: str
    steam_app_id: str | None
    thumbnail_url: str | None
    offers: tuple[ProviderOffer, ...]
    source: str
    cheapest_price: Decimal | None = None


@dataclass(frozen=True)
class Game(ProviderGame):
    last_refreshed_at: datetime | None = None


@dataclass(frozen=True)
class PriceSnapshot:
    id: int
    game_id: str
    store_id: str
    deal_id: str
    price: Decimal
    observed_at: datetime
    source: str


@dataclass(frozen=True)
class WatchlistItem:
    id: int
    watchlist_id: int
    game_id: str
    target_price: Decimal
    steam_only: bool
    alert_active: bool
    created_at: datetime
    game: Game


@dataclass(frozen=True)
class Watchlist:
    id: int
    name: str
    created_at: datetime
    items: tuple[WatchlistItem, ...] = ()


@dataclass(frozen=True)
class Notification:
    id: int
    watchlist_id: int
    item_id: int | None
    game_id: str
    game_title: str
    target_price: Decimal
    observed_price: Decimal
    created_at: datetime


@dataclass(frozen=True)
class WatchlistSummary:
    watchlist_id: int
    total_items: int
    priced_items: int
    matched_count: int
    current_total: Decimal
    currency: str
    source: str


@dataclass(frozen=True)
class RefreshResult:
    refreshed_games: int
    checked_items: int
    matched_count: int
    notifications_created: int
    watchlist_id: int | None = None
