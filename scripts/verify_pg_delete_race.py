"""Deterministic PostgreSQL refresh/delete race against temporary owned records.

Run with the application environment and dependencies. No external provider is used.
Exit 0: overlapping handlers succeeded; 1: handler/cleanup failure; 2: inconclusive.
Only exception class names and SQLSTATE values are printed, never exception text.
The success oracle requires a protected parent before DELETE starts and zero owned
watchlists/items/notifications after both handlers commit.
"""

import json
import threading
import time
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import delete, func, select, text

from app import models
from app.db import engine
from app.domain.entities import ProviderGame, ProviderOffer
from app.repositories import create_repositories
from app.usecase_handlers import DeleteWatchlistHandler, GetGameHandler
from app.usecases import DeleteWatchlistUseCase, GetGameUseCase


def safe_failure(exc):
    original = getattr(exc, "orig", None)
    return {
        "ok": False,
        "exception_type": type(exc).__name__,
        "sqlstate": getattr(original, "sqlstate", None),
    }


def bounded_repositories(connection):
    connection.execute(text("SET LOCAL lock_timeout = '8s'"))
    connection.execute(text("SET LOCAL statement_timeout = '10s'"))
    return create_repositories(connection)


def main():
    report = {"scenario": "refresh_game_vs_delete_watchlist", "cleanup": False}
    if engine.dialect.name != "postgresql":
        report["inconclusive"] = "PostgreSQL is required"
        print(json.dumps(report, sort_keys=True))
        return 2

    marker = f"owned-delete-race-{uuid4().hex}"
    game_id = "9" + str(uuid4().int % (10**31)).zfill(31)
    game = ProviderGame(
        id=game_id,
        title=marker,
        steam_app_id=None,
        thumbnail_url=None,
        source="mock",
        cheapest_price=Decimal("3.00"),
        offers=(
            ProviderOffer(
                deal_id=marker,
                store_id="1",
                price=Decimal("3.00"),
                retail_price=Decimal("4.00"),
                savings=Decimal("25.000000"),
            ),
        ),
    )

    class OfflineProvider:
        source = "mock"

        def get_game(self, requested_id):
            if requested_id != game_id:
                raise AssertionError("Only the owned game may be refreshed")
            return game

    provider = OfflineProvider()
    locked_items = threading.Event()
    release_refresh = threading.Event()
    pids = {}
    outcomes = {}
    watchlist_id = None
    seeded = False
    threads = []

    @contextmanager
    def connection_factory(role):
        with engine.connect() as connection:
            # Reading the driver's PID does not begin a SQLAlchemy transaction.
            pids[role] = connection.connection.driver_connection.info.backend_pid
            yield connection

    def refresh_repositories(connection):
        actual = bounded_repositories(connection)

        class PausedWatchlists:
            def __getattr__(self, name):
                return getattr(actual.watchlists, name)

            def items_for_game(self, requested_id, *, lock=False):
                items = actual.watchlists.items_for_game(requested_id, lock=lock)
                if requested_id == game_id and lock:
                    locked_items.set()
                    if not release_refresh.wait(6):
                        raise TimeoutError("Refresh overlap was not released")
                return items

        return SimpleNamespace(games=actual.games, watchlists=PausedWatchlists())

    def refresh():
        try:
            GetGameHandler(
                lambda: connection_factory("refresh"),
                provider,
                cache_ttl_seconds=0,
                repository_factory=refresh_repositories,
            ).handle(GetGameUseCase(game_id))
            outcomes["refresh"] = {"ok": True}
        except Exception as exc:
            outcomes["refresh"] = safe_failure(exc)

    def remove():
        try:
            DeleteWatchlistHandler(
                lambda: connection_factory("delete"),
                provider,
                repository_factory=bounded_repositories,
            ).handle(DeleteWatchlistUseCase(watchlist_id))
            outcomes["delete"] = {"ok": True}
        except Exception as exc:
            outcomes["delete"] = safe_failure(exc)

    try:
        with engine.begin() as connection:
            repositories = bounded_repositories(connection)
            if repositories.games.get(game_id) is not None:
                raise RuntimeError("Synthetic ID collision")
            initial_game = replace(
                game,
                cheapest_price=Decimal("8.00"),
                offers=(
                    replace(
                        game.offers[0],
                        price=Decimal("8.00"),
                        retail_price=Decimal("10.00"),
                        savings=Decimal("20.000000"),
                    ),
                ),
            )
            repositories.games.save_observation(initial_game, datetime.now(UTC))
            watchlist = repositories.watchlists.create(marker)
            watchlist_id = watchlist.id
            # Initially above target; the offline provider lowers it to INSERT a notification.
            repositories.watchlists.add_item(
                watchlist_id, game_id, Decimal("5.00"), steam_only=True
            )
        seeded = True

        refresh_thread = threading.Thread(target=refresh, daemon=True)
        threads.append(refresh_thread)
        refresh_thread.start()
        if not locked_items.wait(3):
            report["inconclusive"] = "Refresh did not reach the owned item locks"
        else:
            # An independent FOR UPDATE NOWAIT must conflict with refresh's parent
            # KEY SHARE before DELETE begins. This distinguishes the repaired order.
            try:
                with engine.begin() as probe:
                    probe.execute(text("SET LOCAL statement_timeout = '2s'"))
                    probe.execute(
                        select(models.watchlists.c.id)
                        .where(models.watchlists.c.id == watchlist_id)
                        .with_for_update(nowait=True)
                    ).all()
                report["parent_protected_before_delete"] = False
            except Exception as exc:
                if safe_failure(exc)["sqlstate"] != "55P03":
                    raise
                report["parent_protected_before_delete"] = True
            delete_thread = threading.Thread(target=remove, daemon=True)
            threads.append(delete_thread)
            delete_thread.start()
            deadline = time.monotonic() + 3
            blocked = False
            while time.monotonic() < deadline:
                delete_pid = pids.get("delete")
                refresh_pid = pids.get("refresh")
                if delete_pid and refresh_pid:
                    with engine.connect() as monitor:
                        monitor.execute(text("SET LOCAL statement_timeout = '2s'"))
                        blockers = monitor.scalar(select(func.pg_blocking_pids(delete_pid)))
                    if refresh_pid in blockers:
                        blocked = True
                        break
                if "delete" in outcomes:
                    break
                time.sleep(0.05)
            report["delete_blocked_by_refresh"] = blocked
            if not blocked:
                report["inconclusive"] = "DELETE did not wait for the paused refresh"
        release_refresh.set()
        for thread in threads:
            thread.join(timeout=12)
        if any(thread.is_alive() for thread in threads):
            report["inconclusive"] = "A handler did not finish within its SQL timeout"
        else:
            with engine.connect() as connection:
                counts = {
                    "watchlists": connection.scalar(
                        select(func.count())
                        .select_from(models.watchlists)
                        .where(models.watchlists.c.id == watchlist_id)
                    ),
                    "items": connection.scalar(
                        select(func.count())
                        .select_from(models.watchlist_items)
                        .where(models.watchlist_items.c.watchlist_id == watchlist_id)
                    ),
                    "notifications": connection.scalar(
                        select(func.count())
                        .select_from(models.notifications)
                        .where(models.notifications.c.watchlist_id == watchlist_id)
                    ),
                }
            report["owned_counts_before_cleanup"] = counts
            report["successful_delete_left_no_owned_rows"] = all(
                count == 0 for count in counts.values()
            )
            report["consistent_after_rollback"] = counts["notifications"] <= 1 and (
                counts["watchlists"] == 1 or counts["items"] == counts["notifications"] == 0
            )
    except Exception as exc:
        report["setup_or_monitor_failure"] = safe_failure(exc)
    finally:
        release_refresh.set()
        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=12)
        report["handlers"] = outcomes
        report["deadlock_confirmed"] = any(
            outcome.get("sqlstate") == "40P01" for outcome in outcomes.values()
        )
        if seeded and not any(thread.is_alive() for thread in threads):
            try:
                with engine.begin() as connection:
                    bounded_repositories(connection)
                    # Both predicates use this run's unique markers as an ownership guard.
                    connection.execute(
                        delete(models.watchlists).where(
                            models.watchlists.c.id == watchlist_id,
                            models.watchlists.c.name == marker,
                        )
                    )
                    connection.execute(
                        delete(models.games).where(
                            models.games.c.id == game_id, models.games.c.title == marker
                        )
                    )
                report["cleanup"] = True
            except Exception as exc:
                report["cleanup_failure"] = safe_failure(exc)
        engine.dispose()

    print(json.dumps(report, sort_keys=True))
    if "inconclusive" in report:
        return 2
    if (
        not report["cleanup"]
        or "setup_or_monitor_failure" in report
        or not report.get("parent_protected_before_delete", False)
        or not report.get("successful_delete_left_no_owned_rows", False)
        or not report.get("consistent_after_rollback", False)
        or set(outcomes) != {"refresh", "delete"}
        or any(not outcome["ok"] for outcome in outcomes.values())
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
