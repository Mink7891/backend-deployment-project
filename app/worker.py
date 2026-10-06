"""Periodic refresh worker; shares application use cases with the HTTP API."""

import logging
import os
import signal
import threading
import time
from pathlib import Path

from app.application.use_cases import RefreshAllWatchedGames
from app.config import get_settings
from app.db import SessionLocal
from app.infrastructure.repositories import SqlAlchemyUnitOfWork
from app.providers import get_provider

logger = logging.getLogger(__name__)
HEARTBEAT_PATH = Path(os.environ.get("WORKER_HEARTBEAT_PATH", "/tmp/worker-heartbeat"))


def touch_heartbeat() -> None:
    HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_PATH.write_text(str(time.time()), encoding="utf-8")


def refresh_once(should_stop=None):
    settings = get_settings()
    with SessionLocal() as session:
        use_case = RefreshAllWatchedGames(
            SqlAlchemyUnitOfWork(session),
            get_provider(),
            settings.refresh_min_interval_seconds,
            should_stop=should_stop,
        )
        result = use_case.execute()
        logger.info(
            "Refresh cycle: games=%s checked=%s matched=%s notifications=%s failed=%s source=%s",
            result.refreshed_games,
            result.checked_items,
            result.matched_count,
            result.notifications_created,
            use_case.failed_games,
            settings.price_source,
        )
        return result


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    stop_event = threading.Event()

    def stop(signum, frame):
        stop_event.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    touch_heartbeat()

    def keep_heartbeat_alive():
        while not stop_event.wait(30):
            touch_heartbeat()

    # A long refresh batch must not make an otherwise live worker fail its healthcheck.
    threading.Thread(target=keep_heartbeat_alive, daemon=True).start()
    while not stop_event.is_set():
        started = time.monotonic()
        try:
            refresh_once(should_stop=stop_event.is_set)
        except Exception as exc:
            # Leave the process alive for transient DB failures; avoid logging credentials.
            logger.error(
                "Refresh cycle failed (%s); retrying at the next interval", type(exc).__name__
            )
        deadline = started + settings.refresh_interval_seconds
        stop_event.wait(max(0, deadline - time.monotonic()))
        touch_heartbeat()


if __name__ == "__main__":
    main()
