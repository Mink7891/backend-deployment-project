from decimal import Decimal

import httpx
import pytest

from app.adapters.providers import CheapSharkProvider, MockProvider
from app.config import Settings
from app.exceptions import GameNotFound, ProviderUnavailable


@pytest.fixture
def upstream(monkeypatch):
    original_client = httpx.Client
    requests = []

    def configure(handler):
        def record(request):
            requests.append(request)
            return handler(request)

        def client(**kwargs):
            kwargs["transport"] = httpx.MockTransport(record)
            return original_client(**kwargs)

        monkeypatch.setattr(httpx, "Client", client)
        monkeypatch.setattr("app.adapters.providers.time.sleep", lambda _: None)
        settings = Settings(
            _env_file=None,
            database_url="sqlite+pysqlite:///:memory:",
            api_key="provider-tests-only-secret",
            price_source="cheapshark",
            cheapshark_base_url="https://provider.invalid/api",
            refresh_min_interval_seconds=300,
        )
        return CheapSharkProvider(settings)

    return configure, requests


def test_mock_provider_works_without_outbound_http():
    provider = MockProvider()
    assert provider.get_game("612").source == "mock"
    assert provider.search(" LEGO ")[0].id == "612"
    assert provider.search("no such title") == []
    with pytest.raises(GameNotFound):
        provider.get_game("999999")


def test_search_parses_currency_data_and_caches_normalized_query(upstream):
    configure, requests = upstream
    payload = [
        {
            "gameID": "612",
            "external": "LEGO Batman",
            "steamAppID": "21000",
            "cheapest": "2.99",
            "thumb": "https://example.invalid/game.jpg",
        }
    ]
    provider = configure(lambda _: httpx.Response(200, json=payload))
    first = provider.search("LEGO")
    second = provider.search(" lego ")
    assert first == second
    assert first[0].source == "cheapshark"
    assert first[0].cheapest_price == Decimal("2.99")
    assert first[0].offers == ()
    assert len(requests) == 1
    assert requests[0].url.host == "provider.invalid"
    assert requests[0].url.path == "/api/games"


def test_details_parse_offers_and_do_not_follow_user_supplied_urls(upstream):
    configure, requests = upstream
    payload = {
        "info": {"title": "LEGO Batman", "steamAppID": "21000", "thumb": None},
        "deals": [
            {
                "dealID": "encoded-deal",
                "storeID": "1",
                "price": "3.99",
                "retailPrice": "19.99",
                "savings": "80.04002",
            }
        ],
    }
    provider = configure(lambda _: httpx.Response(200, json=payload))
    game = provider.get_game("612")
    assert game.id == "612" and game.steam_app_id == "21000"
    assert game.offers[0].price == game.cheapest_price == Decimal("3.99")
    assert requests[0].url.params["id"] == "612"


@pytest.mark.parametrize(
    "payload",
    [
        {"unexpected": "shape"},
        [{"gameID": "abc"}],
        [{"gameID": "1", "external": "X", "cheapest": "NaN"}],
    ],
)
def test_invalid_search_payload_becomes_controlled_failure(upstream, payload):
    configure, _ = upstream
    provider = configure(lambda _: httpx.Response(200, json=payload))
    with pytest.raises(ProviderUnavailable):
        provider.search("game")


@pytest.mark.parametrize("price", ["-1.00", "NaN", "Infinity", "10000000000.00"])
def test_invalid_provider_price_is_rejected(upstream, price):
    configure, _ = upstream
    provider = configure(
        lambda _: httpx.Response(200, json=[{"gameID": "1", "external": "X", "cheapest": price}])
    )
    with pytest.raises(ProviderUnavailable):
        provider.search("game")


def test_rate_limit_retains_cooldown_and_prevents_second_http_call(upstream):
    configure, requests = upstream
    provider = configure(lambda _: httpx.Response(429, headers={"Retry-After": "37"}))
    with pytest.raises(ProviderUnavailable) as first:
        provider.get_game("612")
    assert first.value.retry_after == 37
    with pytest.raises(ProviderUnavailable) as second:
        provider.get_game("128")
    assert 1 <= second.value.retry_after <= 37
    assert len(requests) == 1


def test_timeout_is_controlled_and_upstream_details_are_not_exposed(upstream):
    configure, _ = upstream

    def timeout(request):
        raise httpx.ReadTimeout("sensitive-upstream-details", request=request)

    provider = configure(timeout)
    with pytest.raises(ProviderUnavailable) as failure:
        provider.get_game("612")
    assert "sensitive-upstream-details" not in str(failure.value)


def test_empty_provider_details_mean_game_not_found(upstream):
    configure, _ = upstream
    provider = configure(lambda _: httpx.Response(200, json={}))
    with pytest.raises(GameNotFound):
        provider.get_game("999999")
