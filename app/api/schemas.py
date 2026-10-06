from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

GameId = Annotated[str, StringConstraints(pattern=r"^[0-9]{1,32}$")]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class GameCard(ResponseModel):
    id: str
    title: str
    steam_app_id: str | None
    thumbnail_url: str | None
    cheapest_price: Decimal | None
    currency: Literal["USD"] = "USD"
    source: str


class OfferResponse(ResponseModel):
    deal_id: str
    store_id: str
    store_name: str
    price: Decimal
    retail_price: Decimal
    savings: Decimal
    deal_url: str | None = None


class GameDetails(GameCard):
    last_refreshed_at: datetime | None
    offers: list[OfferResponse]
    best_price: Decimal | None


class SnapshotResponse(ResponseModel):
    id: int
    game_id: str
    store_id: str
    deal_id: str
    price: Decimal
    observed_at: datetime
    source: str


class CreateWatchlistRequest(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class AddItemRequest(BaseModel):
    game_id: GameId
    target_price: Money
    steam_only: bool = True


class UpdateItemRequest(BaseModel):
    target_price: Money | None = None
    steam_only: bool | None = None

    @model_validator(mode="after")
    def require_patch_fields(self):
        if not self.model_fields_set:
            raise ValueError("Provide target_price or steam_only")
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Patch fields cannot be null")
        return self


class WatchlistResponse(ResponseModel):
    id: int
    name: str
    created_at: datetime


class ItemResponse(ResponseModel):
    id: int
    game_id: str
    target_price: Decimal
    steam_only: bool
    created_at: datetime
    game: GameCard
    current_price: Decimal | None
    threshold_met: bool


class WatchlistDetails(WatchlistResponse):
    items: list[ItemResponse]


class SummaryResponse(ResponseModel):
    watchlist_id: int
    total_items: int
    priced_items: int
    matched_count: int
    current_total: Decimal
    currency: Literal["USD"]
    source: str


class NotificationResponse(ResponseModel):
    id: int
    watchlist_id: int
    item_id: int | None
    game_id: str
    game_title: str
    target_price: Decimal
    observed_price: Decimal
    created_at: datetime


class RefreshResponse(ResponseModel):
    watchlist_id: int
    refreshed_games: int
    checked_items: int
    matched_count: int
    notifications_created: int
