"""Агрегатор роутеров API v1."""

from __future__ import annotations

from fastapi import APIRouter

from game_radar.api.v1.endpoints.games import router as games_router
from game_radar.api.v1.endpoints.health import router as health_router
from game_radar.api.v1.endpoints.watchlists import router as watchlists_router

api_v1_router = APIRouter()

api_v1_router.include_router(health_router)
api_v1_router.include_router(games_router)
api_v1_router.include_router(watchlists_router)
