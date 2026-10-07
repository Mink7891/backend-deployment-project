"""SQLAlchemy ORM-модели сервиса Game Radar.

Схему БД ведут миграции Alembic (`migrations/`); модели должны им соответствовать.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый класс для всех ORM-моделей."""

    pass


class GameModel(Base):
    """Таблица games — локальный каталог игр."""

    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    steam_app_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    cheapest_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    offers: Mapped[list[OfferModel]] = relationship(
        lazy="selectin",
        order_by="(OfferModel.price, OfferModel.store_id, OfferModel.deal_id)",
        passive_deletes=True,
    )


class OfferModel(Base):
    """Таблица offers — текущие предложения магазинов по игре."""

    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    deal_id: Mapped[str] = mapped_column(String(512), nullable=False)
    store_id: Mapped[str] = mapped_column(String(32), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    retail_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    savings: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)

    __table_args__ = (
        UniqueConstraint("game_id", "deal_id"),
        Index("ix_offers_game_id", "game_id"),
    )


class PriceSnapshotModel(Base):
    """Таблица price_snapshots — история наблюдавшихся цен."""

    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    store_id: Mapped[str] = mapped_column(String(32), nullable=False)
    deal_id: Mapped[str] = mapped_column(String(512), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_price_snapshots_game_observed", "game_id", "observed_at"),)


class WatchlistModel(Base):
    """Таблица watchlists — списки желаемых игр."""

    __tablename__ = "watchlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    items: Mapped[list[WatchlistItemModel]] = relationship(
        lazy="selectin", order_by="WatchlistItemModel.id", passive_deletes=True
    )


class WatchlistItemModel(Base):
    """Таблица watchlist_items — игра в списке с желаемой ценой."""

    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(
        ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False
    )
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), nullable=False)
    target_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    steam_only: Mapped[bool] = mapped_column(Boolean, nullable=False)
    alert_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    game: Mapped[GameModel] = relationship(lazy="selectin")

    __table_args__ = (
        UniqueConstraint("watchlist_id", "game_id"),
        Index("ix_watchlist_items_game_id", "game_id"),
        Index("ix_watchlist_items_watchlist_id", "watchlist_id"),
    )


class NotificationModel(Base):
    """Таблица notifications — журнал достижения желаемой цены."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(
        ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[int | None] = mapped_column(
        ForeignKey("watchlist_items.id", ondelete="SET NULL"), nullable=True
    )
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), nullable=False)
    game_title: Mapped[str] = mapped_column(String(300), nullable=False)
    target_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    observed_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_notifications_watchlist_created", "watchlist_id", "created_at"),)
