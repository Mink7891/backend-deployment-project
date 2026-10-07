from collections.abc import Callable, Generator
from contextlib import contextmanager

from sqlalchemy.engine import Connection

from app.adapters.ports import PriceProvider
from app.repositories import RepositorySet, create_repositories
from app.services.game_refresh_service import GameRefreshService

ConnectionFactory = Callable[[], Connection]
RepositoryFactory = Callable[[Connection], RepositorySet]


class DatabaseHandler:
    def __init__(
        self,
        connection_factory: ConnectionFactory,
        provider: PriceProvider,
        cache_ttl_seconds: int = 300,
        repository_factory: RepositoryFactory = create_repositories,
        refresh_service: GameRefreshService | None = None,
    ):
        self.connection_factory = connection_factory
        self.provider = provider
        self.cache_ttl_seconds = cache_ttl_seconds
        self.repository_factory = repository_factory
        self.refresh_service = refresh_service or GameRefreshService(provider, cache_ttl_seconds)

    @contextmanager
    def transaction(self) -> Generator[RepositorySet]:
        """Handlers own begin/commit/rollback; repositories only execute Core statements."""
        with self.connection_factory() as connection:
            with connection.begin():
                yield self.repository_factory(connection)
