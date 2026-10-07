"""Guard the taught contract/handler/dispatcher/Core transaction boundaries."""

import ast
import inspect
from dataclasses import FrozenInstanceError, is_dataclass
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from app import models
from app.dispatcher import UseCaseDispatcher
from app.domain.entities import Watchlist
from app.repositories import create_repositories
from app.schemas import AddItemRequest, CreateWatchlistRequest, UpdateItemRequest, WatchlistResponse
from app.usecase_handlers import AddWatchlistItemHandler, CreateWatchlistHandler
from app.usecases import (
    AddWatchlistItemUseCase,
    CreateWatchlistUseCase,
    DeleteWatchlistItemUseCase,
    DeleteWatchlistUseCase,
    GetGameUseCase,
    GetNotificationsUseCase,
    GetPriceHistoryUseCase,
    GetWatchlistSummaryUseCase,
    GetWatchlistUseCase,
    ListWatchlistsUseCase,
    RefreshAllWatchedGamesUseCase,
    RefreshWatchlistUseCase,
    SearchGamesUseCase,
    UpdateWatchlistItemUseCase,
)

CONTRACTS = [
    SearchGamesUseCase("lego"),
    GetGameUseCase("612"),
    GetPriceHistoryUseCase("612"),
    CreateWatchlistUseCase(CreateWatchlistRequest(name="Games")),
    ListWatchlistsUseCase(),
    GetWatchlistUseCase(1),
    DeleteWatchlistUseCase(1),
    AddWatchlistItemUseCase(1, AddItemRequest(game_id="612", target_price=Decimal("4.00"))),
    UpdateWatchlistItemUseCase(1, 2, UpdateItemRequest(target_price=Decimal("3.00"))),
    DeleteWatchlistItemUseCase(1, 2),
    GetWatchlistSummaryUseCase(1),
    GetNotificationsUseCase(1),
    RefreshWatchlistUseCase(1),
    RefreshAllWatchedGamesUseCase(),
]


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda contract: type(contract).__name__)
def test_commands_and_queries_are_frozen_data_without_execution_logic(contract):
    assert is_dataclass(contract)
    assert type(contract).__name__.endswith("UseCase")
    assert type(contract).__dataclass_params__.frozen is True
    with pytest.raises(FrozenInstanceError):
        contract.business_dependency = object()
    assert not hasattr(contract, "execute")
    assert not hasattr(contract, "handle")
    assert not [
        name
        for name, value in vars(type(contract)).items()
        if callable(value) and not name.startswith("__")
    ]
    # Inspect the declared class rather than generated dataclass __init__/__repr__.
    declaration = ast.parse(inspect.getsource(type(contract))).body[0]
    assert not any(
        isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
        and member.name != "__post_init__"
        for member in declaration.body
    )


def test_dispatcher_returns_registered_handler_result_and_rejects_unknown_contract():
    dispatcher = UseCaseDispatcher()
    handler = MagicMock(return_value={"cached": True})
    dispatcher.register(GetGameUseCase, handler)
    command = GetGameUseCase("612")
    assert dispatcher.dispatch(command) == {"cached": True}
    handler.assert_called_once_with(command)
    with pytest.raises(RuntimeError, match="not supported"):
        dispatcher.dispatch(GetPriceHistoryUseCase("612"))
    assert handler.call_count == 1


def test_duplicate_registration_does_not_replace_existing_dispatcher_handler():
    dispatcher = UseCaseDispatcher()
    original = MagicMock(return_value="original")
    replacement = MagicMock(return_value="replacement")
    dispatcher.register(GetGameUseCase, original)
    with pytest.raises(ValueError, match="already registered"):
        dispatcher.register(GetGameUseCase, replacement)
    assert dispatcher.dispatch(GetGameUseCase("612")) == "original"
    replacement.assert_not_called()


def test_handler_accepts_injected_connection_and_repositories_and_returns_response_dto(provider):
    connection = MagicMock(spec=Connection)
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection
    connection_factory = MagicMock(return_value=connection_context)
    view = Watchlist(7, "Games", datetime.now(UTC))
    repository = MagicMock()
    repository.create.return_value = view
    repository_factory = MagicMock(return_value=SimpleNamespace(watchlists=repository))
    handler = CreateWatchlistHandler(
        connection_factory,
        provider,
        repository_factory=repository_factory,
    )
    result = handler.handle(CreateWatchlistUseCase(CreateWatchlistRequest(name="Games")))
    assert isinstance(result, WatchlistResponse)
    assert result.id == view.id and result.name == view.name
    connection_factory.assert_called_once_with()
    repository_factory.assert_called_once_with(connection)
    connection.begin.assert_called_once_with()
    repository.create.assert_called_once_with("Games")


def test_repository_returns_plain_view_and_leaves_commit_to_caller(connection_factory):
    with connection_factory() as connection:
        transaction = connection.begin()
        view = create_repositories(connection).watchlists.create("Uncommitted")
        assert is_dataclass(view) and not isinstance(view, BaseModel)
        assert type(view).__dataclass_params__.frozen is True
        assert transaction.is_active
        assert connection.scalar(select(func.count()).select_from(models.watchlists)) == 1
        transaction.rollback()
    with connection_factory() as verification:
        assert verification.scalar(select(func.count()).select_from(models.watchlists)) == 0


def test_handler_rolls_back_every_partial_write_when_notification_creation_fails(
    connection_factory, provider
):
    watchlist = CreateWatchlistHandler(connection_factory, provider).handle(
        CreateWatchlistUseCase(CreateWatchlistRequest(name="Persistent watchlist"))
    )

    def failing_repositories(connection):
        actual = create_repositories(connection)

        class FailingNotifications:
            def __getattr__(self, name):
                return getattr(actual.watchlists, name)

            def add_notification(self, item, observed_price):
                actual.watchlists.add_notification(item, observed_price)
                raise RuntimeError("Injected failure after database writes")

        return SimpleNamespace(games=actual.games, watchlists=FailingNotifications())

    handler = AddWatchlistItemHandler(
        connection_factory,
        provider,
        repository_factory=failing_repositories,
    )
    command = AddWatchlistItemUseCase(
        watchlist.id, AddItemRequest(game_id="612", target_price=Decimal("4.00"))
    )
    with pytest.raises(RuntimeError, match="after database writes"):
        handler.handle(command)
    with connection_factory() as verification:
        for table in (
            models.games,
            models.offers,
            models.price_snapshots,
            models.watchlist_items,
            models.notifications,
        ):
            assert verification.scalar(select(func.count()).select_from(table)) == 0, table.name
        assert verification.scalar(select(func.count()).select_from(models.watchlists)) == 1
