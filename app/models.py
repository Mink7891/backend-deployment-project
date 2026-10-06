from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Game(Base):
    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    steam_app_id: Mapped[str | None] = mapped_column(String(32))
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048))
    source: Mapped[str] = mapped_column(String(20))
    cheapest_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    offers: Mapped[list["Offer"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class Offer(Base):
    __tablename__ = "offers"
    __table_args__ = (UniqueConstraint("game_id", "deal_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), index=True)
    deal_id: Mapped[str] = mapped_column(String(512))
    store_id: Mapped[str] = mapped_column(String(32))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    retail_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    savings: Mapped[Decimal] = mapped_column(Numeric(12, 6))


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"
    __table_args__ = (Index("ix_price_snapshots_game_observed", "game_id", "observed_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    store_id: Mapped[str] = mapped_column(String(32))
    deal_id: Mapped[str] = mapped_column(String(512))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    source: Mapped[str] = mapped_column(String(20))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Watchlist(Base):
    __tablename__ = "watchlists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    items: Mapped[list["WatchlistItem"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", passive_deletes=True
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("watchlist_id", "game_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(
        ForeignKey("watchlists.id", ondelete="CASCADE"), index=True
    )
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), index=True)
    target_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    steam_only: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    game: Mapped[Game] = relationship(lazy="selectin")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_watchlist_created", "watchlist_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlists.id", ondelete="CASCADE"))
    item_id: Mapped[int | None] = mapped_column(
        ForeignKey("watchlist_items.id", ondelete="SET NULL")
    )
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"))
    game_title: Mapped[str] = mapped_column(String(300))
    target_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    observed_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
