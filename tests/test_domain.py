from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from app.domain.entities import Game, Watchlist, WatchlistItem
from app.domain.pricing import best_price, summarize, threshold_met


def make_game(provider, game_id="612"):
    data = provider.get_game(game_id)
    return Game(
        id=data.id,
        title=data.title,
        steam_app_id=data.steam_app_id,
        thumbnail_url=data.thumbnail_url,
        offers=data.offers,
        source=data.source,
        cheapest_price=data.cheapest_price,
    )


def make_item(game, target="3.99", steam_only=True, item_id=1):
    return WatchlistItem(
        id=item_id,
        watchlist_id=1,
        game_id=game.id,
        target_price=Decimal(target),
        steam_only=steam_only,
        alert_active=False,
        created_at=datetime.now(UTC),
        game=game,
    )


def test_steam_filter_and_exact_threshold(provider):
    game = make_game(provider)
    assert best_price(game, steam_only=True) == Decimal("3.99")
    assert best_price(game, steam_only=False) == Decimal("2.99")
    assert threshold_met(make_item(game, "3.99")) is True
    assert threshold_met(make_item(game, "3.98")) is False
    assert threshold_met(make_item(game, "3.00", steam_only=False)) is True


def test_missing_steam_offer_does_not_count_as_free(provider):
    game = make_game(provider)
    game = replace(game, offers=tuple(offer for offer in game.offers if offer.store_id != "1"))
    assert best_price(game, steam_only=True) is None
    assert threshold_met(make_item(game, "9999.00")) is False
    summary = summarize(Watchlist(1, "Games", datetime.now(UTC), (make_item(game),)), "mock")
    assert summary.total_items == 1
    assert summary.priced_items == 0
    assert summary.matched_count == 0
    assert summary.current_total == Decimal("0.00")


def test_summary_uses_each_items_store_preference(provider):
    first = make_item(make_game(provider), target="4.00")
    second = make_item(make_game(provider, "128"), target="7.00", steam_only=False, item_id=2)
    summary = summarize(Watchlist(1, "Games", datetime.now(UTC), (first, second)), "mock")
    assert summary.current_total == Decimal("10.98")
    assert summary.priced_items == summary.matched_count == summary.total_items == 2
    assert summary.currency == "USD"


def test_empty_watchlist_has_zero_total():
    summary = summarize(Watchlist(1, "Empty", datetime.now(UTC)), "mock")
    assert summary.current_total == Decimal("0.00")
    assert summary.total_items == summary.priced_items == summary.matched_count == 0
