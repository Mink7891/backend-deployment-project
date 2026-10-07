"""Офлайн-источник цен: вымышленные фиксированные цены без внешних запросов."""

from __future__ import annotations

from decimal import Decimal

from game_radar.config import settings
from game_radar.errors import game_not_found
from game_radar.schemas.price_provider import ProviderGame, ProviderOffer


class MockPriceApi:
    """Замена CheapShark для разработки и демонстрации (PRICE_SOURCE=mock)."""

    source = "mock"

    def __init__(self) -> None:
        self.games: dict[str, ProviderGame] = {}
        # game_id, название, Steam App ID, цена Steam, цена магазина 7, розничная цена
        for game_id, title, steam_id, steam_price, other_price, retail in (
            ("612", "LEGO Batman", "21000", "3.99", "2.99", "19.99"),
            ("128", "BioShock", "7670", "7.49", "6.99", "19.99"),
            ("101", "Portal 2", "620", "4.99", "3.99", "9.99"),
        ):
            offers = tuple(
                ProviderOffer(
                    deal_id=f"mock-{game_id}-{store_id}",
                    store_id=store_id,
                    price=Decimal(price),
                    retail_price=Decimal(retail),
                    savings=((1 - Decimal(price) / Decimal(retail)) * 100).quantize(
                        Decimal("0.000001")
                    ),
                )
                for store_id, price in ((settings.STEAM_STORE_ID, steam_price), ("7", other_price))
            )
            self.games[game_id] = ProviderGame(
                id=game_id,
                title=title,
                steam_app_id=steam_id,
                thumbnail_url=None,
                offers=offers,
                source=self.source,
                cheapest_price=min(offer.price for offer in offers),
            )

    async def search(self, query: str, limit: int = 20) -> list[ProviderGame]:
        query = query.casefold().strip()
        return [game for game in self.games.values() if query in game.title.casefold()][:limit]

    async def get_game(self, game_id: str) -> ProviderGame:
        game = self.games.get(game_id)
        if game is None:
            raise game_not_found()
        return game
