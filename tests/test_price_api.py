from decimal import Decimal

import pytest

from game_radar.adapters.mock_price_api import MockPriceApi
from game_radar.errors import ServiceError
from game_radar.mapping.cheapshark_mapper import (
    map_cheapshark_game_to_provider_game,
    map_cheapshark_search_to_provider_games,
)


@pytest.mark.anyio
async def test_mock_api_search_and_details():
    api = MockPriceApi()
    found = await api.search(" lego ")
    assert [game.id for game in found] == ["612"]
    game = await api.get_game("612")
    assert {offer.price for offer in game.offers} == {Decimal("3.99"), Decimal("2.99")}


@pytest.mark.anyio
async def test_mock_api_unknown_game_is_404():
    with pytest.raises(ServiceError) as error:
        await MockPriceApi().get_game("999999")
    assert error.value.status == 404


def test_cheapshark_search_mapping():
    payload = [
        {"gameID": "612", "external": "LEGO Batman", "steamAppID": "21000", "cheapest": "2.99"}
    ]
    games = map_cheapshark_search_to_provider_games(payload, limit=20)
    assert games[0].id == "612"
    assert games[0].cheapest_price == Decimal("2.99")
    assert games[0].offers == ()


def test_cheapshark_details_mapping():
    payload = {
        "info": {"title": "LEGO Batman", "steamAppID": "21000"},
        "deals": [
            {
                "dealID": "deal",
                "storeID": "1",
                "price": "3.99",
                "retailPrice": "19.99",
                "savings": "80.04",
            }
        ],
    }
    game = map_cheapshark_game_to_provider_game(payload, "612")
    assert game.cheapest_price == Decimal("3.99")
    assert game.offers[0].store_id == "1"


@pytest.mark.parametrize("price", ["-1.00", "NaN", "10000000000.00"])
def test_cheapshark_invalid_price_is_rejected(price):
    payload = [{"gameID": "1", "external": "X", "cheapest": price}]
    with pytest.raises(ValueError):
        map_cheapshark_search_to_provider_games(payload, limit=20)
