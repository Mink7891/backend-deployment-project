"""SQLAlchemy Core adapters; callers own connections and transactions."""

from app.repositories.factory import RepositorySet, create_repositories
from app.repositories.games import GamesRepository
from app.repositories.watchlists import WatchlistsRepository

__all__ = ["GamesRepository", "RepositorySet", "WatchlistsRepository", "create_repositories"]
