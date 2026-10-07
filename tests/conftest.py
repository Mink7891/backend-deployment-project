"""Тесты работают без БД и сети: репозитории и диспетчер подменяются."""

import os

os.environ["API_KEY"] = "test-api-key"
os.environ["PRICE_SOURCE"] = "mock"

import pytest  # noqa: E402


@pytest.fixture
def anyio_backend():
    return "asyncio"
