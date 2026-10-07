"""Every test runs offline; environment overrides isolate database, key and provider."""

import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["API_KEY"] = "tests-only-api-key-32-characters"
os.environ["PRICE_SOURCE"] = "mock"
os.environ["REFRESH_MIN_INTERVAL_SECONDS"] = "300"

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.adapters.providers import MockProvider  # noqa: E402
from app.models import metadata  # noqa: E402

API_KEY = os.environ["API_KEY"]


@pytest.fixture(autouse=True)
def forbid_external_http(monkeypatch):
    def block_sync(*args, **kwargs):
        raise AssertionError("A test attempted an external HTTP request")

    async def block_async(*args, **kwargs):
        raise AssertionError("A test attempted an external HTTP request")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", block_sync)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", block_async)


@pytest.fixture
def database():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def connection_factory(database):
    return database.connect


@pytest.fixture
def provider():
    return MockProvider()


@pytest.fixture
def client(database, provider):
    from fastapi import Depends
    from fastapi.testclient import TestClient

    from app.adapters.providers import get_provider
    from app.api.dependencies import get_dispatcher
    from app.db import get_connection
    from app.dependencies.dispatcher_register import build_dispatcher
    from app.main import app

    def test_connection():
        with database.connect() as connection:
            yield connection

    def test_dispatcher(current_provider=Depends(get_provider)):
        return build_dispatcher(database.connect, current_provider, cache_ttl_seconds=300)

    app.dependency_overrides[get_connection] = test_connection
    app.dependency_overrides[get_dispatcher] = test_dispatcher
    app.dependency_overrides[get_provider] = lambda: provider
    try:
        with TestClient(app, headers={"X-API-Key": API_KEY}) as instance:
            yield instance
    finally:
        app.dependency_overrides.clear()
