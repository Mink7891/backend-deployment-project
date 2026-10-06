"""Every test runs offline; environment overrides isolate database, key and provider."""

import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["API_KEY"] = "tests-only-api-key-32-characters"
os.environ["PRICE_SOURCE"] = "mock"
os.environ["REFRESH_MIN_INTERVAL_SECONDS"] = "300"

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402, F401
from app.db import Base  # noqa: E402
from app.providers import MockProvider  # noqa: E402

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

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(database):
    with Session(database, expire_on_commit=False) as instance:
        yield instance


@pytest.fixture
def provider():
    return MockProvider()


@pytest.fixture
def client(database, provider):
    from fastapi.testclient import TestClient

    from app.db import get_session
    from app.main import app
    from app.providers import get_provider

    def test_session():
        with Session(database, expire_on_commit=False) as instance:
            try:
                yield instance
            except Exception:
                instance.rollback()
                raise

    app.dependency_overrides[get_session] = test_session
    app.dependency_overrides[get_provider] = lambda: provider
    try:
        with TestClient(app, headers={"X-API-Key": API_KEY}) as instance:
            yield instance
    finally:
        app.dependency_overrides.clear()
