from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.application.exceptions import Conflict
from app.domain import entities


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _game(row: models.Game) -> entities.Game:
    return entities.Game(
        id=row.id,
        title=row.title,
        steam_app_id=row.steam_app_id,
        thumbnail_url=row.thumbnail_url,
        source=row.source,
        cheapest_price=row.cheapest_price,
        last_refreshed_at=_utc(row.last_refreshed_at),
        offers=tuple(
            entities.ProviderOffer(
                deal_id=offer.deal_id,
                store_id=offer.store_id,
                price=offer.price,
                retail_price=offer.retail_price,
                savings=offer.savings,
            )
            for offer in sorted(row.offers, key=lambda offer: (offer.price, offer.store_id))
        ),
    )


def _item(row: models.WatchlistItem) -> entities.WatchlistItem:
    return entities.WatchlistItem(
        id=row.id,
        watchlist_id=row.watchlist_id,
        game_id=row.game_id,
        target_price=row.target_price,
        steam_only=row.steam_only,
        alert_active=row.alert_active,
        created_at=_utc(row.created_at),
        game=_game(row.game),
    )


def _notification(row: models.Notification) -> entities.Notification:
    return entities.Notification(
        id=row.id,
        watchlist_id=row.watchlist_id,
        item_id=row.item_id,
        game_id=row.game_id,
        game_title=row.game_title,
        target_price=row.target_price,
        observed_price=row.observed_price,
        created_at=_utc(row.created_at),
    )


class SqlAlchemyGameRepository:
    def __init__(self, session: Session):
        self.session = session

    def _get_row(self, game_id: str, lock: bool = False) -> models.Game | None:
        if lock and self.session.get_bind().dialect.name == "postgresql":
            # Serialize cold-cache creation too: row locks cannot lock a missing game.
            key = int.from_bytes(hashlib.blake2b(game_id.encode(), digest_size=8).digest(), "big")
            key &= (1 << 63) - 1
            self.session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
        statement = select(models.Game).where(models.Game.id == game_id)
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        return self.session.scalar(statement)

    def get(self, game_id: str, *, lock: bool = False) -> entities.Game | None:
        row = self._get_row(game_id, lock)
        return _game(row) if row else None

    def _metadata_row(self, game: entities.ProviderGame) -> models.Game:
        row = self._get_row(game.id, lock=True)
        if row is None:
            row = models.Game(id=game.id)
            self.session.add(row)
        elif row.source != game.source:
            row.offers.clear()
            row.last_refreshed_at = None
        row.title = game.title
        row.steam_app_id = game.steam_app_id
        row.thumbnail_url = game.thumbnail_url
        row.source = game.source
        row.cheapest_price = game.cheapest_price
        self.session.flush()
        return row

    def save_metadata(self, game: entities.ProviderGame) -> entities.Game:
        return _game(self._metadata_row(game))

    def save_observation(self, game: entities.ProviderGame, observed_at: datetime) -> entities.Game:
        row = self._metadata_row(game)
        row.offers.clear()
        # Flush deletes before inserting identical deal IDs under the unique constraint.
        self.session.flush()
        row.offers.extend(
            models.Offer(
                deal_id=offer.deal_id,
                store_id=offer.store_id,
                price=offer.price,
                retail_price=offer.retail_price,
                savings=offer.savings,
            )
            for offer in game.offers
        )
        row.last_refreshed_at = observed_at
        row.cheapest_price = min((offer.price for offer in game.offers), default=None)
        self.session.add_all(
            models.PriceSnapshot(
                game_id=game.id,
                store_id=offer.store_id,
                deal_id=offer.deal_id,
                price=offer.price,
                source=game.source,
                observed_at=observed_at,
            )
            for offer in game.offers
        )
        self.session.flush()
        return _game(row)

    def history(self, game_id: str, limit: int, offset: int) -> list[entities.PriceSnapshot]:
        rows = self.session.scalars(
            select(models.PriceSnapshot)
            .where(models.PriceSnapshot.game_id == game_id)
            .order_by(models.PriceSnapshot.observed_at.desc(), models.PriceSnapshot.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return [
            entities.PriceSnapshot(
                id=row.id,
                game_id=row.game_id,
                store_id=row.store_id,
                deal_id=row.deal_id,
                price=row.price,
                observed_at=_utc(row.observed_at),
                source=row.source,
            )
            for row in rows
        ]


class SqlAlchemyWatchlistRepository:
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _watchlist(row: models.Watchlist, include_items: bool = True) -> entities.Watchlist:
        return entities.Watchlist(
            id=row.id,
            name=row.name,
            created_at=_utc(row.created_at),
            items=tuple(_item(item) for item in sorted(row.items, key=lambda item: item.id))
            if include_items
            else (),
        )

    def create(self, name: str) -> entities.Watchlist:
        row = models.Watchlist(name=name)
        self.session.add(row)
        self.session.flush()
        return self._watchlist(row)

    def list(self) -> list[entities.Watchlist]:
        rows = self.session.scalars(select(models.Watchlist).order_by(models.Watchlist.id))
        return [self._watchlist(row, include_items=False) for row in rows]

    def get(self, watchlist_id: int) -> entities.Watchlist | None:
        row = self.session.scalar(
            select(models.Watchlist)
            .where(models.Watchlist.id == watchlist_id)
            .execution_options(populate_existing=True)
        )
        return self._watchlist(row) if row else None

    def delete(self, watchlist_id: int) -> None:
        self.session.execute(delete(models.Watchlist).where(models.Watchlist.id == watchlist_id))

    def find_item(
        self, watchlist_id: int, item_id: int, *, lock: bool = False
    ) -> entities.WatchlistItem | None:
        statement = select(models.WatchlistItem).where(
            models.WatchlistItem.watchlist_id == watchlist_id,
            models.WatchlistItem.id == item_id,
        )
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        row = self.session.scalar(statement)
        return _item(row) if row else None

    def find_game_item(self, watchlist_id: int, game_id: str) -> entities.WatchlistItem | None:
        row = self.session.scalar(
            select(models.WatchlistItem).where(
                models.WatchlistItem.watchlist_id == watchlist_id,
                models.WatchlistItem.game_id == game_id,
            )
        )
        return _item(row) if row else None

    def add_item(
        self, watchlist_id: int, game_id: str, target_price: Decimal, steam_only: bool
    ) -> entities.WatchlistItem:
        row = models.WatchlistItem(
            watchlist_id=watchlist_id,
            game_id=game_id,
            target_price=target_price,
            steam_only=steam_only,
        )
        self.session.add(row)
        self.session.flush()
        return _item(row)

    def update_item(
        self, item_id: int, target_price: Decimal | None, steam_only: bool | None
    ) -> entities.WatchlistItem:
        row = self.session.get(models.WatchlistItem, item_id)
        if target_price is not None:
            row.target_price = target_price
        if steam_only is not None:
            row.steam_only = steam_only
        self.session.flush()
        return _item(row)

    def delete_item(self, item_id: int) -> None:
        self.session.execute(delete(models.WatchlistItem).where(models.WatchlistItem.id == item_id))

    def items_for_game(self, game_id: str, *, lock: bool = False) -> list[entities.WatchlistItem]:
        statement = (
            select(models.WatchlistItem)
            .where(models.WatchlistItem.game_id == game_id)
            .order_by(models.WatchlistItem.id)
        )
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        return [_item(row) for row in self.session.scalars(statement)]

    def watched_game_ids(self) -> list[str]:
        return list(
            self.session.scalars(
                select(models.WatchlistItem.game_id)
                .distinct()
                .order_by(models.WatchlistItem.game_id)
            )
        )

    def set_alert_active(self, item_id: int, active: bool) -> None:
        row = self.session.get(models.WatchlistItem, item_id)
        row.alert_active = active
        self.session.flush()

    def add_notification(
        self, item: entities.WatchlistItem, observed_price: Decimal
    ) -> entities.Notification:
        row = models.Notification(
            watchlist_id=item.watchlist_id,
            item_id=item.id,
            game_id=item.game_id,
            game_title=item.game.title,
            target_price=item.target_price,
            observed_price=observed_price,
        )
        self.session.add(row)
        self.session.flush()
        return _notification(row)

    def notifications(
        self, watchlist_id: int, limit: int, offset: int
    ) -> list[entities.Notification]:
        return [
            _notification(row)
            for row in self.session.scalars(
                select(models.Notification)
                .where(models.Notification.watchlist_id == watchlist_id)
                .order_by(models.Notification.created_at.desc(), models.Notification.id.desc())
                .limit(limit)
                .offset(offset)
            )
        ]


class SqlAlchemyUnitOfWork:
    def __init__(self, session: Session):
        self.session = session
        self.games = SqlAlchemyGameRepository(session)
        self.watchlists = SqlAlchemyWatchlistRepository(session)

    def commit(self) -> None:
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise Conflict("Resource already exists or was modified concurrently") from exc

    def rollback(self) -> None:
        self.session.rollback()
