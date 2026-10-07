"""Проверка порога цены и запись в журнал при его достижении."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from game_radar.database.models import NotificationModel, WatchlistItemModel
from game_radar.repositories.database.notification_repository import NotificationRepository
from game_radar.repositories.database.watchlist_item_repository import WatchlistItemRepository
from game_radar.services.pricing import PricingActions


class PriceAlertService:
    """Создаёт запись журнала только при переходе в состояние «порог достигнут»."""

    def __init__(
        self,
        item_repo: WatchlistItemRepository,
        notification_repo: NotificationRepository,
    ) -> None:
        self.item_repo = item_repo
        self.notification_repo = notification_repo

    async def evaluate(
        self, session: AsyncSession, item: WatchlistItemModel
    ) -> NotificationModel | None:
        price = PricingActions.best_price(item.game, item.steam_only)
        matched = price is not None and price <= item.target_price
        notification = None
        if matched and not item.alert_active:
            notification = await self.notification_repo.create(session, item, price)
        if matched != item.alert_active:
            await self.item_repo.set_alert_active(session, item.id, matched)
        return notification
