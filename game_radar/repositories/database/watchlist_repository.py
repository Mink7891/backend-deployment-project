"""Репозиторий таблицы watchlists."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.database.models import WatchlistModel


class WatchlistRepository:
    """Слой доступа к спискам наблюдения."""

    async def get(self, session: AsyncSession, watchlist_id: int) -> WatchlistModel | None:
        result = await session.execute(
            select(WatchlistModel)
            .where(WatchlistModel.id == watchlist_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_all(self, session: AsyncSession) -> Sequence[WatchlistModel]:
        result = await session.execute(select(WatchlistModel).order_by(WatchlistModel.id))
        return result.scalars().all()

    async def create(self, session: AsyncSession, name: str) -> WatchlistModel:
        result = await session.execute(
            insert(WatchlistModel)
            .values(name=name, created_at=datetime.now(UTC))
            .returning(WatchlistModel.id)
        )
        return await self.get(session, result.scalar_one())

    async def delete(self, session: AsyncSession, watchlist_id: int) -> None:
        # Позиции и журнал удаляются каскадом на стороне БД (ON DELETE CASCADE).
        await session.execute(delete(WatchlistModel).where(WatchlistModel.id == watchlist_id))
