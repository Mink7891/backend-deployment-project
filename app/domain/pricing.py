from decimal import Decimal

from app.domain.entities import Game, Watchlist, WatchlistItem, WatchlistSummary


def best_price(game: Game, steam_only: bool = False) -> Decimal | None:
    return min(
        (offer.price for offer in game.offers if not steam_only or offer.store_id == "1"),
        default=None,
    )


def threshold_met(item: WatchlistItem) -> bool:
    price = best_price(item.game, item.steam_only)
    return price is not None and price <= item.target_price


def summarize(watchlist: Watchlist, source: str) -> WatchlistSummary:
    prices = [best_price(item.game, item.steam_only) for item in watchlist.items]
    available = [price for price in prices if price is not None]
    sources = {item.game.source for item in watchlist.items}
    if sources:
        source = next(iter(sources)) if len(sources) == 1 else "mixed"
    return WatchlistSummary(
        watchlist_id=watchlist.id,
        total_items=len(watchlist.items),
        priced_items=len(available),
        matched_count=sum(threshold_met(item) for item in watchlist.items),
        current_total=sum(available, Decimal("0.00")),
        currency="USD",
        source=source,
    )
