"""Репозиторий таблицы watchlist_items."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.database.models import WatchlistItemModel, WatchlistModel


class WatchlistItemRepository:
    """Слой доступа к играм в списках наблюдения."""

    async def get(
        self,
        session: AsyncSession,
        watchlist_id: int,
        item_id: int,
        for_update: bool = False,
    ) -> WatchlistItemModel | None:
        stmt = (
            select(WatchlistItemModel)
            .where(
                WatchlistItemModel.watchlist_id == watchlist_id,
                WatchlistItemModel.id == item_id,
            )
            .execution_options(populate_existing=True)
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_game(
        self, session: AsyncSession, watchlist_id: int, game_id: str
    ) -> WatchlistItemModel | None:
        result = await session.execute(
            select(WatchlistItemModel).where(
                WatchlistItemModel.watchlist_id == watchlist_id,
                WatchlistItemModel.game_id == game_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_for_game(
        self, session: AsyncSession, game_id: str, for_update: bool = False
    ) -> Sequence[WatchlistItemModel]:
        if for_update:
            # Порядок блокировок: игра → родительские списки → позиции. DELETE списка
            # берёт блокировку родителя до каскада, поэтому обновление цены делает так же.
            parent_ids = select(WatchlistItemModel.watchlist_id).where(
                WatchlistItemModel.game_id == game_id
            )
            await session.execute(
                select(WatchlistModel.id)
                .where(WatchlistModel.id.in_(parent_ids))
                .order_by(WatchlistModel.id)
                .with_for_update(read=True, key_share=True)
            )
        stmt = (
            select(WatchlistItemModel)
            .where(WatchlistItemModel.game_id == game_id)
            .order_by(WatchlistItemModel.id)
            .execution_options(populate_existing=True)
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_watched_game_ids(self, session: AsyncSession) -> list[str]:
        result = await session.execute(
            select(WatchlistItemModel.game_id).distinct().order_by(WatchlistItemModel.game_id)
        )
        return list(result.scalars().all())

    async def create(
        self,
        session: AsyncSession,
        watchlist_id: int,
        game_id: str,
        target_price: Decimal,
        steam_only: bool,
    ) -> WatchlistItemModel:
        result = await session.execute(
            insert(WatchlistItemModel)
            .values(
                watchlist_id=watchlist_id,
                game_id=game_id,
                target_price=target_price,
                steam_only=steam_only,
                alert_active=False,
                created_at=datetime.now(UTC),
            )
            .returning(WatchlistItemModel.id)
        )
        return await self.get(session, watchlist_id, result.scalar_one())

    async def update(
        self,
        session: AsyncSession,
        item_id: int,
        target_price: Decimal | None,
        steam_only: bool | None,
    ) -> None:
        values: dict[str, object] = {}
        if target_price is not None:
            values["target_price"] = target_price
        if steam_only is not None:
            values["steam_only"] = steam_only
        if values:
            await session.execute(
                update(WatchlistItemModel).where(WatchlistItemModel.id == item_id).values(**values)
            )

    async def set_alert_active(self, session: AsyncSession, item_id: int, active: bool) -> None:
        await session.execute(
            update(WatchlistItemModel)
            .where(WatchlistItemModel.id == item_id)
            .values(alert_active=active)
        )

    async def delete(self, session: AsyncSession, item_id: int) -> None:
        await session.execute(delete(WatchlistItemModel).where(WatchlistItemModel.id == item_id))
