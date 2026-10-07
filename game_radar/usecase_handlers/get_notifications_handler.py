"""Хендлер GetNotificationsUseCase."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.errors import watchlist_not_found
from game_radar.mapping.watchlist_mapper import map_notification_response
from game_radar.repositories.database.notification_repository import NotificationRepository
from game_radar.repositories.database.watchlist_repository import WatchlistRepository
from game_radar.schemas.game_radar_api import NotificationResponse
from game_radar.usecases.watchlists import GetNotificationsUseCase


class GetNotificationsHandler:
    """Возвращает журнал достижения желаемой цены, новые записи первыми."""

    def __init__(
        self,
        watchlist_repo: WatchlistRepository,
        notification_repo: NotificationRepository,
    ) -> None:
        self.watchlist_repo = watchlist_repo
        self.notification_repo = notification_repo

    async def handle(
        self, usecase: GetNotificationsUseCase, session: AsyncSession
    ) -> list[NotificationResponse]:
        async with session.begin():
            if await self.watchlist_repo.get(session, usecase.watchlist_id) is None:
                raise watchlist_not_found()
            notifications = await self.notification_repo.get_by_watchlist(
                session, usecase.watchlist_id, usecase.limit, usecase.offset
            )

        return [map_notification_response(notification) for notification in notifications]
