"""Репозиторий таблиц games и offers (каталог игр и текущие предложения)."""

from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import BigInteger, delete, func, insert, literal, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.database.models import GameModel, OfferModel
from game_radar.mapping.game_mapper import map_game_row, map_offer_rows
from game_radar.schemas.price_provider import ProviderGame


class GameRepository:
    """Слой доступа к данным каталога игр."""

    async def get(
        self, session: AsyncSession, game_id: str, for_update: bool = False
    ) -> GameModel | None:
        if for_update:
            # Строку, которой ещё нет, заблокировать нельзя: сериализуем первое
            # создание игры advisory-блокировкой по её идентификатору.
            key = int.from_bytes(hashlib.blake2b(game_id.encode(), digest_size=8).digest(), "big")
            key &= (1 << 63) - 1
            await session.execute(select(func.pg_advisory_xact_lock(literal(key, BigInteger()))))
        stmt = (
            select(GameModel)
            .where(GameModel.id == game_id)
            .execution_options(populate_existing=True)
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_metadata(self, session: AsyncSession, game: ProviderGame) -> GameModel:
        """Создаёт или обновляет игру без изменения её предложений."""
        existing = await self.get(session, game.id, for_update=True)
        values = map_game_row(game)
        if existing is None:
            await session.execute(insert(GameModel).values(id=game.id, **values))
        else:
            if existing.source != game.source:
                # Цены другого источника несопоставимы: сбрасываем кеш предложений.
                await session.execute(delete(OfferModel).where(OfferModel.game_id == game.id))
                values["last_refreshed_at"] = None
            await session.execute(update(GameModel).where(GameModel.id == game.id).values(**values))
        return await self.get(session, game.id)

    async def replace_offers(
        self, session: AsyncSession, game: ProviderGame, observed_at: datetime
    ) -> GameModel:
        """Сохраняет свежие предложения игры и время их получения."""
        await self.save_metadata(session, game)
        await session.execute(delete(OfferModel).where(OfferModel.game_id == game.id))
        rows = map_offer_rows(game)
        if rows:
            await session.execute(insert(OfferModel), rows)
        await session.execute(
            update(GameModel)
            .where(GameModel.id == game.id)
            .values(
                last_refreshed_at=observed_at,
                cheapest_price=min((offer.price for offer in game.offers), default=None),
            )
        )
        return await self.get(session, game.id)
