from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from app.domain import entities

Record = Mapping[str, Any]


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def game_view(row: Record, offers: Iterable[Record]) -> entities.Game:
    return entities.Game(
        id=row["id"],
        title=row["title"],
        steam_app_id=row["steam_app_id"],
        thumbnail_url=row["thumbnail_url"],
        source=row["source"],
        cheapest_price=row["cheapest_price"],
        last_refreshed_at=utc(row["last_refreshed_at"]) if row["last_refreshed_at"] else None,
        offers=tuple(
            entities.ProviderOffer(
                deal_id=offer["deal_id"],
                store_id=offer["store_id"],
                price=offer["price"],
                retail_price=offer["retail_price"],
                savings=offer["savings"],
            )
            for offer in offers
        ),
    )


def item_view(row: Record, game: entities.Game) -> entities.WatchlistItem:
    return entities.WatchlistItem(
        id=row["id"],
        watchlist_id=row["watchlist_id"],
        game_id=row["game_id"],
        target_price=row["target_price"],
        steam_only=row["steam_only"],
        alert_active=row["alert_active"],
        created_at=utc(row["created_at"]),
        game=game,
    )


def notification_view(row: Record) -> entities.Notification:
    return entities.Notification(
        id=row["id"],
        watchlist_id=row["watchlist_id"],
        item_id=row["item_id"],
        game_id=row["game_id"],
        game_title=row["game_title"],
        target_price=row["target_price"],
        observed_price=row["observed_price"],
        created_at=utc(row["created_at"]),
    )
