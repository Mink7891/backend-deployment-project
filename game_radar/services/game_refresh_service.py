"""Обновление цен игры с учётом кеша и проверкой порогов всех её позиций."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.adapters.ports import PriceApi
from game_radar.database.models import GameModel, NotificationModel
from game_radar.repositories.database.game_repository import GameRepository
from game_radar.repositories.database.price_snapshot_repository import PriceSnapshotRepository
from game_radar.repositories.database.watchlist_item_repository import WatchlistItemRepository
from game_radar.services.price_alert_service import PriceAlertService


@dataclass(frozen=True)
class GameRefreshResult:
    game: GameModel
    refreshed: bool
    notifications: tuple[NotificationModel, ...]


class GameRefreshService:
    """Транзакцией управляет вызывающий хендлер."""

    def __init__(
        self,
        price_api: PriceApi,
        game_repo: GameRepository,
        snapshot_repo: PriceSnapshotRepository,
        item_repo: WatchlistItemRepository,
        alert_service: PriceAlertService,
        cache_ttl_seconds: int,
    ) -> None:
        self.price_api = price_api
        self.game_repo = game_repo
        self.snapshot_repo = snapshot_repo
        self.item_repo = item_repo
        self.alert_service = alert_service
        self.cache_ttl_seconds = cache_ttl_seconds

    async def refresh(self, session: AsyncSession, game_id: str) -> GameRefreshResult:
        now = datetime.now(UTC)
        game = await self.game_repo.get(session, game_id, for_update=True)
        cached = (
            game is not None
            and game.source == self.price_api.source
            and game.last_refreshed_at is not None
            and (now - game.last_refreshed_at).total_seconds() < self.cache_ttl_seconds
        )
        if not cached:
            data = await self.price_api.get_game(game_id)
            game = await self.game_repo.replace_offers(session, data, now)
            # Снимок истории пишется только при реальном получении цен.
            await self.snapshot_repo.create_many(session, data, now)

        notifications = []
        for item in await self.item_repo.get_for_game(session, game_id, for_update=True):
            notification = await self.alert_service.evaluate(session, item)
            if notification is not None:
                notifications.append(notification)
        return GameRefreshResult(game, not cached, tuple(notifications))
