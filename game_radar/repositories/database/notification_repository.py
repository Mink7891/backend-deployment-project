"""Репозиторий таблицы notifications (журнал достижения желаемой цены)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.database.models import NotificationModel, WatchlistItemModel


class NotificationRepository:
    """Слой доступа к журналу срабатываний."""

    async def create(
        self, session: AsyncSession, item: WatchlistItemModel, observed_price: Decimal
    ) -> NotificationModel:
        result = await session.execute(
            insert(NotificationModel)
            .values(
                watchlist_id=item.watchlist_id,
                item_id=item.id,
                game_id=item.game_id,
                game_title=item.game.title,
                target_price=item.target_price,
                observed_price=observed_price,
                created_at=datetime.now(UTC),
            )
            .returning(NotificationModel.id)
        )
        notification = await session.get(NotificationModel, result.scalar_one())
        return notification

    async def get_by_watchlist(
        self, session: AsyncSession, watchlist_id: int, limit: int, offset: int
    ) -> Sequence[NotificationModel]:
        result = await session.execute(
            select(NotificationModel)
            .where(NotificationModel.watchlist_id == watchlist_id)
            .order_by(NotificationModel.created_at.desc(), NotificationModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()
