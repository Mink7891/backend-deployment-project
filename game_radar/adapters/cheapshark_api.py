"""HTTP-адаптер CheapShark API (https://apidocs.cheapshark.com/)."""

from __future__ import annotations

import logging
from decimal import InvalidOperation

import httpx

from game_radar.adapters.http_client import BaseHttpAdapter
from game_radar.config import settings
from game_radar.errors import game_not_found, price_provider_unavailable
from game_radar.mapping.cheapshark_mapper import (
    map_cheapshark_game_to_provider_game,
    map_cheapshark_search_to_provider_games,
)
from game_radar.schemas.price_provider import ProviderGame

logger = logging.getLogger(__name__)


class CheapSharkApi(BaseHttpAdapter):
    """Адаптер CheapShark API.

    Эндпоинты: GET /games?title=... (поиск), GET /games?id=... (предложения игры).
    """

    source = "cheapshark"

    def __init__(self) -> None:
        super().__init__(
            settings.CHEAPSHARK_BASE_URL,
            timeout=settings.CHEAPSHARK_TIMEOUT,
            headers={"User-Agent": settings.CHEAPSHARK_USER_AGENT},
        )

    async def _get_games(self, params: dict[str, object]) -> object:
        try:
            client = await self._get_client()
            response = await client.get("/games", params=params)
        except httpx.HTTPError as exc:
            logger.error(
                "CheapShark request failed",
                extra={"extra_fields": {"error_type": type(exc).__name__}},
            )
            raise price_provider_unavailable() from None

        if response.status_code >= 400:
            logger.error(
                "CheapShark request unavailable",
                extra={"extra_fields": {"status_code": response.status_code}},
            )
            raise price_provider_unavailable()
        try:
            return response.json()
        except ValueError:
            raise price_provider_unavailable() from None

    async def search(self, query: str, limit: int = 20) -> list[ProviderGame]:
        payload = await self._get_games({"title": query, "limit": limit})
        try:
            return map_cheapshark_search_to_provider_games(payload, limit)
        except (KeyError, TypeError, ValueError, InvalidOperation):
            raise price_provider_unavailable() from None

    async def get_game(self, game_id: str) -> ProviderGame:
        payload = await self._get_games({"id": game_id})
        if payload in (None, [], {}):
            raise game_not_found()
        try:
            return map_cheapshark_game_to_provider_game(payload, game_id)
        except (KeyError, TypeError, ValueError, InvalidOperation):
            raise price_provider_unavailable() from None
