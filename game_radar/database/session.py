"""Конфигурация асинхронной сессии базы данных."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from game_radar.config import settings

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def close_db_session() -> None:
    """Закрывает движок и пул соединений."""
    await engine.dispose()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI-зависимость: предоставляет асинхронную сессию БД."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
