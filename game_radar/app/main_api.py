"""Агрегатор роутеров верхнего уровня."""

from __future__ import annotations

from fastapi import APIRouter

from game_radar.game_radar_api import game_radar_router

main_router = APIRouter()
main_router.include_router(game_radar_router)
