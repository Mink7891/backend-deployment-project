"""Агрегатор роутеров уровня модуля."""

from __future__ import annotations

from fastapi import APIRouter

from game_radar.api.v1.api_v1 import api_v1_router

game_radar_router = APIRouter()
game_radar_router.include_router(api_v1_router)
