"""Business scenarios execute frozen contracts through handlers, without HTTP."""

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest

from app.exceptions import Conflict, NotFound, ProviderUnavailable
from app.repositories import create_repositories
from app.schemas import AddItemRequest, CreateWatchlistRequest, UpdateItemRequest
from app.usecase_handlers import (
    AddWatchlistItemHandler,
    CreateWatchlistHandler,
    GetGameHandler,
    GetNotificationsHandler,
    GetPriceHistoryHandler,
    GetWatchlistSummaryHandler,
    RefreshAllWatchedGamesHandler,
    RefreshWatchlistHandler,
    SearchGamesHandler,
    UpdateWatchlistItemHandler,
)
from app.usecases import (
    AddWatchlistItemUseCase,
    CreateWatchlistUseCase,
    GetGameUseCase,
    GetNotificationsUseCase,
    GetPriceHistoryUseCase,
    GetWatchlistSummaryUseCase,
    RefreshAllWatchedGamesUseCase,
    RefreshWatchlistUseCase,
    SearchGamesUseCase,
    UpdateWatchlistItemUseCase,
)


class CountingProvider:
    def __init__(self, delegate):
        self.delegate = delegate
        self.source = delegate.source
        self.calls = []

    def search(self, query, limit=20):
        return self.delegate.search(query, limit)

    def get_game(self, game_id):
        self.calls.append(game_id)
        return self.delegate.get_game(game_id)


def create_watchlist(factory, provider, name="Games"):
    return CreateWatchlistHandler(factory, provider).handle(
        CreateWatchlistUseCase(request=CreateWatchlistRequest(name=name))
    )


def add_command(watchlist_id, game_id="612", target="3.99", steam_only=True):
    return AddWatchlistItemUseCase(
        watchlist_id=watchlist_id,
        request=AddItemRequest(
            game_id=game_id, target_price=Decimal(target), steam_only=steam_only
        ),
    )


def test_get_game_cache_skips_provider_and_history_duplicates(connection_factory, provider):
    counting = CountingProvider(provider)
    handler = GetGameHandler(connection_factory, counting, 300)
    first = handler.handle(GetGameUseCase(game_id="612"))
    second = handler.handle(GetGameUseCase(game_id="612"))
    assert first.last_refreshed_at == second.last_refreshed_at
    assert counting.calls == ["612"]
    history = GetPriceHistoryHandler(connection_factory, provider).handle(
        GetPriceHistoryUseCase("612")
    )
    assert len(history) == 2
    assert {row.store_id for row in history} == {"1", "7"}


def test_search_metadata_does_not_create_price_observations(connection_factory, provider):
    found = SearchGamesHandler(connection_factory, provider).handle(
        SearchGamesUseCase(query="lego")
    )
    assert [game.id for game in found] == ["612"]
    history = GetPriceHistoryHandler(connection_factory, provider)
    assert history.handle(GetPriceHistoryUseCase("612")) == []
    GetGameHandler(connection_factory, provider, 300).handle(GetGameUseCase("612"))
    assert len(history.handle(GetPriceHistoryUseCase("612"))) == 2


def test_cached_refresh_deduplicates_notifications(connection_factory, provider):
    watchlist = create_watchlist(connection_factory, provider)
    AddWatchlistItemHandler(connection_factory, provider, 300).handle(add_command(watchlist.id))
    result = RefreshWatchlistHandler(connection_factory, provider, 300).handle(
        RefreshWatchlistUseCase(watchlist.id)
    )
    assert result.refreshed_games == 0
    assert result.checked_items == result.matched_count == 1
    assert result.notifications_created == 0
    events = GetNotificationsHandler(connection_factory, provider).handle(
        GetNotificationsUseCase(watchlist.id)
    )
    assert len(events) == 1
    assert events[0].observed_price == events[0].target_price == Decimal("3.99")


def test_notification_only_on_reentering_price_threshold(connection_factory, provider):
    watchlist = create_watchlist(connection_factory, provider)
    item = AddWatchlistItemHandler(connection_factory, provider, 0).handle(
        add_command(watchlist.id, target="4.00")
    )
    original = provider.games["612"]
    expensive = tuple(replace(offer, price=Decimal("8.00")) for offer in original.offers)
    provider.games["612"] = replace(original, offers=expensive, cheapest_price=Decimal("8.00"))
    refresh = RefreshWatchlistHandler(connection_factory, provider, 0)
    events = GetNotificationsHandler(connection_factory, provider)
    down = refresh.handle(RefreshWatchlistUseCase(watchlist.id))
    assert down.matched_count == down.notifications_created == 0
    assert len(events.handle(GetNotificationsUseCase(watchlist.id))) == 1
    provider.games["612"] = original
    up = refresh.handle(RefreshWatchlistUseCase(watchlist.id))
    assert up.matched_count == up.notifications_created == 1
    assert len(events.handle(GetNotificationsUseCase(watchlist.id))) == 2
    with connection_factory() as connection:
        assert (
            create_repositories(connection).watchlists.find_item(watchlist.id, item.id).alert_active
        )
    history = GetPriceHistoryHandler(connection_factory, provider).handle(
        GetPriceHistoryUseCase("612")
    )
    assert len(history) == 6


def test_changing_store_preference_recalculates_threshold(connection_factory, provider):
    watchlist = create_watchlist(connection_factory, provider)
    item = AddWatchlistItemHandler(connection_factory, provider, 300).handle(
        add_command(watchlist.id, target="3.00")
    )
    assert item.threshold_met is False
    updated = UpdateWatchlistItemHandler(connection_factory, provider, 300).handle(
        UpdateWatchlistItemUseCase(
            watchlist.id, item.id, request=UpdateItemRequest(steam_only=False)
        )
    )
    assert updated.threshold_met is True
    summary = GetWatchlistSummaryHandler(connection_factory, provider).handle(
        GetWatchlistSummaryUseCase(watchlist.id)
    )
    assert summary.current_total == Decimal("2.99")
    events = GetNotificationsHandler(connection_factory, provider).handle(
        GetNotificationsUseCase(watchlist.id)
    )
    assert len(events) == 1


def test_duplicate_or_missing_watchlist_fails_before_external_lookup(connection_factory, provider):
    counting = CountingProvider(provider)
    handler = AddWatchlistItemHandler(connection_factory, counting, 300)
    with pytest.raises(NotFound):
        handler.handle(add_command(9999, target="4.00"))
    assert counting.calls == []
    watchlist = create_watchlist(connection_factory, provider)
    handler.handle(add_command(watchlist.id, target="4.00"))
    with pytest.raises(Conflict):
        handler.handle(add_command(watchlist.id, target="4.00"))
    assert counting.calls == ["612"]


def test_worker_refreshes_shared_game_once_and_updates_both_watchlists(
    connection_factory, provider
):
    for name in ["First", "Second"]:
        watchlist = create_watchlist(connection_factory, provider, name)
        AddWatchlistItemHandler(connection_factory, provider, 300).handle(
            add_command(watchlist.id, target="2.00")
        )
    counting = CountingProvider(provider)
    result = RefreshAllWatchedGamesHandler(connection_factory, counting, 0).handle(
        RefreshAllWatchedGamesUseCase()
    )
    assert counting.calls == ["612"]
    assert result.refreshed_games == 1
    assert result.checked_items == 2
    assert result.matched_count == result.notifications_created == 0


def test_worker_continues_after_provider_failure(connection_factory, provider):
    watchlist = create_watchlist(connection_factory, provider)
    add = AddWatchlistItemHandler(connection_factory, provider, 300)
    add.handle(add_command(watchlist.id, target="4.00"))
    add.handle(add_command(watchlist.id, "128", "8.00"))

    class PartialFailure(CountingProvider):
        def get_game(self, game_id):
            if game_id == "128":
                raise ProviderUnavailable()
            return super().get_game(game_id)

    handler = RefreshAllWatchedGamesHandler(connection_factory, PartialFailure(provider), 0)
    result = handler.handle(RefreshAllWatchedGamesUseCase())
    assert handler.failed_games == 1
    assert result.refreshed_games == result.checked_items == 1
    events = GetNotificationsHandler(connection_factory, provider).handle(
        GetNotificationsUseCase(watchlist.id)
    )
    assert len(events) == 2


@pytest.mark.parametrize(
    "cached_sources,configured_source,expected_source",
    [
        (("mock", "cheapshark"), "cheapshark", "mixed"),
        (("mock", "mock"), "cheapshark", "mock"),
        ((), "cheapshark", "cheapshark"),
    ],
)
def test_summary_reports_cached_price_sources_without_querying_current_provider(
    connection_factory, provider, cached_sources, configured_source, expected_source
):
    watchlist = create_watchlist(connection_factory, provider)
    with connection_factory() as connection, connection.begin():
        repositories = create_repositories(connection)
        for game_id, source in zip(("612", "128"), cached_sources, strict=False):
            repositories.games.save_observation(
                replace(provider.games[game_id], source=source), datetime.now(UTC)
            )
            repositories.watchlists.add_item(
                watchlist.id, game_id, Decimal("10.00"), steam_only=False
            )
    active_provider = Mock(source=configured_source)
    result = GetWatchlistSummaryHandler(connection_factory, active_provider).handle(
        GetWatchlistSummaryUseCase(watchlist.id)
    )
    assert result.source == expected_source
    assert result.total_items == result.priced_items == len(cached_sources)
    assert result.current_total == (Decimal("9.98") if cached_sources else Decimal("0.00"))
    assert result.model_dump(mode="json")["currentTotal"] == str(result.current_total)
    active_provider.get_game.assert_not_called()
    active_provider.search.assert_not_called()
