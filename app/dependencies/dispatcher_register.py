"""Composition root: create shared services and bind UseCase contracts to handlers."""

from collections.abc import Callable

from app import usecase_handlers, usecases
from app.adapters.ports import PriceProvider
from app.dispatcher import UseCaseDispatcher
from app.repositories import create_repositories
from app.services.game_refresh_service import GameRefreshService
from app.usecase_handlers.base import ConnectionFactory, RepositoryFactory


class DispatcherRegistrar:
    def __init__(
        self,
        dispatcher: UseCaseDispatcher,
        connection_factory: ConnectionFactory,
        provider: PriceProvider,
        cache_ttl_seconds: int = 300,
        repository_factory: RepositoryFactory = create_repositories,
        should_stop: Callable[[], bool] | None = None,
    ):
        self.dispatcher = dispatcher
        self.connection_factory = connection_factory
        self.provider = provider
        self.cache_ttl_seconds = cache_ttl_seconds
        self.repository_factory = repository_factory
        self.should_stop = should_stop

    def register(self) -> UseCaseDispatcher:
        refresh_service = GameRefreshService(self.provider, self.cache_ttl_seconds)
        registrations = (
            (usecases.SearchGamesUseCase, usecase_handlers.SearchGamesHandler),
            (usecases.GetGameUseCase, usecase_handlers.GetGameHandler),
            (usecases.GetPriceHistoryUseCase, usecase_handlers.GetPriceHistoryHandler),
            (usecases.CreateWatchlistUseCase, usecase_handlers.CreateWatchlistHandler),
            (usecases.ListWatchlistsUseCase, usecase_handlers.ListWatchlistsHandler),
            (usecases.GetWatchlistUseCase, usecase_handlers.GetWatchlistHandler),
            (usecases.DeleteWatchlistUseCase, usecase_handlers.DeleteWatchlistHandler),
            (usecases.AddWatchlistItemUseCase, usecase_handlers.AddWatchlistItemHandler),
            (usecases.UpdateWatchlistItemUseCase, usecase_handlers.UpdateWatchlistItemHandler),
            (usecases.DeleteWatchlistItemUseCase, usecase_handlers.DeleteWatchlistItemHandler),
            (usecases.GetWatchlistSummaryUseCase, usecase_handlers.GetWatchlistSummaryHandler),
            (usecases.GetNotificationsUseCase, usecase_handlers.GetNotificationsHandler),
            (usecases.RefreshWatchlistUseCase, usecase_handlers.RefreshWatchlistHandler),
            (
                usecases.RefreshAllWatchedGamesUseCase,
                usecase_handlers.RefreshAllWatchedGamesHandler,
            ),
        )
        for contract_type, handler_type in registrations:
            extra = (
                {"should_stop": self.should_stop}
                if contract_type is usecases.RefreshAllWatchedGamesUseCase
                else {}
            )
            handler = handler_type(
                self.connection_factory,
                self.provider,
                cache_ttl_seconds=self.cache_ttl_seconds,
                repository_factory=self.repository_factory,
                refresh_service=refresh_service,
                **extra,
            )
            self.dispatcher.register(contract_type, handler.handle)
        return self.dispatcher


def build_dispatcher(
    connection_factory: ConnectionFactory,
    provider: PriceProvider,
    cache_ttl_seconds: int = 300,
    repository_factory: RepositoryFactory = create_repositories,
    should_stop: Callable[[], bool] | None = None,
) -> UseCaseDispatcher:
    return DispatcherRegistrar(
        UseCaseDispatcher(),
        connection_factory,
        provider,
        cache_ttl_seconds,
        repository_factory,
        should_stop,
    ).register()


_dispatcher_instance: UseCaseDispatcher | None = None


def init_dispatcher(*args, **kwargs) -> UseCaseDispatcher:
    global _dispatcher_instance
    _dispatcher_instance = build_dispatcher(*args, **kwargs)
    return _dispatcher_instance


def get_usecase_dispatcher() -> UseCaseDispatcher:
    if _dispatcher_instance is None:
        raise RuntimeError("UseCaseDispatcher is not initialized")
    return _dispatcher_instance
