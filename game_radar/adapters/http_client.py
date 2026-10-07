"""Базовый HTTP-адаптер."""

from __future__ import annotations

import httpx


class BaseHttpAdapter:
    """Общая настройка httpx-клиента для адаптеров внешних API."""

    def __init__(
        self,
        base_url: str,
        timeout: float,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = headers or {}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self.headers,
                follow_redirects=False,
            )
        return self._client
