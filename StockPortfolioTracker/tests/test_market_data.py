"""
Unit Tests for Market Data Module.
"""

from unittest.mock import patch, MagicMock
import pytest
import requests

from src.market_data import (
    MarketDataCache,
    MarketDataService,
    OfflineProvider,
    AlphaVantageProvider,
    FinnhubProvider,
    PriceResult,
)


class TestMarketDataCache:
    def test_cache_hit_and_manual_override(self):
        cache = MarketDataCache(ttl_seconds=10)

        # Initially empty
        assert cache.get("AAPL") is None

        # Set cache
        cache.set("AAPL", 150.0, "2024-01-01 10:00:00", is_delayed=True)
        res = cache.get("AAPL")
        assert res is not None
        assert res.price == 150.0
        assert res.source == "CACHED"

        # Manual price override
        cache.set_manual("AAPL", 155.0)
        res_manual = cache.get("AAPL")
        assert res_manual is not None
        assert res_manual.price == 155.0
        assert res_manual.source == "MANUAL"

        # Clear manual
        cache.clear_manual("AAPL")
        res_cleared = cache.get("AAPL")
        assert res_cleared.source == "CACHED"

    def test_cache_expiration(self):
        cache = MarketDataCache(ttl_seconds=0)  # Expires immediately
        cache.set("MSFT", 300.0, "2024-01-01 10:00:00")
        # Should expire because ttl is 0
        assert cache.get("MSFT") is None


class TestOfflineProvider:
    def test_offline_mode(self):
        service = MarketDataService(provider_name="OFFLINE", cache=MarketDataCache())
        res = service.get_stock_price("AAPL")
        assert res.price is None
        assert res.source == "UNAVAILABLE"
        assert "Offline mode" in (res.error_message or "")


class TestAlphaVantageProvider:
    def test_missing_api_key(self):
        provider = AlphaVantageProvider(api_key="")
        res = provider.fetch_price("AAPL")
        assert res.price is None
        assert res.source == "UNAVAILABLE"
        assert "key not configured" in (res.error_message or "")

    @patch("src.market_data.requests.get")
    def test_successful_quote(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "Global Quote": {
                "01. symbol": "AAPL",
                "05. price": "175.5000",
            }
        }
        mock_get.return_value = mock_resp

        provider = AlphaVantageProvider(api_key="valid_key")
        res = provider.fetch_price("AAPL")
        assert res.price == 175.50
        assert res.source == "LIVE"

    @patch("src.market_data.requests.get")
    def test_rate_limit_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "Note": "Thank you for using Alpha Vantage! Our standard API call frequency is 5 calls per minute."
        }
        mock_get.return_value = mock_resp

        provider = AlphaVantageProvider(api_key="valid_key")
        res = provider.fetch_price("AAPL")
        assert res.price is None
        assert res.source == "UNAVAILABLE"
        assert "rate limit" in (res.error_message or "").lower()

    @patch("src.market_data.requests.get")
    def test_network_timeout(self, mock_get):
        mock_get.side_effect = requests.Timeout("Connection timed out")
        provider = AlphaVantageProvider(api_key="valid_key")
        res = provider.fetch_price("AAPL")
        assert res.price is None
        assert res.source == "UNAVAILABLE"
        assert "timeout" in (res.error_message or "").lower()


class TestFinnhubProvider:
    def test_missing_api_key(self):
        provider = FinnhubProvider(api_key="")
        res = provider.fetch_price("MSFT")
        assert res.price is None
        assert res.source == "UNAVAILABLE"
        assert "key not configured" in (res.error_message or "")

    @patch("src.market_data.requests.get")
    def test_successful_quote(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"c": 325.40, "d": 2.1, "dp": 0.65}
        mock_get.return_value = mock_resp

        provider = FinnhubProvider(api_key="valid_key")
        res = provider.fetch_price("MSFT")
        assert res.price == 325.40
        assert res.source == "LIVE"

    @patch("src.market_data.requests.get")
    def test_http_429_rate_limit(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_get.return_value = mock_resp

        provider = FinnhubProvider(api_key="valid_key")
        res = provider.fetch_price("MSFT")
        assert res.price is None
        assert res.source == "UNAVAILABLE"
        assert "rate limit" in (res.error_message or "").lower()
