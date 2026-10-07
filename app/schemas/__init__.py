"""Stable exports for schemas generated from the approved OpenAPI contract."""

from app.schemas.base import DTO
from app.schemas.game_radar_api import (
    AddItemRequest,
    CreateWatchlistRequest,
    GameCard,
    GameDetails,
    HealthResponse,
    ItemResponse,
    NotificationResponse,
    OfferResponse,
    RefreshResponse,
    SnapshotResponse,
    SummaryResponse,
    UpdateItemRequest,
    WatchlistDetails,
    WatchlistResponse,
)
from app.schemas.internal import RefreshBatchResponse
from app.schemas.types import GameId, Money

__all__ = [
    "DTO",
    "GameId",
    "Money",
    "AddItemRequest",
    "CreateWatchlistRequest",
    "GameCard",
    "GameDetails",
    "HealthResponse",
    "ItemResponse",
    "NotificationResponse",
    "OfferResponse",
    "RefreshResponse",
    "RefreshBatchResponse",
    "SnapshotResponse",
    "SummaryResponse",
    "UpdateItemRequest",
    "WatchlistDetails",
    "WatchlistResponse",
]
