"""Авторизация по общему ключу из заголовка X-API-Key."""

from __future__ import annotations

import secrets

from fastapi import Depends
from fastapi.security import APIKeyHeader

from game_radar.config import settings
from game_radar.errors import unauthorized

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str | None = Depends(api_key_header)) -> None:
    """FastAPI-зависимость: пропускает запрос только с правильным ключом."""
    expected = settings.API_KEY
    if not expected or key is None or not secrets.compare_digest(key.encode(), expected.encode()):
        raise unauthorized()
