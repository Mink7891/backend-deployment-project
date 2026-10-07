"""Фоновый worker: периодически обновляет цены всех отслеживаемых игр.

Запускается отдельным процессом (`python -m game_radar.worker`) и вызывает
тот же UseCase через тот же диспетчер, что и HTTP API.
"""

from __future__ import annotations

import asyncio
import logging

from game_radar.config import settings
from game_radar.database.session import async_session_factory, close_db_session
from game_radar.dependencies.dispatcher_register import init_dispatcher
from game_radar.middleware.logging import configure_logging
from game_radar.usecases.refresh import RefreshAllWatchedGamesUseCase

logger = logging.getLogger("game_radar.worker")

async def run() -> None:
    dispatcher = init_dispatcher()
    try:
        while True:
            try:
                async with async_session_factory() as session:
                    result = await dispatcher.dispatch(RefreshAllWatchedGamesUseCase(), session)
                logger.info(
                    "refresh_cycle_finished",
                    extra={"extra_fields": result.model_dump()},
                )
            except Exception:
                # Временный сбой БД не должен останавливать worker.
                logger.exception("refresh_cycle_failed")
            await asyncio.sleep(settings.REFRESH_INTERVAL_SECONDS)
    finally:
        await close_db_session()


def main() -> None:
    configure_logging(settings.LOG_LEVEL)
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
