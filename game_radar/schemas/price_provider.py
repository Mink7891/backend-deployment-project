"""Pydantic-схемы данных, полученных от провайдера цен (CheapShark или mock)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProviderOffer(BaseModel):
    """Предложение магазина по игре."""

    model_config = ConfigDict(frozen=True)

    deal_id: str
    store_id: str
    price: Decimal
    retail_price: Decimal
    savings: Decimal


class ProviderGame(BaseModel):
    """Игра с текущими предложениями; в результатах поиска offers пустой."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    steam_app_id: str | None
    thumbnail_url: str | None
    offers: tuple[ProviderOffer, ...] = ()
    source: str
    cheapest_price: Decimal | None = None
