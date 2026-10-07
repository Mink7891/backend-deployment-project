from sqlalchemy.engine import Connection

from app.repositories.games import GamesRepository
from app.repositories.watchlists import WatchlistsRepository


class RepositorySet:
    def __init__(self, connection: Connection):
        self.games = GamesRepository(connection)
        self.watchlists = WatchlistsRepository(connection)


def create_repositories(connection: Connection) -> RepositorySet:
    return RepositorySet(connection)
