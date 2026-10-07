from urllib.parse import quote, unquote

from app.domain.entities import Game, Watchlist, WatchlistItem
from app.domain.pricing import best_price, threshold_met
from app.schemas import (
    GameCard,
    GameDetails,
    ItemResponse,
    OfferResponse,
    WatchlistDetails,
)


def present_game(game: Game) -> GameDetails:
    return GameDetails(
        **GameCard.model_validate(game).model_dump(),
        last_refreshed_at=game.last_refreshed_at,
        best_price=best_price(game),
        offers=[
            OfferResponse(
                deal_id=offer.deal_id,
                store_id=offer.store_id,
                store_name="Steam" if offer.store_id == "1" else f"Store {offer.store_id}",
                price=offer.price,
                retail_price=offer.retail_price,
                savings=offer.savings,
                deal_url=(
                    "https://www.cheapshark.com/redirect?dealID="
                    + quote(unquote(offer.deal_id), safe="")
                )
                if game.source == "cheapshark"
                else None,
            )
            for offer in game.offers
        ],
    )


def present_item(item: WatchlistItem) -> ItemResponse:
    return ItemResponse(
        id=item.id,
        game_id=item.game_id,
        target_price=item.target_price,
        steam_only=item.steam_only,
        created_at=item.created_at,
        game=GameCard.model_validate(item.game),
        current_price=best_price(item.game, item.steam_only),
        threshold_met=threshold_met(item),
    )


def present_watchlist(watchlist: Watchlist) -> WatchlistDetails:
    return WatchlistDetails(
        id=watchlist.id,
        name=watchlist.name,
        created_at=watchlist.created_at,
        items=[present_item(item) for item in watchlist.items],
    )
