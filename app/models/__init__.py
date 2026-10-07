"""SQLAlchemy Core tables. The database schema is owned by Alembic migrations."""

from app.models.tables import (
    metadata,
)
from app.models.tables import t_games as games
from app.models.tables import t_notifications as notifications
from app.models.tables import t_offers as offers
from app.models.tables import t_price_snapshots as price_snapshots
from app.models.tables import t_watchlist_items as watchlist_items
from app.models.tables import t_watchlists as watchlists

__all__ = [
    "games",
    "metadata",
    "notifications",
    "offers",
    "price_snapshots",
    "watchlist_items",
    "watchlists",
]
