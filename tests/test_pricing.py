from datetime import UTC, datetime
from decimal import Decimal

from game_radar.database.models import GameModel, OfferModel, WatchlistItemModel, WatchlistModel
from game_radar.mapping.watchlist_mapper import map_summary_response
from game_radar.services.pricing import PricingActions


def make_game(steam_price="3.99", other_price="2.99", source="mock"):
    return GameModel(
        id="612",
        title="LEGO Batman",
        source=source,
        offers=[
            OfferModel(store_id="1", deal_id="steam", price=Decimal(steam_price)),
            OfferModel(store_id="7", deal_id="other", price=Decimal(other_price)),
        ],
    )


def make_item(game, target="4.00", steam_only=True):
    return WatchlistItemModel(
        id=1,
        watchlist_id=1,
        game_id=game.id,
        game=game,
        target_price=Decimal(target),
        steam_only=steam_only,
        alert_active=False,
        created_at=datetime.now(UTC),
    )


def test_best_price_respects_steam_filter():
    game = make_game()
    assert PricingActions.best_price(game) == Decimal("2.99")
    assert PricingActions.best_price(game, steam_only=True) == Decimal("3.99")


def test_best_price_without_steam_offer_is_none():
    game = make_game()
    game.offers = [offer for offer in game.offers if offer.store_id != "1"]
    assert PricingActions.best_price(game, steam_only=True) is None


def test_threshold_is_inclusive():
    game = make_game()
    assert PricingActions.threshold_met(make_item(game, "3.99")) is True
    assert PricingActions.threshold_met(make_item(game, "3.98")) is False
    assert PricingActions.threshold_met(make_item(game, "3.00", steam_only=False)) is True


def test_summary_totals_and_source():
    watchlist = WatchlistModel(
        id=1,
        name="Games",
        created_at=datetime.now(UTC),
        items=[
            make_item(make_game(), "4.00"),
            make_item(make_game("9.99", "8.99", source="cheapshark"), "5.00", steam_only=False),
        ],
    )
    summary = map_summary_response(watchlist, "mock")
    assert summary.current_total == Decimal("12.98")
    assert summary.matched_count == 1
    assert summary.total_items == summary.priced_items == 2
    assert summary.source == "mixed"


def test_empty_summary_uses_configured_source():
    watchlist = WatchlistModel(id=1, name="Empty", created_at=datetime.now(UTC), items=[])
    summary = map_summary_response(watchlist, "cheapshark")
    assert summary.current_total == Decimal("0.00")
    assert summary.source == "cheapshark"
