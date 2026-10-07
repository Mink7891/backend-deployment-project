"""Проверка доступности БД и наличия схемы."""

from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.database.models import WatchlistModel


class HealthRepository:
    async def check(self, session: AsyncSession) -> None:
        """Падает, если БД недоступна или миграции не применены."""
        await session.execute(text("SELECT 1"))
        await session.execute(select(WatchlistModel.id).limit(1))
