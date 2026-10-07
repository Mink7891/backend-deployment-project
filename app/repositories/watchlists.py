from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Connection

from app.domain import entities
from app.models import notifications, watchlist_items, watchlists
from app.repositories.games import GamesRepository
from app.repositories.mapping import Record, item_view, notification_view, utc


class WatchlistsRepository:
    def __init__(self, connection: Connection):
        self.connection = connection
        self.games = GamesRepository(connection)

    def _items(self, records: Iterable[Record]) -> list[entities.WatchlistItem]:
        records = list(records)
        games = self.games.get_many(row["game_id"] for row in records)
        return [item_view(row, games[row["game_id"]]) for row in records]

    @staticmethod
    def _watchlist(row: Record, items: Iterable[entities.WatchlistItem] = ()) -> entities.Watchlist:
        return entities.Watchlist(
            id=row["id"], name=row["name"], created_at=utc(row["created_at"]), items=tuple(items)
        )

    def create(self, name: str) -> entities.Watchlist:
        row = (
            self.connection.execute(
                insert(watchlists)
                .values(name=name, created_at=datetime.now(UTC))
                .returning(watchlists)
            )
            .mappings()
            .one()
        )
        return self._watchlist(row)

    def list(self) -> list[entities.Watchlist]:
        rows = self.connection.execute(select(watchlists).order_by(watchlists.c.id)).mappings()
        return [self._watchlist(row) for row in rows]

    def get(self, watchlist_id: int) -> entities.Watchlist | None:
        row = (
            self.connection.execute(select(watchlists).where(watchlists.c.id == watchlist_id))
            .mappings()
            .first()
        )
        if row is None:
            return None
        items = self._items(
            self.connection.execute(
                select(watchlist_items)
                .where(watchlist_items.c.watchlist_id == watchlist_id)
                .order_by(watchlist_items.c.id)
            ).mappings()
        )
        return self._watchlist(row, items)

    def delete(self, watchlist_id: int) -> None:
        self.connection.execute(delete(watchlists).where(watchlists.c.id == watchlist_id))

    def find_item(
        self, watchlist_id: int, item_id: int, *, lock: bool = False
    ) -> entities.WatchlistItem | None:
        statement = select(watchlist_items).where(
            watchlist_items.c.watchlist_id == watchlist_id,
            watchlist_items.c.id == item_id,
        )
        if lock:
            statement = statement.with_for_update()
        row = self.connection.execute(statement).mappings().first()
        return self._items([row])[0] if row else None

    def find_game_item(self, watchlist_id: int, game_id: str) -> entities.WatchlistItem | None:
        row = (
            self.connection.execute(
                select(watchlist_items).where(
                    watchlist_items.c.watchlist_id == watchlist_id,
                    watchlist_items.c.game_id == game_id,
                )
            )
            .mappings()
            .first()
        )
        return self._items([row])[0] if row else None

    def add_item(
        self, watchlist_id: int, game_id: str, target_price: Decimal, steam_only: bool
    ) -> entities.WatchlistItem:
        row = (
            self.connection.execute(
                insert(watchlist_items)
                .values(
                    watchlist_id=watchlist_id,
                    game_id=game_id,
                    target_price=target_price,
                    steam_only=steam_only,
                    alert_active=False,
                    created_at=datetime.now(UTC),
                )
                .returning(watchlist_items)
            )
            .mappings()
            .one()
        )
        return self._items([row])[0]

    def update_item(
        self, item_id: int, target_price: Decimal | None, steam_only: bool | None
    ) -> entities.WatchlistItem:
        values = {}
        if target_price is not None:
            values["target_price"] = target_price
        if steam_only is not None:
            values["steam_only"] = steam_only
        if values:
            self.connection.execute(
                update(watchlist_items).where(watchlist_items.c.id == item_id).values(**values)
            )
        row = (
            self.connection.execute(select(watchlist_items).where(watchlist_items.c.id == item_id))
            .mappings()
            .one()
        )
        return self._items([row])[0]

    def delete_item(self, item_id: int) -> None:
        self.connection.execute(delete(watchlist_items).where(watchlist_items.c.id == item_id))

    def items_for_game(self, game_id: str, *, lock: bool = False) -> list[entities.WatchlistItem]:
        if lock and self.connection.dialect.name == "postgresql":
            # DELETE takes the parent lock before cascading into its items. Refresh must
            # use the same order before it locks items and inserts notification FKs.
            parent_ids = select(watchlist_items.c.watchlist_id).where(
                watchlist_items.c.game_id == game_id
            )
            self.connection.execute(
                select(watchlists.c.id)
                .where(watchlists.c.id.in_(parent_ids))
                .order_by(watchlists.c.id)
                .with_for_update(read=True, key_share=True)
            ).all()
        statement = (
            select(watchlist_items)
            .where(watchlist_items.c.game_id == game_id)
            .order_by(watchlist_items.c.id)
        )
        if lock:
            statement = statement.with_for_update()
        return self._items(self.connection.execute(statement).mappings())

    def watched_game_ids(self) -> list[str]:
        return list(
            self.connection.execute(
                select(watchlist_items.c.game_id).distinct().order_by(watchlist_items.c.game_id)
            ).scalars()
        )

    def set_alert_active(self, item_id: int, active: bool) -> None:
        self.connection.execute(
            update(watchlist_items)
            .where(watchlist_items.c.id == item_id)
            .values(alert_active=active)
        )

    def add_notification(
        self, item: entities.WatchlistItem, observed_price: Decimal
    ) -> entities.Notification:
        row = (
            self.connection.execute(
                insert(notifications)
                .values(
                    watchlist_id=item.watchlist_id,
                    item_id=item.id,
                    game_id=item.game_id,
                    game_title=item.game.title,
                    target_price=item.target_price,
                    observed_price=observed_price,
                    created_at=datetime.now(UTC),
                )
                .returning(notifications)
            )
            .mappings()
            .one()
        )
        return notification_view(row)

    def notifications(
        self, watchlist_id: int, limit: int, offset: int
    ) -> list[entities.Notification]:
        rows = self.connection.execute(
            select(notifications)
            .where(notifications.c.watchlist_id == watchlist_id)
            .order_by(notifications.c.created_at.desc(), notifications.c.id.desc())
            .limit(limit)
            .offset(offset)
        ).mappings()
        return [notification_view(row) for row in rows]
