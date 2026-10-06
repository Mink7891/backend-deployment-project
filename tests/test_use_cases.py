"""Business scenarios invoked directly, without FastAPI or HTTP."""

from dataclasses import replace
from decimal import Decimal

import pytest

from app.application.exceptions import Conflict, NotFound, ProviderUnavailable
from app.application.use_cases import (
    AddWatchlistItem,
    CreateWatchlist,
    GetGame,
    GetNotifications,
    GetPriceHistory,
    GetWatchlistSummary,
    RefreshAllWatchedGames,
    RefreshWatchlist,
    SearchGames,
    UpdateWatchlistItem,
)
from app.infrastructure.repositories import SqlAlchemyUnitOfWork


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


def test_get_game_cache_skips_provider_and_history_duplicates(session, provider):
    uow = SqlAlchemyUnitOfWork(session)
    counting = CountingProvider(provider)
    first = GetGame(uow, counting, 300).execute("612")
    second = GetGame(uow, counting, 300).execute("612")
    assert first.last_refreshed_at == second.last_refreshed_at
    assert counting.calls == ["612"]
    history = GetPriceHistory(uow).execute("612")
    assert len(history) == 2
    assert {row.store_id for row in history} == {"1", "7"}


def test_search_metadata_does_not_create_price_observations(session, provider):
    uow = SqlAlchemyUnitOfWork(session)
    found = SearchGames(uow, provider).execute("lego")
    assert [game.id for game in found] == ["612"]
    assert GetPriceHistory(uow).execute("612") == []
    GetGame(uow, provider, 300).execute("612")
    assert len(GetPriceHistory(uow).execute("612")) == 2


def test_cached_refresh_deduplicates_notifications(session, provider):
    uow = SqlAlchemyUnitOfWork(session)
    watchlist = CreateWatchlist(uow).execute("Games")
    AddWatchlistItem(uow, provider, 300).execute(watchlist.id, "612", Decimal("3.99"))
    result = RefreshWatchlist(uow, provider, 300).execute(watchlist.id)
    assert result.refreshed_games == 0
    assert result.checked_items == result.matched_count == 1
    assert result.notifications_created == 0
    events = GetNotifications(uow).execute(watchlist.id)
    assert len(events) == 1
    assert events[0].observed_price == events[0].target_price == Decimal("3.99")


def test_notification_only_on_reentering_price_threshold(session, provider):
    uow = SqlAlchemyUnitOfWork(session)
    watchlist = CreateWatchlist(uow).execute("Games")
    item = AddWatchlistItem(uow, provider, 0).execute(watchlist.id, "612", Decimal("4.00"))
    original = provider.games["612"]
    expensive = tuple(replace(offer, price=Decimal("8.00")) for offer in original.offers)
    provider.games["612"] = replace(original, offers=expensive, cheapest_price=Decimal("8.00"))
    down = RefreshWatchlist(uow, provider, 0).execute(watchlist.id)
    assert down.matched_count == down.notifications_created == 0
    assert len(GetNotifications(uow).execute(watchlist.id)) == 1
    provider.games["612"] = original
    up = RefreshWatchlist(uow, provider, 0).execute(watchlist.id)
    assert up.matched_count == up.notifications_created == 1
    assert len(GetNotifications(uow).execute(watchlist.id)) == 2
    assert uow.watchlists.find_item(watchlist.id, item.id).alert_active is True
    assert len(GetPriceHistory(uow).execute("612")) == 6


def test_changing_store_preference_recalculates_threshold(session, provider):
    uow = SqlAlchemyUnitOfWork(session)
    watchlist = CreateWatchlist(uow).execute("Games")
    item = AddWatchlistItem(uow, provider, 300).execute(watchlist.id, "612", Decimal("3.00"))
    assert item.alert_active is False
    updated = UpdateWatchlistItem(uow, provider, 300).execute(
        watchlist.id, item.id, steam_only=False
    )
    assert updated.alert_active is True
    assert GetWatchlistSummary(uow, "mock").execute(watchlist.id).current_total == Decimal("2.99")
    assert len(GetNotifications(uow).execute(watchlist.id)) == 1


def test_duplicate_or_missing_watchlist_fails_before_external_lookup(session, provider):
    uow = SqlAlchemyUnitOfWork(session)
    counting = CountingProvider(provider)
    operation = AddWatchlistItem(uow, counting, 300)
    with pytest.raises(NotFound):
        operation.execute(9999, "612", Decimal("4.00"))
    assert counting.calls == []
    watchlist = CreateWatchlist(uow).execute("Games")
    operation.execute(watchlist.id, "612", Decimal("4.00"))
    with pytest.raises(Conflict):
        operation.execute(watchlist.id, "612", Decimal("4.00"))
    assert counting.calls == ["612"]


def test_worker_refreshes_shared_game_once_and_updates_both_watchlists(session, provider):
    uow = SqlAlchemyUnitOfWork(session)
    for name in ["First", "Second"]:
        watchlist = CreateWatchlist(uow).execute(name)
        AddWatchlistItem(uow, provider, 300).execute(watchlist.id, "612", Decimal("2.00"))
    counting = CountingProvider(provider)
    result = RefreshAllWatchedGames(uow, counting, 0).execute()
    assert counting.calls == ["612"]
    assert result.refreshed_games == 1
    assert result.checked_items == 2
    assert result.matched_count == result.notifications_created == 0


def test_worker_continues_after_provider_failure(session, provider):
    uow = SqlAlchemyUnitOfWork(session)
    watchlist = CreateWatchlist(uow).execute("Games")
    add = AddWatchlistItem(uow, provider, 300)
    add.execute(watchlist.id, "612", Decimal("4.00"))
    add.execute(watchlist.id, "128", Decimal("8.00"))

    class PartialFailure(CountingProvider):
        def get_game(self, game_id):
            if game_id == "128":
                raise ProviderUnavailable()
            return super().get_game(game_id)

    operation = RefreshAllWatchedGames(uow, PartialFailure(provider), 0)
    result = operation.execute()
    assert operation.failed_games == 1
    assert result.refreshed_games == result.checked_items == 1
    assert len(GetNotifications(uow).execute(watchlist.id)) == 2
