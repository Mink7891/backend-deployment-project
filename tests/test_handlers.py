"""Бизнес-логика хендлеров и сервисов на подменённых репозиториях."""

from contextlib import asynccontextmanager
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from game_radar.dispatcher import UseCaseDispatcher
from game_radar.errors import ServiceError
from game_radar.services.price_alert_service import PriceAlertService
from game_radar.usecase_handlers.add_watchlist_item_handler import AddWatchlistItemHandler
from game_radar.usecases.watchlists import AddWatchlistItemUseCase, GetWatchlistUseCase


class FakeSession:
    @asynccontextmanager
    async def begin(self):
        yield


def make_item(alert_active):
    offer = SimpleNamespace(store_id="1", price=Decimal("3.99"))
    game = SimpleNamespace(offers=[offer])
    return SimpleNamespace(
        id=1, game=game, steam_only=True, target_price=Decimal("4.00"), alert_active=alert_active
    )


@pytest.mark.anyio
async def test_alert_created_only_on_transition_into_threshold():
    item_repo = SimpleNamespace(set_alert_active=AsyncMock())
    notification_repo = SimpleNamespace(create=AsyncMock(return_value="notification"))
    service = PriceAlertService(item_repo, notification_repo)

    assert await service.evaluate(FakeSession(), make_item(alert_active=False)) == "notification"
    item_repo.set_alert_active.assert_awaited_once()

    notification_repo.create.reset_mock()
    assert await service.evaluate(FakeSession(), make_item(alert_active=True)) is None
    notification_repo.create.assert_not_awaited()


@pytest.mark.anyio
async def test_add_item_to_missing_watchlist_does_not_call_price_api():
    watchlist_repo = SimpleNamespace(get=AsyncMock(return_value=None))
    refresh_service = SimpleNamespace(refresh=AsyncMock())
    handler = AddWatchlistItemHandler(watchlist_repo, AsyncMock(), refresh_service, AsyncMock())

    with pytest.raises(ServiceError) as error:
        await handler.handle(AddWatchlistItemUseCase(1, "612", Decimal("4.00")), FakeSession())

    assert error.value.code == "WATCHLIST_NOT_FOUND"
    refresh_service.refresh.assert_not_awaited()


@pytest.mark.anyio
async def test_add_duplicate_game_is_conflict():
    watchlist_repo = SimpleNamespace(get=AsyncMock(return_value=object()))
    item_repo = SimpleNamespace(get_by_game=AsyncMock(return_value=object()))
    handler = AddWatchlistItemHandler(watchlist_repo, item_repo, AsyncMock(), AsyncMock())

    with pytest.raises(ServiceError) as error:
        await handler.handle(AddWatchlistItemUseCase(1, "612", Decimal("4.00")), FakeSession())

    assert error.value.status == 409


@pytest.mark.anyio
async def test_dispatcher_routes_usecase_and_rejects_unknown():
    dispatcher = UseCaseDispatcher()
    handler = AsyncMock(return_value="result")
    dispatcher.register(GetWatchlistUseCase, handler)

    assert await dispatcher.dispatch(GetWatchlistUseCase(1), "session") == "result"
    handler.assert_awaited_once_with(GetWatchlistUseCase(1), "session")
    with pytest.raises(ValueError):
        await dispatcher.dispatch(AddWatchlistItemUseCase(1, "612", Decimal("1")), "session")
