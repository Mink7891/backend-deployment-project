import hashlib
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import BigInteger, delete, func, insert, literal, select, update
from sqlalchemy.engine import Connection

from app.domain import entities
from app.models import games, offers, price_snapshots
from app.repositories.mapping import Record, game_view, utc


class GamesRepository:
    def __init__(self, connection: Connection):
        self.connection = connection

    def _get_record(self, game_id: str, lock: bool = False) -> Record | None:
        if lock and self.connection.dialect.name == "postgresql":
            # Missing rows cannot be row-locked; serialize cold-cache creation by game ID.
            key = int.from_bytes(hashlib.blake2b(game_id.encode(), digest_size=8).digest(), "big")
            key &= (1 << 63) - 1
            self.connection.execute(select(func.pg_advisory_xact_lock(literal(key, BigInteger()))))
        statement = select(games).where(games.c.id == game_id)
        if lock:
            statement = statement.with_for_update()
        return self.connection.execute(statement).mappings().first()

    def _views(self, records: Iterable[Record]) -> dict[str, entities.Game]:
        records = list(records)
        if not records:
            return {}
        game_ids = [row["id"] for row in records]
        offers_by_game = defaultdict(list)
        for row in self.connection.execute(
            select(offers)
            .where(offers.c.game_id.in_(game_ids))
            .order_by(offers.c.game_id, offers.c.price, offers.c.store_id, offers.c.deal_id)
        ).mappings():
            offers_by_game[row["game_id"]].append(row)
        return {row["id"]: game_view(row, offers_by_game[row["id"]]) for row in records}

    def get_many(self, game_ids: Iterable[str]) -> dict[str, entities.Game]:
        game_ids = sorted(set(game_ids))
        if not game_ids:
            return {}
        records = self.connection.execute(
            select(games).where(games.c.id.in_(game_ids)).order_by(games.c.id)
        ).mappings()
        return self._views(records)

    def get(self, game_id: str, *, lock: bool = False) -> entities.Game | None:
        row = self._get_record(game_id, lock)
        return self._views([row])[game_id] if row else None

    def save_metadata(self, game: entities.ProviderGame) -> entities.Game:
        row = self._get_record(game.id, lock=True)
        values = {
            "title": game.title,
            "steam_app_id": game.steam_app_id,
            "thumbnail_url": game.thumbnail_url,
            "source": game.source,
            "cheapest_price": game.cheapest_price,
        }
        if row is None:
            self.connection.execute(insert(games).values(id=game.id, **values))
        else:
            if row["source"] != game.source:
                self.connection.execute(delete(offers).where(offers.c.game_id == game.id))
                values["last_refreshed_at"] = None
            self.connection.execute(update(games).where(games.c.id == game.id).values(**values))
        return self.get(game.id)

    def save_observation(self, game: entities.ProviderGame, observed_at: datetime) -> entities.Game:
        self.save_metadata(game)
        self.connection.execute(delete(offers).where(offers.c.game_id == game.id))
        if game.offers:
            self.connection.execute(
                insert(offers),
                [
                    {
                        "game_id": game.id,
                        "deal_id": offer.deal_id,
                        "store_id": offer.store_id,
                        "price": offer.price,
                        "retail_price": offer.retail_price,
                        "savings": offer.savings,
                    }
                    for offer in game.offers
                ],
            )
            self.connection.execute(
                insert(price_snapshots),
                [
                    {
                        "game_id": game.id,
                        "store_id": offer.store_id,
                        "deal_id": offer.deal_id,
                        "price": offer.price,
                        "source": game.source,
                        "observed_at": observed_at,
                    }
                    for offer in game.offers
                ],
            )
        self.connection.execute(
            update(games)
            .where(games.c.id == game.id)
            .values(
                last_refreshed_at=observed_at,
                cheapest_price=min((offer.price for offer in game.offers), default=None),
            )
        )
        return self.get(game.id)

    def history(self, game_id: str, limit: int, offset: int) -> list[entities.PriceSnapshot]:
        rows = self.connection.execute(
            select(price_snapshots)
            .where(price_snapshots.c.game_id == game_id)
            .order_by(price_snapshots.c.observed_at.desc(), price_snapshots.c.id.desc())
            .limit(limit)
            .offset(offset)
        ).mappings()
        return [
            entities.PriceSnapshot(
                id=row["id"],
                game_id=row["game_id"],
                store_id=row["store_id"],
                deal_id=row["deal_id"],
                price=row["price"],
                observed_at=utc(row["observed_at"]),
                source=row["source"],
            )
            for row in rows
        ]
