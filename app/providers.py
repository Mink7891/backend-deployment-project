"""Bounded CheapShark integration and an entirely offline demonstration provider."""

import threading
import time
from collections import OrderedDict
from decimal import Decimal, InvalidOperation
from functools import lru_cache

import httpx

from app.application.exceptions import GameNotFound, ProviderUnavailable
from app.application.ports import PriceProvider
from app.config import Settings, get_settings
from app.domain.entities import ProviderGame, ProviderOffer


def _price(value) -> Decimal:
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0 or amount > Decimal("9999999999.99"):
        raise ValueError("Invalid provider price")
    return amount.quantize(Decimal("0.01"))


class MockProvider:
    """Fictional fixed prices. This provider never constructs an HTTP client."""

    source = "mock"

    def __init__(self):
        self.games: dict[str, ProviderGame] = {}
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
                for store_id, price in (("1", steam_price), ("7", other_price))
            )
            self.games[game_id] = ProviderGame(
                id=game_id,
                title=title,
                steam_app_id=steam_id,
                thumbnail_url=None,
                offers=offers,
                source="mock",
                cheapest_price=min(offer.price for offer in offers),
            )

    def search(self, query: str, limit: int = 20) -> list[ProviderGame]:
        query = query.casefold().strip()
        return [game for game in self.games.values() if query in game.title.casefold()][:limit]

    def get_game(self, game_id: str) -> ProviderGame:
        try:
            return self.games[game_id]
        except KeyError as exc:
            raise GameNotFound(game_id) from exc


class CheapSharkProvider:
    source = "cheapshark"

    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = threading.Lock()
        self._last_request_at = 0.0
        self._blocked_until = 0.0
        self._cache_lock = threading.Lock()
        self._search_cache: OrderedDict[tuple[str, int], tuple[float, list[ProviderGame]]] = (
            OrderedDict()
        )

    def _request(self, params: dict) -> object:
        # No user input is used as a URL. Redirects are deliberately disabled.
        if not self._lock.acquire(timeout=1):
            raise ProviderUnavailable("Price provider is busy; retry shortly", retry_after=2)
        try:
            now = time.monotonic()
            if now < self._blocked_until:
                raise ProviderUnavailable(
                    "Price provider rate limit is active",
                    retry_after=max(1, int(self._blocked_until - now)),
                )
            remaining = 1 - (now - self._last_request_at)
            if remaining > 0:
                time.sleep(remaining)
            self._last_request_at = time.monotonic()
            try:
                with httpx.Client(
                    timeout=httpx.Timeout(10, connect=3),
                    follow_redirects=False,
                    trust_env=False,
                    headers={"User-Agent": self.settings.cheapshark_user_agent},
                ) as client:
                    response = client.get(
                        f"{self.settings.cheapshark_base_url}/games", params=params
                    )
                if response.status_code == 429:
                    try:
                        delay = min(3600, max(1, int(response.headers.get("Retry-After", "60"))))
                    except ValueError:
                        delay = 60
                    self._blocked_until = time.monotonic() + delay
                    raise ProviderUnavailable(
                        "Price provider rate limit reached", retry_after=delay
                    )
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                # Do not echo upstream response bodies or URLs into the public API.
                raise ProviderUnavailable() from exc
        finally:
            self._lock.release()

    def search(self, query: str, limit: int = 20) -> list[ProviderGame]:
        key = (query.casefold().strip(), limit)
        with self._cache_lock:
            cached = self._search_cache.get(key)
        if cached and time.monotonic() - cached[0] < self.settings.refresh_min_interval_seconds:
            return list(cached[1])
        payload = self._request({"title": query, "limit": limit})
        try:
            if not isinstance(payload, list):
                raise ValueError("Invalid search response")
            games = [
                ProviderGame(
                    id=str(row["gameID"]),
                    title=str(row["external"]),
                    steam_app_id=str(row["steamAppID"]) if row.get("steamAppID") else None,
                    thumbnail_url=row.get("thumb") or None,
                    offers=(),
                    source=self.source,
                    cheapest_price=_price(row["cheapest"]),
                )
                for row in payload[:limit]
            ]
            if any(not game.id.isdigit() or len(game.id) > 32 for game in games):
                raise ValueError("Invalid provider game ID")
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise ProviderUnavailable("Price provider returned invalid game data") from exc
        with self._cache_lock:
            self._search_cache[key] = (time.monotonic(), games)
            self._search_cache.move_to_end(key)
            while len(self._search_cache) > 256:
                self._search_cache.popitem(last=False)
        return list(games)

    def get_game(self, game_id: str) -> ProviderGame:
        payload = self._request({"id": game_id})
        if payload in (None, [], {}):
            raise GameNotFound(game_id)
        try:
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
                source=self.source,
                cheapest_price=min((offer.price for offer in offers), default=None),
            )
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise ProviderUnavailable("Price provider returned invalid game data") from exc


@lru_cache
def get_provider() -> PriceProvider:
    settings = get_settings()
    if settings.price_source == "mock":
        return MockProvider()
    return CheapSharkProvider(settings)
