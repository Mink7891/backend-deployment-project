from uuid import UUID

import pytest
from sqlalchemy import func, select

from app import models
from app.exceptions import ProviderUnavailable


def assert_api_problem(response, status, code):
    assert response.status_code == status
    assert response.headers["content-type"].split(";")[0] == "application/problem+json"
    problem = response.json()
    assert problem["status"] == status and problem["code"] == code
    assert isinstance(problem["detail"], str)
    assert problem["type"].startswith("urn:gameradar:error:")
    assert problem["instance"].startswith("urn:uuid:")
    UUID(problem["traceId"])
    assert response.headers["x-request-id"] == problem["traceId"]
    return problem


def create_watchlist(client, name="Games"):
    response = client.post("/watchlists", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def add_item(client, watchlist_id, game_id="612", target="3.99", steam_only=True):
    return client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"game_id": game_id, "target_price": target, "steam_only": steam_only},
    )


def test_public_health_docs_and_openapi(client):
    for path in ["/health", "/docs", "/openapi.json", "/metrics"]:
        assert client.get(path, headers={"X-API-Key": ""}).status_code == 200
    schema = client.get("/openapi.json").json()
    assert schema["components"]["securitySchemes"]["APIKeyHeader"]["name"] == "X-API-Key"
    assert schema["paths"]["/watchlists"]["post"]["security"] == [{"APIKeyHeader": []}]
    assert client.get("/health").json() == {
        "status": "ok",
        "database": "ready",
        "priceSource": "mock",
        "mockPricesAreFictional": True,
    }


@pytest.mark.parametrize(
    "method,path",
    [("get", "/games/search?query=lego"), ("get", "/watchlists"), ("post", "/watchlists")],
)
def test_protected_operations_reject_bad_key(client, method, path):
    response = getattr(client, method)(path, headers={"X-API-Key": "wrong-key"})
    assert_api_problem(response, 401, "UNAUTHORIZED")
    assert response.headers["www-authenticate"] == "APIKey"


def test_missing_key_is_rejected(client):
    client.headers.pop("X-API-Key")
    assert_api_problem(client.get("/watchlists"), 401, "UNAUTHORIZED")


def test_mock_search_details_and_own_history(client):
    search = client.get("/games/search", params={"query": "LEGO"})
    assert search.status_code == 200
    assert [(game["id"], game["source"]) for game in search.json()] == [("612", "mock")]
    assert client.get("/games/612/history").json() == []
    game = client.get("/games/612").json()
    assert game["currency"] == "USD"
    assert game["bestPrice"] == "2.99"
    steam = next(offer for offer in game["offers"] if offer["storeId"] == "1")
    assert steam["storeName"] == "Steam" and steam["price"] == "3.99"
    assert all(offer["dealUrl"] is None for offer in game["offers"])
    first = client.get("/games/612/history").json()
    assert len(first) == 2
    assert all(row["source"] == "mock" and row["gameId"] == "612" for row in first)
    client.get("/games/612")
    assert client.get("/games/612/history").json() == first
    assert len(client.get("/games/612/history?limit=1&offset=1").json()) == 1


def test_watchlist_full_flow_summary_notifications_and_delete(client, database):
    watchlist_id = create_watchlist(client, "  Wishlist  ")
    assert client.get("/watchlists").json()[0]["name"] == "Wishlist"
    item = add_item(client, watchlist_id)
    assert item.status_code == 201
    assert item.json()["thresholdMet"] is True
    assert item.json()["currentPrice"] == "3.99"
    item_id = item.json()["id"]
    other = add_item(client, watchlist_id, "128", "7.00", steam_only=False)
    assert other.status_code == 201
    details = client.get(f"/watchlists/{watchlist_id}").json()
    assert len(details["items"]) == 2
    summary = client.get(f"/watchlists/{watchlist_id}/summary").json()
    assert summary["currentTotal"] == "10.98"
    assert summary["totalItems"] == summary["pricedItems"] == summary["matchedCount"] == 2
    notifications = client.get(f"/watchlists/{watchlist_id}/notifications").json()
    assert len(notifications) == 2
    assert {event["observedPrice"] for event in notifications} == {"3.99", "6.99"}
    refreshed = client.post(f"/watchlists/{watchlist_id}/refresh").json()
    assert refreshed["checkedItems"] == 2
    assert refreshed["notificationsCreated"] == 0
    assert len(client.get(f"/watchlists/{watchlist_id}/notifications").json()) == 2
    assert client.delete(f"/watchlists/{watchlist_id}/items/{item_id}").status_code == 204
    journal = client.get(f"/watchlists/{watchlist_id}/notifications").json()
    assert next(event for event in journal if event["gameId"] == "612")["itemId"] is None
    assert client.delete(f"/watchlists/{watchlist_id}").status_code == 204
    assert client.get(f"/watchlists/{watchlist_id}").status_code == 404
    with database.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(models.watchlist_items)) == 0
        assert connection.scalar(select(func.count()).select_from(models.notifications)) == 0


def test_duplicate_and_item_from_other_watchlist_are_rejected(client):
    first = create_watchlist(client, "First")
    second = create_watchlist(client, "Second")
    item = add_item(client, first).json()
    assert_api_problem(add_item(client, first), 409, "CONFLICT")
    path = f"/watchlists/{second}/items/{item['id']}"
    assert_api_problem(client.patch(path, json={"target_price": "9.00"}), 404, "NOT_FOUND")
    assert client.delete(path).status_code == 404
    assert client.get(f"/watchlists/{first}").json()["items"][0]["targetPrice"] == "3.99"


def test_patch_store_and_threshold_transitions(client):
    watchlist_id = create_watchlist(client)
    item = add_item(client, watchlist_id, target="3.00").json()
    assert item["thresholdMet"] is False
    path = f"/watchlists/{watchlist_id}/items/{item['id']}"
    assert client.patch(path, json={"steam_only": False}).json()["currentPrice"] == "2.99"
    assert len(client.get(f"/watchlists/{watchlist_id}/notifications").json()) == 1
    assert client.patch(path, json={"target_price": "2.00"}).json()["thresholdMet"] is False
    assert client.patch(path, json={"target_price": "3.00"}).json()["thresholdMet"] is True
    assert len(client.get(f"/watchlists/{watchlist_id}/notifications").json()) == 2
    for body in [{}, {"target_price": None}, {"steam_only": None}]:
        assert client.patch(path, json=body).status_code == 422


@pytest.mark.parametrize("value", ["-1.00", "NaN", "Infinity", "1.234", "10000000000.00"])
def test_invalid_money_is_rejected_without_writing_item(client, value):
    watchlist_id = create_watchlist(client)
    problem = assert_api_problem(
        add_item(client, watchlist_id, target=value), 422, "VALIDATION_ERROR"
    )
    assert problem["errors"]
    assert all(set(error) == {"field", "type", "message"} for error in problem["errors"])
    assert client.get(f"/watchlists/{watchlist_id}").json()["items"] == []


def test_validation_and_unknown_resources(client):
    assert client.post("/watchlists", json={"name": "   "}).status_code == 422
    assert client.get("/games/search?query=%20%20").status_code == 422
    assert client.get("/games/search?query=lego&limit=0").status_code == 422
    assert client.get("/games/not-a-number").status_code == 422
    assert client.get("/games/999999999").status_code == 404
    assert client.get("/games/612/history").status_code == 404
    assert client.get("/watchlists/0").status_code == 422
    assert client.get("/watchlists/999999").status_code == 404
    assert client.post("/watchlists/999999/refresh").status_code == 404


def test_provider_failure_is_controlled_and_does_not_write_partial_item(client, database):
    from app.adapters.providers import get_provider
    from app.main import app

    class FailingProvider:
        source = "mock"

        def search(self, query, limit=20):
            raise ProviderUnavailable()

        def get_game(self, game_id):
            raise ProviderUnavailable()

    watchlist_id = create_watchlist(client)
    app.dependency_overrides[get_provider] = FailingProvider
    assert_api_problem(client.get("/games/search?query=lego"), 503, "PROVIDER_UNAVAILABLE")
    assert_api_problem(add_item(client, watchlist_id), 503, "PROVIDER_UNAVAILABLE")
    with database.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(models.games)) == 0
    assert client.get(f"/watchlists/{watchlist_id}").json()["items"] == []


def test_prometheus_uses_route_templates(client):
    client.get("/watchlists/912345")
    client.get("/watchlists/987654")
    metrics = client.get("/metrics").text
    assert '"/watchlists/{watchlist_id}"' in metrics
    assert "/watchlists/912345" not in metrics
    assert "/watchlists/987654" not in metrics


def test_health_requires_schema_and_reports_unready_database(client, database):
    models.metadata.drop_all(database)
    response = client.get("/health")
    assert response.status_code == 503
    assert_api_problem(response, 503, "DATABASE_UNAVAILABLE")
    assert "gameradar_database_ready 0.0" in client.get("/metrics").text


def test_camel_case_requests_and_responses_use_approved_contract(client):
    watchlist_id = create_watchlist(client)
    response = client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"gameId": "612", "targetPrice": "3.00", "steamOnly": False},
    )
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["gameId"] == "612"
    assert item["currentPrice"] == "2.99"
    assert item["thresholdMet"] is True
    assert "game_id" not in item and "target_price" not in item and "steam_only" not in item
    assert "steamAppId" in item["game"] and "steam_app_id" not in item["game"]
    patched = client.patch(
        f"/watchlists/{watchlist_id}/items/{item['id']}",
        json={"targetPrice": "2.00", "steamOnly": True},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["targetPrice"] == "2.00"
    assert patched.json()["currentPrice"] == "3.99"
    assert patched.json()["thresholdMet"] is False


def test_camel_case_fields_have_the_same_input_validation(client):
    watchlist_id = create_watchlist(client)
    response = client.post(
        f"/watchlists/{watchlist_id}/items",
        json={"gameId": "612", "targetPrice": "NaN", "steamOnly": False},
    )
    assert response.status_code == 422
    assert client.get(f"/watchlists/{watchlist_id}").json()["items"] == []
