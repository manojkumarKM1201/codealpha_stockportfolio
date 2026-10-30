"""
Market Data Adapter Module for Stock Portfolio Tracker.

Provides pluggable market data fetching with:
- Configurable providers: YFINANCE, ALPHA_VANTAGE, FINNHUB, OFFLINE
- Local memory caching with configurable TTL (default 300s / 5m)
- Distinction between LIVE, CACHED, MANUAL, and UNAVAILABLE data
- Resilient error handling (rate limits, network timeouts, invalid tickers)
- Graceful offline fallback with manual price overrides
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import os
import time
from typing import Any, Dict, Optional
import requests
from dotenv import load_dotenv

# Load environment variables if present
load_dotenv()

DEFAULT_CACHE_TTL = int(os.environ.get("PRICE_CACHE_TTL_SECONDS", "300"))


@dataclass
class PriceResult:
    """Standardized market price result."""
    symbol: str
    price: Optional[float] = None
    source: str = "UNAVAILABLE"  # LIVE, CACHED, MANUAL, UNAVAILABLE
    timestamp: Optional[str] = None
    currency: str = "USD"
    is_delayed: bool = False
    error_message: Optional[str] = None


class MarketDataCache:
    """In-memory cache for stock quotes with time-to-live expiration."""

    def __init__(self, ttl_seconds: int = DEFAULT_CACHE_TTL):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._manual_prices: Dict[str, Dict[str, Any]] = {}

    def get(self, symbol: str) -> Optional[PriceResult]:
        """Return cached price if still valid within TTL."""
        sym = symbol.upper()
        if sym in self._manual_prices:
            m = self._manual_prices[sym]
            return PriceResult(
                symbol=sym,
                price=m["price"],
                source="MANUAL",
                timestamp=m["timestamp"],
                currency=m.get("currency", "USD"),
            )

        if sym in self._cache:
            entry = self._cache[sym]
            now = time.time()
            if now - entry["cached_at"] <= self.ttl_seconds:
                return PriceResult(
                    symbol=sym,
                    price=entry["price"],
                    source="CACHED",
                    timestamp=entry["timestamp"],
                    currency=entry.get("currency", "USD"),
                    is_delayed=entry.get("is_delayed", True),
                )
        return None

    def set(
        self,
        symbol: str,
        price: float,
        timestamp: str,
        currency: str = "USD",
        is_delayed: bool = True,
    ) -> None:
        """Store a newly fetched market price in cache."""
        sym = symbol.upper()
        self._cache[sym] = {
            "price": round(price, 4),
            "cached_at": time.time(),
            "timestamp": timestamp,
            "currency": currency,
            "is_delayed": is_delayed,
        }

    def set_manual(self, symbol: str, price: float) -> None:
        """Set or update user manual price override for a symbol."""
        sym = symbol.upper()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._manual_prices[sym] = {
            "price": round(price, 4),
            "timestamp": now_str,
            "currency": "USD",
        }

    def clear_manual(self, symbol: Optional[str] = None) -> None:
        """Clear manual price overrides."""
        if symbol:
            self._manual_prices.pop(symbol.upper(), None)
        else:
            self._manual_prices.clear()

    def clear(self) -> None:
        """Clear all cached data."""
        self._cache.clear()


# Global cache instance
_GLOBAL_CACHE = MarketDataCache()


class BaseMarketDataProvider:
    """Base interface for market data providers."""

    def fetch_price(self, symbol: str) -> PriceResult:
        raise NotImplementedError("Subclasses must implement fetch_price.")


class OfflineProvider(BaseMarketDataProvider):
    """Offline provider that makes zero external calls."""

    def fetch_price(self, symbol: str) -> PriceResult:
        return PriceResult(
            symbol=symbol.upper(),
            price=None,
            source="UNAVAILABLE",
            error_message="Offline mode active: external market data disabled.",
        )


class AlphaVantageProvider(BaseMarketDataProvider):
    """Alpha Vantage market data provider using official REST endpoint."""

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ALPHA_VANTAGE_API_KEY", "")

    def fetch_price(self, symbol: str) -> PriceResult:
        sym = symbol.upper()
        if not self.api_key:
            return PriceResult(
                symbol=sym,
                price=None,
                source="UNAVAILABLE",
                error_message="Alpha Vantage API key not configured.",
            )

        try:
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": sym,
                "apikey": self.api_key,
            }
            resp = requests.get(self.BASE_URL, params=params, timeout=7.0)
            if resp.status_code != 200:
                return PriceResult(
                    symbol=sym,
                    price=None,
                    source="UNAVAILABLE",
                    error_message=f"HTTP Error {resp.status_code} from Alpha Vantage.",
                )

            data = resp.json()
            if "Note" in data:
                return PriceResult(
                    symbol=sym,
                    price=None,
                    source="UNAVAILABLE",
                    error_message="Alpha Vantage rate limit reached. Please wait or use manual price.",
                )

            quote = data.get("Global Quote", {})
            price_str = quote.get("05. price")
            if price_str:
                price = float(price_str)
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                return PriceResult(
                    symbol=sym,
                    price=price,
                    source="LIVE",
                    timestamp=now_str,
                    currency="USD",
                    is_delayed=True,
                )

            return PriceResult(
                symbol=sym,
                price=None,
                source="UNAVAILABLE",
                error_message=f"Symbol '{sym}' not found on Alpha Vantage.",
            )
        except requests.Timeout:
            return PriceResult(
                symbol=sym,
                price=None,
                source="UNAVAILABLE",
                error_message="Network timeout connecting to Alpha Vantage.",
            )
        except Exception as e:
            return PriceResult(
                symbol=sym,
                price=None,
                source="UNAVAILABLE",
                error_message=f"Alpha Vantage request failed: {str(e)}",
            )


class FinnhubProvider(BaseMarketDataProvider):
    """Finnhub market data provider."""

    BASE_URL = "https://finnhub.io/api/v1/quote"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("FINNHUB_API_KEY", "")

    def fetch_price(self, symbol: str) -> PriceResult:
        sym = symbol.upper()
        if not self.api_key:
            return PriceResult(
                symbol=sym,
                price=None,
                source="UNAVAILABLE",
                error_message="Finnhub API key not configured.",
            )

        try:
            params = {"symbol": sym, "token": self.api_key}
            resp = requests.get(self.BASE_URL, params=params, timeout=7.0)
            if resp.status_code == 429:
                return PriceResult(
                    symbol=sym,
                    price=None,
                    source="UNAVAILABLE",
                    error_message="Finnhub rate limit exceeded.",
                )
            if resp.status_code != 200:
                return PriceResult(
                    symbol=sym,
                    price=None,
                    source="UNAVAILABLE",
                    error_message=f"HTTP {resp.status_code} from Finnhub.",
                )

            data = resp.json()
            current_price = data.get("c")
            if current_price and float(current_price) > 0:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                return PriceResult(
                    symbol=sym,
                    price=float(current_price),
                    source="LIVE",
                    timestamp=now_str,
                    currency="USD",
                    is_delayed=False,
                )

            return PriceResult(
                symbol=sym,
                price=None,
                source="UNAVAILABLE",
                error_message=f"No price data available for '{sym}' from Finnhub.",
            )
        except requests.Timeout:
            return PriceResult(
                symbol=sym,
                price=None,
                source="UNAVAILABLE",
                error_message="Network timeout connecting to Finnhub.",
            )
        except Exception as e:
            return PriceResult(
                symbol=sym,
                price=None,
                source="UNAVAILABLE",
                error_message=f"Finnhub request failed: {str(e)}",
            )


class YFinanceProvider(BaseMarketDataProvider):
    """Yahoo Finance provider using yfinance package with strict timeout safety."""

    def fetch_price(self, symbol: str) -> PriceResult:
        import socket
        sym = symbol.upper()
        old_timeout = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(3.0)
            import yfinance as yf

            ticker = yf.Ticker(sym)
            fast_info = getattr(ticker, "fast_info", None)
            price = None
            currency = "USD"

            if fast_info:
                try:
                    price = getattr(fast_info, "last_price", None)
                    currency = getattr(fast_info, "currency", "USD") or "USD"
                except Exception:
                    price = None

            if price is None:
                # Fallback to historical daily quote with small period
                try:
                    hist = ticker.history(period="1d")
                    if not hist.empty and "Close" in hist.columns:
                        price = float(hist["Close"].iloc[-1])
                except Exception:
                    price = None

            if price is not None and price > 0:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                return PriceResult(
                    symbol=sym,
                    price=round(float(price), 4),
                    source="LIVE",
                    timestamp=now_str,
                    currency=currency,
                    is_delayed=True,
                )

            return PriceResult(
                symbol=sym,
                price=None,
                source="UNAVAILABLE",
                error_message=f"Ticker symbol '{sym}' returned no price data from Yahoo Finance.",
            )
        except ImportError:
            return PriceResult(
                symbol=sym,
                price=None,
                source="UNAVAILABLE",
                error_message="yfinance library is not installed.",
            )
        except (socket.timeout, TimeoutError, requests.RequestException, OSError) as e:
            return PriceResult(
                symbol=sym,
                price=None,
                source="UNAVAILABLE",
                error_message=f"Network error or timeout connecting to Yahoo Finance: {str(e)}",
            )
        except Exception as e:
            return PriceResult(
                symbol=sym,
                price=None,
                source="UNAVAILABLE",
                error_message=f"Yahoo Finance fetch error: {str(e)}",
            )
        finally:
            socket.setdefaulttimeout(old_timeout)



class MarketDataService:
    """
    Centralized Market Data Service managing caching, provider selection,
    and fallback handling.
    """

    def __init__(
        self,
        provider_name: Optional[str] = None,
        cache: Optional[MarketDataCache] = None,
    ):
        self.provider_name = (
            provider_name or os.environ.get("MARKET_DATA_PROVIDER", "YFINANCE")
        ).upper()
        self.cache = cache if cache is not None else _GLOBAL_CACHE
        self._provider = self._create_provider(self.provider_name)

    def _create_provider(self, name: str) -> BaseMarketDataProvider:
        if name == "ALPHA_VANTAGE":
            return AlphaVantageProvider()
        elif name == "FINNHUB":
            return FinnhubProvider()
        elif name == "OFFLINE":
            return OfflineProvider()
        elif name == "YFINANCE":
            return YFinanceProvider()
        else:
            return OfflineProvider()

    def set_provider(self, name: str) -> None:
        """Switch active market data provider at runtime."""
        self.provider_name = name.upper()
        self._provider = self._create_provider(self.provider_name)

    def get_stock_price(self, symbol: str, force_refresh: bool = False) -> PriceResult:
        """
        Get latest price for symbol.
        Checks cache unless force_refresh is True.
        """
        sym = symbol.strip().upper()
        if not sym:
            return PriceResult(symbol="", price=None, source="UNAVAILABLE", error_message="Empty symbol.")

        # Check cache if not forcing refresh
        if not force_refresh:
            cached = self.cache.get(sym)
            if cached is not None:
                return cached

        # Otherwise fetch from active provider
        result = self._provider.fetch_price(sym)

        # If fetch succeeded, save in cache
        if result.price is not None and result.price >= 0:
            self.cache.set(
                symbol=sym,
                price=result.price,
                timestamp=result.timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                currency=result.currency,
                is_delayed=result.is_delayed,
            )

        return result

    def set_manual_price(self, symbol: str, price: float) -> None:
        """Manually supply or override price for a stock symbol."""
        self.cache.set_manual(symbol, price)

    def clear_manual_price(self, symbol: Optional[str] = None) -> None:
        """Clear manual price for a symbol or all symbols."""
        self.cache.clear_manual(symbol)

    def get_price_dict_for_symbols(
        self, symbols: list[str], force_refresh: bool = False
    ) -> Dict[str, Dict[str, Any]]:
        """
        Retrieve prices for a collection of symbols, returning a dict ready
        for portfolio calculations.
        """
        res: Dict[str, Dict[str, Any]] = {}
        for s in symbols:
            pr = self.get_stock_price(s, force_refresh=force_refresh)
            res[s.upper()] = {
                "price": pr.price,
                "source": pr.source,
                "timestamp": pr.timestamp,
                "currency": pr.currency,
                "error": pr.error_message,
            }
        return res
