"""Регистрация диспетчера — связывает все UseCase'ы с Handler'ами (DI-контейнер)."""

from __future__ import annotations

from game_radar.adapters.cheapshark_api import CheapSharkApi
from game_radar.adapters.mock_price_api import MockPriceApi
from game_radar.adapters.ports import PriceApi
from game_radar.config import settings
from game_radar.dispatcher import UseCaseDispatcher
from game_radar.repositories.database.game_repository import GameRepository
from game_radar.repositories.database.health_repository import HealthRepository
from game_radar.repositories.database.notification_repository import NotificationRepository
from game_radar.repositories.database.price_snapshot_repository import PriceSnapshotRepository
from game_radar.repositories.database.watchlist_item_repository import WatchlistItemRepository
from game_radar.repositories.database.watchlist_repository import WatchlistRepository
from game_radar.services.game_refresh_service import GameRefreshService
from game_radar.services.price_alert_service import PriceAlertService

# Хендлеры
from game_radar.usecase_handlers.add_watchlist_item_handler import AddWatchlistItemHandler
from game_radar.usecase_handlers.create_watchlist_handler import CreateWatchlistHandler
from game_radar.usecase_handlers.delete_watchlist_handler import DeleteWatchlistHandler
from game_radar.usecase_handlers.delete_watchlist_item_handler import DeleteWatchlistItemHandler
from game_radar.usecase_handlers.get_game_handler import GetGameHandler
from game_radar.usecase_handlers.get_health_handler import GetHealthHandler
from game_radar.usecase_handlers.get_notifications_handler import GetNotificationsHandler
from game_radar.usecase_handlers.get_price_history_handler import GetPriceHistoryHandler
from game_radar.usecase_handlers.get_watchlist_handler import GetWatchlistHandler
from game_radar.usecase_handlers.get_watchlist_summary_handler import GetWatchlistSummaryHandler
from game_radar.usecase_handlers.list_watchlists_handler import ListWatchlistsHandler
from game_radar.usecase_handlers.refresh_all_watched_games_handler import (
    RefreshAllWatchedGamesHandler,
)
from game_radar.usecase_handlers.refresh_watchlist_handler import RefreshWatchlistHandler
from game_radar.usecase_handlers.search_games_handler import SearchGamesHandler
from game_radar.usecase_handlers.update_watchlist_item_handler import UpdateWatchlistItemHandler

# UseCase'ы
from game_radar.usecases.games import GetGameUseCase, GetPriceHistoryUseCase, SearchGamesUseCase
from game_radar.usecases.health import GetHealthUseCase
from game_radar.usecases.refresh import RefreshAllWatchedGamesUseCase, RefreshWatchlistUseCase
from game_radar.usecases.watchlists import (
    AddWatchlistItemUseCase,
    CreateWatchlistUseCase,
    DeleteWatchlistItemUseCase,
    DeleteWatchlistUseCase,
    GetNotificationsUseCase,
    GetWatchlistSummaryUseCase,
    GetWatchlistUseCase,
    ListWatchlistsUseCase,
    UpdateWatchlistItemUseCase,
)


def create_price_api() -> PriceApi:
    """Источник цен по настройке PRICE_SOURCE."""
    if settings.PRICE_SOURCE == "cheapshark":
        return CheapSharkApi()
    return MockPriceApi()


class DispatcherRegistrar:
    """Конфигуратор UseCaseDispatcher — связывает UseCases с Handlers."""

    def __init__(self, dispatcher: UseCaseDispatcher) -> None:
        self._dispatcher = dispatcher

    def register(self) -> UseCaseDispatcher:
        game_repo = GameRepository()
        snapshot_repo = PriceSnapshotRepository()
        watchlist_repo = WatchlistRepository()
        item_repo = WatchlistItemRepository()
        notification_repo = NotificationRepository()
        health_repo = HealthRepository()

        price_api = create_price_api()

        alert_service = PriceAlertService(item_repo, notification_repo)
        refresh_service = GameRefreshService(
            price_api,
            game_repo,
            snapshot_repo,
            item_repo,
            alert_service,
            settings.REFRESH_MIN_INTERVAL_SECONDS,
        )

        self._dispatcher.register(
            GetHealthUseCase,
            GetHealthHandler(health_repo, price_api.source).handle,
        )
        self._dispatcher.register(
            SearchGamesUseCase,
            SearchGamesHandler(price_api, game_repo).handle,
        )
        self._dispatcher.register(
            GetGameUseCase,
            GetGameHandler(refresh_service).handle,
        )
        self._dispatcher.register(
            GetPriceHistoryUseCase,
            GetPriceHistoryHandler(game_repo, snapshot_repo).handle,
        )
        self._dispatcher.register(
            CreateWatchlistUseCase,
            CreateWatchlistHandler(watchlist_repo).handle,
        )
        self._dispatcher.register(
            ListWatchlistsUseCase,
            ListWatchlistsHandler(watchlist_repo).handle,
        )
        self._dispatcher.register(
            GetWatchlistUseCase,
            GetWatchlistHandler(watchlist_repo).handle,
        )
        self._dispatcher.register(
            DeleteWatchlistUseCase,
            DeleteWatchlistHandler(watchlist_repo).handle,
        )
        self._dispatcher.register(
            AddWatchlistItemUseCase,
            AddWatchlistItemHandler(
                watchlist_repo, item_repo, refresh_service, alert_service
            ).handle,
        )
        self._dispatcher.register(
            UpdateWatchlistItemUseCase,
            UpdateWatchlistItemHandler(item_repo, refresh_service, alert_service).handle,
        )
        self._dispatcher.register(
            DeleteWatchlistItemUseCase,
            DeleteWatchlistItemHandler(item_repo).handle,
        )
        self._dispatcher.register(
            GetWatchlistSummaryUseCase,
            GetWatchlistSummaryHandler(watchlist_repo, price_api.source).handle,
        )
        self._dispatcher.register(
            GetNotificationsUseCase,
            GetNotificationsHandler(watchlist_repo, notification_repo).handle,
        )
        self._dispatcher.register(
            RefreshWatchlistUseCase,
            RefreshWatchlistHandler(watchlist_repo, refresh_service).handle,
        )
        self._dispatcher.register(
            RefreshAllWatchedGamesUseCase,
            RefreshAllWatchedGamesHandler(item_repo, refresh_service).handle,
        )

        return self._dispatcher


_dispatcher_instance: UseCaseDispatcher | None = None


def init_dispatcher() -> UseCaseDispatcher:
    """Инициализирует глобальный UseCaseDispatcher. Идемпотентен."""
    global _dispatcher_instance
    if _dispatcher_instance is not None:
        return _dispatcher_instance
    dispatcher = UseCaseDispatcher()
    DispatcherRegistrar(dispatcher).register()
    _dispatcher_instance = dispatcher
    return dispatcher


def get_usecase_dispatcher() -> UseCaseDispatcher:
    if _dispatcher_instance is None:
        raise RuntimeError("UseCaseDispatcher is not initialized")
    return _dispatcher_instance
