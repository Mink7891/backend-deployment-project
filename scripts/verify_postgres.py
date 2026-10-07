"""PostgreSQL/live HTTP verification; run through stdin inside the mock app container.

Uses production dependencies only. It deletes its own watchlists and synthetic games;
observations of the shared real-contract mock game 612 remain legitimate history.
"""

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

from sqlalchemy import delete, exists, func, select
from sqlalchemy.exc import IntegrityError

from app import models, usecases
from app.adapters.providers import MockProvider
from app.bootstrap import build_dispatcher
from app.config import get_settings
from app.db import engine
from app.exceptions import Conflict
from app.repositories import create_repositories
from app.schemas import AddItemRequest, CreateWatchlistRequest, UpdateItemRequest
from app.usecase_handlers import AddWatchlistItemHandler


class InjectedFailure(RuntimeError):
    pass


class CountingMockProvider(MockProvider):
    def __init__(self, synthetic_ids):
        super().__init__()
        template = self.games["101"]
        for game_id in synthetic_ids:
            self.games[game_id] = replace(
                template,
                id=game_id,
                title="Synthetic Core live check",
                offers=tuple(
                    replace(offer, deal_id=f"live-check-{game_id}-{offer.store_id}")
                    for offer in template.offers
                ),
            )
        self.calls = Counter()
        self.counter_lock = threading.Lock()

    def get_game(self, game_id):
        with self.counter_lock:
            self.calls[game_id] += 1
        time.sleep(0.05)  # Make simultaneous cold requests overlap without external I/O.
        return super().get_game(game_id)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        return None


class LiveCheck:
    def __init__(self):
        self.stage = "preconditions"
        self.summary = {}
        self.owned_names = set()
        self.owned_lists = set()
        self.synthetic_ids = set()
        self.http_delete_status = None
        self.settings = get_settings()
        assert os.environ.get("PRICE_SOURCE") == "mock"
        assert self.settings.price_source == "mock"
        assert engine.dialect.name == "postgresql"
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        self.run_name = "core-live-" + uuid4().hex

    @staticmethod
    def count(connection, table, condition):
        return connection.scalar(select(func.count()).select_from(table).where(condition))

    def new_game_id(self):
        while True:
            game_id = str(10**28 + uuid4().int % (10**28))
            if game_id in self.synthetic_ids:
                continue
            with engine.connect() as connection:
                present = connection.scalar(
                    select(models.games.c.id).where(models.games.c.id == game_id)
                )
            if present is None:
                self.synthetic_ids.add(game_id)
                return game_id

    def new_list(self, dispatcher, suffix):
        name = self.run_name + "-" + suffix
        self.owned_names.add(name)
        result = dispatcher.dispatch(
            usecases.CreateWatchlistUseCase(CreateWatchlistRequest(name=name))
        )
        self.owned_lists.add(result.id)
        return result.id

    def scoped_counts(self, game_id, watchlist_id=None):
        with engine.connect() as connection:
            result = {"games": self.count(connection, models.games, models.games.c.id == game_id)}
            for table in (
                models.offers,
                models.price_snapshots,
                models.watchlist_items,
                models.notifications,
            ):
                result[table.name] = self.count(connection, table, table.c.game_id == game_id)
            if watchlist_id is not None:
                result["watchlists"] = self.count(
                    connection, models.watchlists, models.watchlists.c.id == watchlist_id
                )
        return result

    @staticmethod
    def parallel(action, count=20):
        barrier = threading.Barrier(count)

        def run(index):
            barrier.wait(timeout=20)
            return action(index)

        with ThreadPoolExecutor(max_workers=count) as executor:
            return list(executor.map(run, range(count)))

    def database_checks(self):
        cold_id, rollback_id, caller_id = (self.new_game_id() for _ in range(3))
        provider = CountingMockProvider((cold_id, rollback_id, caller_id))
        dispatcher = build_dispatcher(engine.connect, provider, cache_ttl_seconds=300)
        self.stage = "cold_cache_concurrency"
        results = self.parallel(lambda _: dispatcher.dispatch(usecases.GetGameUseCase(cold_id)))
        assert all(result.id == cold_id for result in results)
        counts = self.scoped_counts(cold_id)
        assert provider.calls[cold_id] == 1
        assert counts["games"] == 1 and counts["offers"] == 2
        assert counts["price_snapshots"] == 2
        self.summary["coldCache"] = {
            "requests": len(results),
            "providerCalls": provider.calls[cold_id],
            "games": counts["games"],
            "offers": counts["offers"],
            "snapshots": counts["price_snapshots"],
        }

        self.stage = "duplicate_add_concurrency"
        watchlist_id = self.new_list(dispatcher, "concurrent")

        def add(_):
            try:
                dispatcher.dispatch(
                    usecases.AddWatchlistItemUseCase(
                        watchlist_id,
                        AddItemRequest(game_id=cold_id, target_price=Decimal("5.00")),
                    )
                )
                return "success"
            except (Conflict, IntegrityError):
                return "conflict"

        outcomes = Counter(self.parallel(add))
        counts = self.scoped_counts(cold_id)
        assert outcomes == {"success": 1, "conflict": 19}
        assert counts["watchlist_items"] == counts["notifications"] == 1
        item = dispatcher.dispatch(usecases.GetWatchlistUseCase(watchlist_id)).items[0]
        self.summary["duplicateAdds"] = {
            "requests": 20,
            "success": outcomes["success"],
            "conflicts": outcomes["conflict"],
            "items": counts["watchlist_items"],
            "notifications": counts["notifications"],
        }

        self.stage = "get_patch_refresh_concurrency"

        def mixed(index):
            if index % 3 == 0:
                command = usecases.GetGameUseCase(cold_id)
            elif index % 3 == 1:
                command = usecases.UpdateWatchlistItemUseCase(
                    watchlist_id,
                    item.id,
                    UpdateItemRequest(target_price=Decimal("5.00"), steam_only=True),
                )
            else:
                command = usecases.RefreshWatchlistUseCase(watchlist_id)
            return dispatcher.dispatch(command)

        mixed_results = self.parallel(mixed)
        counts = self.scoped_counts(cold_id)
        assert provider.calls[cold_id] == 1
        assert counts["watchlist_items"] == counts["notifications"] == 1
        assert counts["price_snapshots"] == 2
        self.summary["getPatchRefresh"] = {
            "requests": len(mixed_results),
            "providerCalls": provider.calls[cold_id],
            "items": counts["watchlist_items"],
            "notifications": counts["notifications"],
            "snapshots": counts["price_snapshots"],
        }

        self.stage = "handler_transaction_rollback"
        failure_list_id = self.new_list(dispatcher, "handler-rollback")
        baseline = self.scoped_counts(rollback_id, failure_list_id)

        def failing_repositories(connection):
            actual = create_repositories(connection)

            class FailingNotifications:
                def __getattr__(self, name):
                    return getattr(actual.watchlists, name)

                def add_notification(self, current_item, observed_price):
                    actual.watchlists.add_notification(current_item, observed_price)
                    raise InjectedFailure("Fault after all actual database writes")

            return SimpleNamespace(games=actual.games, watchlists=FailingNotifications())

        handler = AddWatchlistItemHandler(
            engine.connect, provider, repository_factory=failing_repositories
        )
        try:
            handler.handle(
                usecases.AddWatchlistItemUseCase(
                    failure_list_id,
                    AddItemRequest(game_id=rollback_id, target_price=Decimal("5.00")),
                )
            )
        except InjectedFailure:
            pass
        else:
            raise AssertionError("Injected rollback failure was not raised")
        assert self.scoped_counts(rollback_id, failure_list_id) == baseline
        assert baseline == {
            "games": 0,
            "offers": 0,
            "price_snapshots": 0,
            "watchlist_items": 0,
            "notifications": 0,
            "watchlists": 1,
        }

        self.stage = "caller_transaction_rollback"
        caller_name = self.run_name + "-caller-rollback"
        self.owned_names.add(caller_name)
        caller_baseline = self.scoped_counts(caller_id)
        with engine.connect() as connection:
            transaction = connection.begin()
            repositories = create_repositories(connection)
            temporary_list = repositories.watchlists.create(caller_name)
            self.owned_lists.add(temporary_list.id)
            repositories.games.save_observation(provider.games[caller_id], datetime.now(UTC))
            temporary_item = repositories.watchlists.add_item(
                temporary_list.id, caller_id, Decimal("5.00"), True
            )
            repositories.watchlists.add_notification(temporary_item, Decimal("4.99"))
            assert transaction.is_active
            assert (
                self.count(
                    connection, models.notifications, models.notifications.c.game_id == caller_id
                )
                == 1
            )
            transaction.rollback()
        assert self.scoped_counts(caller_id) == caller_baseline
        with engine.connect() as verification:
            assert (
                self.count(
                    verification, models.watchlists, models.watchlists.c.id == temporary_list.id
                )
                == 0
            )
        self.summary["rollback"] = {
            "handlerBaselineUnchanged": True,
            "callerBaselineUnchanged": True,
            "rolledBackTables": 6,
            "persistentWatchlists": baseline["watchlists"],
        }

    def http(self, method, path, body=None, authenticated=True):
        assert path.startswith("/") and not path.startswith("//")
        headers = {"Content-Type": "application/json"}
        if authenticated:
            headers["X-API-Key"] = self.settings.api_key.get_secret_value()
        request = urllib.request.Request(
            "http://127.0.0.1:8000" + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
            method=method,
        )
        try:
            response = self.opener.open(request, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            content = response.read(1048577)
            assert len(content) <= 1048576
            parsed = json.loads(content) if content else None
            return response.status, parsed, response.headers

    @staticmethod
    def problem(result, status):
        actual_status, body, headers = result
        assert actual_status == status and body["status"] == status
        assert headers.get_content_type() == "application/problem+json"
        assert {"type", "title", "status", "detail", "instance", "traceId", "code"} <= body.keys()
        UUID(body["traceId"])
        assert headers["X-Request-Id"] == body["traceId"]
        assert body["instance"].startswith("urn:uuid:")
        UUID(body["instance"].removeprefix("urn:uuid:"))
        if status == 422:
            assert body["errors"]
            assert all(set(issue) == {"field", "type", "message"} for issue in body["errors"])
        if status == 401:
            assert headers["WWW-Authenticate"] == "APIKey"

    def http_checks(self):
        self.stage = "http_mock_smoke"
        status, health, _ = self.http("GET", "/health", authenticated=False)
        assert status == 200 and health == {
            "status": "ok",
            "database": "ready",
            "priceSource": "mock",
            "mockPricesAreFictional": True,
        }
        self.problem(self.http("GET", "/watchlists", authenticated=False), 401)
        name = self.run_name + "-http"
        self.owned_names.add(name)
        watchlist_id = None
        try:
            status, created, _ = self.http("POST", "/watchlists", {"name": name})
            assert status == 201
            watchlist_id = created["id"]
            self.owned_lists.add(watchlist_id)
            payload = {"gameId": "612", "targetPrice": "4.00", "steamOnly": True}
            status, item, _ = self.http("POST", f"/watchlists/{watchlist_id}/items", payload)
            assert status == 201 and item["currentPrice"] == "3.99" and item["thresholdMet"]
            status, summary, _ = self.http("GET", f"/watchlists/{watchlist_id}/summary")
            assert status == 200 and summary["currentTotal"] == "3.99"
            assert summary["matchedCount"] == summary["totalItems"] == 1
            status, history, _ = self.http("GET", "/games/612/history")
            assert status == 200 and any(
                row["storeId"] == "1" and row["price"] == "3.99" and row["source"] == "mock"
                for row in history
            )
            status, refreshed, _ = self.http("POST", f"/watchlists/{watchlist_id}/refresh")
            assert status == 200 and refreshed["matchedCount"] == 1
            assert refreshed["notificationsCreated"] == 0
            self.problem(self.http("POST", f"/watchlists/{watchlist_id}/items", payload), 409)
            self.problem(
                self.http(
                    "POST",
                    f"/watchlists/{watchlist_id}/items",
                    {
                        "gameId": "612",
                        "targetPrice": "-1.00",
                    },
                ),
                422,
            )
            self.problem(
                self.http("PATCH", f"/watchlists/{watchlist_id}/items/{item['id']}", {}), 422
            )
            status, notifications, _ = self.http("GET", f"/watchlists/{watchlist_id}/notifications")
            assert status == 200 and len(notifications) == 1
            self.summary["http"] = {
                "health": 200,
                "create": 201,
                "add": 201,
                "summary": 200,
                "history": 200,
                "refresh": 200,
                "unauthorized": 401,
                "duplicate": 409,
                "validation": 422,
                "notifications": len(notifications),
            }
        finally:
            if watchlist_id is not None:
                try:
                    status, _, _ = self.http("DELETE", f"/watchlists/{watchlist_id}")
                    self.http_delete_status = status
                except Exception:
                    # Exact tracked-ID SQL cleanup still runs if HTTP becomes unavailable.
                    self.http_delete_status = 0
        assert self.http_delete_status == 204

    def cleanup(self):
        with engine.begin() as connection:
            # Recover only exact, random run names if a response was interrupted after commit.
            if self.owned_names:
                self.owned_lists.update(
                    connection.scalars(
                        select(models.watchlists.c.id).where(
                            models.watchlists.c.name.in_(self.owned_names)
                        )
                    )
                )
            removed_lists = connection.execute(
                delete(models.watchlists).where(
                    models.watchlists.c.id.in_(self.owned_lists),
                    models.watchlists.c.name.in_(self.owned_names),
                )
            ).rowcount
            # Preserve any reference acquired outside this script instead of deleting shared data.
            removed_games = connection.execute(
                delete(models.games).where(
                    models.games.c.id.in_(self.synthetic_ids),
                    ~exists(
                        select(models.watchlist_items.c.id).where(
                            models.watchlist_items.c.game_id == models.games.c.id
                        )
                    ),
                    ~exists(
                        select(models.notifications.c.id).where(
                            models.notifications.c.game_id == models.games.c.id
                        )
                    ),
                )
            ).rowcount
            remaining_lists = self.count(
                connection, models.watchlists, models.watchlists.c.name.in_(self.owned_names)
            )
            remaining_games = self.count(
                connection, models.games, models.games.c.id.in_(self.synthetic_ids)
            )
        return {
            "removedWatchlists": removed_lists,
            "removedSyntheticGames": removed_games,
            "remainingWatchlists": remaining_lists,
            "remainingSyntheticGames": remaining_games,
            "httpDeleteStatus": self.http_delete_status,
        }


def main():
    check = None
    summary = {"status": "failed", "stage": "initialization"}
    try:
        check = LiveCheck()
        check.database_checks()
        check.http_checks()
        summary = {"status": "passed", **check.summary}
    except Exception as error:
        summary = {
            "status": "failed",
            "stage": check.stage if check else "initialization",
            "errorType": type(error).__name__,
            **(check.summary if check else {}),
        }
    finally:
        if check is not None:
            try:
                cleanup = check.cleanup()
                summary["cleanup"] = cleanup
                if cleanup["remainingWatchlists"] or cleanup["remainingSyntheticGames"]:
                    summary["status"] = "failed"
                    summary["cleanupIncomplete"] = True
            except Exception as error:
                summary["status"] = "failed"
                summary["cleanupErrorType"] = type(error).__name__
        engine.dispose()
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
