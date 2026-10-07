"""Расчёт лучшей цены, достижения порога и сводки списка. Без состояния и I/O."""

from __future__ import annotations

from decimal import Decimal

from game_radar.database.models import GameModel, WatchlistItemModel, WatchlistModel

STEAM_STORE_ID = "1"
CURRENCY = "USD"


class PricingActions:
    """Чистые функции предметной области цен."""

    @staticmethod
    def best_price(game: GameModel, steam_only: bool = False) -> Decimal | None:
        """Минимальная цена среди предложений; при steam_only — только магазин Steam."""
        return min(
            (
                offer.price
                for offer in game.offers
                if not steam_only or offer.store_id == STEAM_STORE_ID
            ),
            default=None,
        )

    @staticmethod
    def threshold_met(item: WatchlistItemModel) -> bool:
        """Достигнута ли желаемая цена позиции списка."""
        price = PricingActions.best_price(item.game, item.steam_only)
        return price is not None and price <= item.target_price

    @staticmethod
    def summary_source(watchlist: WatchlistModel, configured_source: str) -> str:
        """Источник цен сводки: общий источник игр, `mixed` или текущая настройка."""
        sources = {item.game.source for item in watchlist.items}
        if not sources:
            return configured_source
        return next(iter(sources)) if len(sources) == 1 else "mixed"
