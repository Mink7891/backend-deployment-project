"""Pure mappings from CheapShark JSON into immutable provider data."""

from decimal import Decimal

from app.domain.entities import ProviderGame, ProviderOffer


def _price(value) -> Decimal:
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0 or amount > Decimal("9999999999.99"):
        raise ValueError("Invalid provider price")
    return amount.quantize(Decimal("0.01"))


def map_search(payload: object, limit: int) -> list[ProviderGame]:
    if not isinstance(payload, list):
        raise ValueError("Invalid search response")
    games = [
        ProviderGame(
            id=str(row["gameID"]),
            title=str(row["external"]),
            steam_app_id=str(row["steamAppID"]) if row.get("steamAppID") else None,
            thumbnail_url=row.get("thumb") or None,
            offers=(),
            source="cheapshark",
            cheapest_price=_price(row["cheapest"]),
        )
        for row in payload[:limit]
    ]
    if any(not game.id.isdigit() or len(game.id) > 32 for game in games):
        raise ValueError("Invalid provider game ID")
    return games


def map_game(payload: dict, game_id: str) -> ProviderGame:
    info = payload["info"]
    offers = tuple(
        ProviderOffer(
            deal_id=str(row["dealID"]),
            store_id=str(row["storeID"]),
            price=_price(row["price"]),
            retail_price=_price(row["retailPrice"]),
            savings=Decimal(str(row["savings"])).quantize(Decimal("0.000001")),
        )
        for row in payload["deals"]
    )
    if any(not offer.savings.is_finite() for offer in offers):
        raise ValueError("Invalid savings")
    return ProviderGame(
        id=game_id,
        title=str(info["title"]),
        steam_app_id=str(info["steamAppID"]) if info.get("steamAppID") else None,
        thumbnail_url=info.get("thumb") or None,
        offers=offers,
        source="cheapshark",
        cheapest_price=min((offer.price for offer in offers), default=None),
    )
