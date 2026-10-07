"""Репозиторий таблицы price_snapshots (история наблюдавшихся цен)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.database.models import PriceSnapshotModel
from game_radar.schemas.price_provider import ProviderGame


class PriceSnapshotRepository:
    """Слой доступа к истории цен."""

    async def create_many(
        self, session: AsyncSession, game: ProviderGame, observed_at: datetime
    ) -> None:
        if not game.offers:
            return
        await session.execute(
            insert(PriceSnapshotModel),
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

    async def get_by_game(
        self, session: AsyncSession, game_id: str, limit: int, offset: int
    ) -> Sequence[PriceSnapshotModel]:
        result = await session.execute(
            select(PriceSnapshotModel)
            .where(PriceSnapshotModel.game_id == game_id)
            .order_by(PriceSnapshotModel.observed_at.desc(), PriceSnapshotModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()
