"""Маппинг списков наблюдения, их позиций и журнала в ответы API."""

from __future__ import annotations

from decimal import Decimal

from game_radar.config import settings
from game_radar.database.models import NotificationModel, WatchlistItemModel, WatchlistModel
from game_radar.mapping.game_mapper import map_game_card
from game_radar.schemas.game_radar_api import (
    ItemResponse,
    NotificationResponse,
    SummaryResponse,
    WatchlistDetails,
    WatchlistResponse,
)
from game_radar.services.pricing import PricingActions


def map_watchlist_response(watchlist: WatchlistModel) -> WatchlistResponse:
    return WatchlistResponse.model_validate(watchlist)


def map_item_response(item: WatchlistItemModel) -> ItemResponse:
    return ItemResponse(
        id=item.id,
        game_id=item.game_id,
        target_price=item.target_price,
        steam_only=item.steam_only,
        created_at=item.created_at,
        game=map_game_card(item.game),
        current_price=PricingActions.best_price(item.game, item.steam_only),
        threshold_met=PricingActions.threshold_met(item),
    )


def map_watchlist_details(watchlist: WatchlistModel) -> WatchlistDetails:
    return WatchlistDetails(
        id=watchlist.id,
        name=watchlist.name,
        created_at=watchlist.created_at,
        items=[map_item_response(item) for item in watchlist.items],
    )


def map_summary_response(watchlist: WatchlistModel, configured_source: str) -> SummaryResponse:
    prices = [PricingActions.best_price(item.game, item.steam_only) for item in watchlist.items]
    available = [price for price in prices if price is not None]
    return SummaryResponse(
        watchlist_id=watchlist.id,
        total_items=len(watchlist.items),
        priced_items=len(available),
        matched_count=sum(PricingActions.threshold_met(item) for item in watchlist.items),
        current_total=sum(available, Decimal("0.00")),
        currency=settings.CURRENCY,
        source=PricingActions.summary_source(watchlist, configured_source),
    )


def map_notification_response(notification: NotificationModel) -> NotificationResponse:
    return NotificationResponse.model_validate(notification)
