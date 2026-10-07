"""Маппинг игр, предложений и истории цен в ответы API."""

from __future__ import annotations

from urllib.parse import quote, unquote

from game_radar.config import settings
from game_radar.database.models import GameModel, OfferModel, PriceSnapshotModel
from game_radar.schemas.game_radar_api import (
    GameCard,
    GameDetails,
    OfferResponse,
    SnapshotResponse,
)
from game_radar.schemas.price_provider import ProviderGame
from game_radar.services.pricing import PricingActions


def map_game_card(game: GameModel) -> GameCard:
    return GameCard.model_validate(game)


def map_offer_response(game: GameModel, offer: OfferModel) -> OfferResponse:
    deal_url = None
    if game.source == "cheapshark":
        deal_url = "https://www.cheapshark.com/redirect?dealID=" + quote(
            unquote(offer.deal_id), safe=""
        )
    return OfferResponse(
        deal_id=offer.deal_id,
        store_id=offer.store_id,
        store_name="Steam"
        if offer.store_id == settings.STEAM_STORE_ID
        else f"Store {offer.store_id}",
        price=offer.price,
        retail_price=offer.retail_price,
        savings=offer.savings,
        deal_url=deal_url,
    )


def map_game_details(game: GameModel) -> GameDetails:
    return GameDetails(
        **map_game_card(game).model_dump(),
        last_refreshed_at=game.last_refreshed_at,
        best_price=PricingActions.best_price(game),
        offers=[map_offer_response(game, offer) for offer in game.offers],
    )


def map_snapshot_response(snapshot: PriceSnapshotModel) -> SnapshotResponse:
    return SnapshotResponse.model_validate(snapshot)


def map_game_row(game: ProviderGame) -> dict[str, object]:
    """Данные провайдера → значения строки таблицы games."""
    return {
        "title": game.title,
        "steam_app_id": game.steam_app_id,
        "thumbnail_url": game.thumbnail_url,
        "source": game.source,
        "cheapest_price": game.cheapest_price,
    }


def map_offer_rows(game: ProviderGame) -> list[dict[str, object]]:
    """Предложения провайдера → строки таблицы offers."""
    return [
        {
            "game_id": game.id,
            "deal_id": offer.deal_id,
            "store_id": offer.store_id,
            "price": offer.price,
            "retail_price": offer.retail_price,
            "savings": offer.savings,
        }
        for offer in game.offers
    ]
