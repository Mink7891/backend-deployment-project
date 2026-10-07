"""HTTP-уровень: авторизация, валидация, формат ошибок, Swagger и метрики."""

import pytest
from fastapi.testclient import TestClient

from game_radar.database.session import get_db_session
from game_radar.dependencies.dispatcher_register import get_usecase_dispatcher
from game_radar.errors import watchlist_not_found
from game_radar.schemas.game_radar_api import WatchlistResponse
from game_radar.usecases.watchlists import CreateWatchlistUseCase, GetWatchlistUseCase
from main import app

HEADERS = {"X-API-Key": "test-api-key"}


class FakeDispatcher:
    def __init__(self):
        self.usecases = []

    async def dispatch(self, usecase, session):
        self.usecases.append(usecase)
        if isinstance(usecase, CreateWatchlistUseCase):
            return WatchlistResponse(id=1, name=usecase.name, created_at="2026-01-01T00:00:00Z")
        if isinstance(usecase, GetWatchlistUseCase):
            raise watchlist_not_found()
        raise AssertionError(f"unexpected {usecase}")


@pytest.fixture
def client():
    dispatcher = FakeDispatcher()

    async def no_session():
        yield None

    app.dependency_overrides[get_db_session] = no_session
    app.dependency_overrides[get_usecase_dispatcher] = lambda: dispatcher
    with TestClient(app) as test_client:
        test_client.dispatcher = dispatcher
        yield test_client
    app.dependency_overrides.clear()


def test_missing_or_wrong_api_key_is_rejected(client):
    assert client.get("/watchlists").status_code == 401
    response = client.get("/watchlists", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


def test_create_watchlist_builds_usecase(client):
    response = client.post("/watchlists", json={"name": "  Хочу купить "}, headers=HEADERS)
    assert response.status_code == 201
    assert response.json()["name"] == "Хочу купить"
    assert client.dispatcher.usecases == [CreateWatchlistUseCase(name="Хочу купить")]


def test_service_error_becomes_problem_details(client):
    response = client.get("/watchlists/5", headers=HEADERS)
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "WATCHLIST_NOT_FOUND"
    assert body["type"] == "urn:game-radar:error:WATCHLIST_NOT_FOUND"


def test_invalid_input_is_rejected_before_dispatch(client):
    response = client.post(
        "/watchlists/1/items", json={"gameId": "612", "targetPrice": "-1"}, headers=HEADERS
    )
    assert response.status_code == 422
    assert client.get("/watchlists/0", headers=HEADERS).status_code == 422
    assert client.dispatcher.usecases == []


def test_swagger_openapi_and_metrics_are_public(client):
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert "/watchlists/{watchlist_id}/items" in paths
    client.post("/watchlists", json={"name": "Games"}, headers=HEADERS)
    assert "http_requests_total" in client.get("/metrics").text
