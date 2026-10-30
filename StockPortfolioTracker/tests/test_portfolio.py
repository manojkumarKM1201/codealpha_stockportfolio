"""
Unit Tests for Portfolio Aggregation Module.
"""

import os
import tempfile
import pytest

from src.database import init_db, add_transaction
from src.portfolio import (
    get_all_portfolio_holdings,
    get_active_holdings,
    get_closed_holdings,
    get_portfolio_overview,
    holdings_to_dataframe,
    transactions_to_dataframe,
)


@pytest.fixture
def populated_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)

    # 1. Buy 10 AAPL @ 150, fee 5
    add_transaction(
        {"symbol": "AAPL", "company_name": "Apple", "transaction_type": "BUY", "quantity": 10, "price": 150, "fees": 5, "date": "2024-01-01"},
        db_path=path,
    )
    # 2. Buy 5 MSFT @ 300, fee 0
    add_transaction(
        {"symbol": "MSFT", "company_name": "Microsoft", "transaction_type": "BUY", "quantity": 5, "price": 300, "fees": 0, "date": "2024-01-05"},
        db_path=path,
    )
    # 3. Sell 5 MSFT @ 320, fee 10 (fully close MSFT)
    add_transaction(
        {"symbol": "MSFT", "company_name": "Microsoft", "transaction_type": "SELL", "quantity": 5, "price": 320, "fees": 10, "date": "2024-01-10"},
        db_path=path,
    )

    yield path
    if os.path.exists(path):
        os.remove(path)


class TestPortfolio:
    def test_get_portfolio_holdings_with_price_data(self, populated_db):
        prices = {
            "AAPL": {"price": 170.0, "source": "LIVE", "timestamp": "2024-01-15 12:00:00"}
        }
        holdings = get_all_portfolio_holdings(price_data=prices, db_path=populated_db)
        assert len(holdings) == 2

        aapl = next(h for h in holdings if h.symbol == "AAPL")
        assert aapl.quantity == 10.0
        assert aapl.latest_price == 170.0
        assert aapl.market_value == 1700.0
        assert aapl.total_cost_basis == 1505.0
        assert aapl.unrealized_pnl == 195.0
        assert aapl.price_source == "LIVE"

        msft = next(h for h in holdings if h.symbol == "MSFT")
        assert msft.quantity == 0.0
        # MSFT realized PnL = (5 * 320 - 10) - (5 * 300) = 1590 - 1500 = 90
        assert msft.realized_pnl == 90.0

    def test_active_and_closed_holdings(self, populated_db):
        active = get_active_holdings(db_path=populated_db)
        closed = get_closed_holdings(db_path=populated_db)

        assert len(active) == 1
        assert active[0].symbol == "AAPL"

        assert len(closed) == 1
        assert closed[0].symbol == "MSFT"

    def test_portfolio_overview(self, populated_db):
        prices = {"AAPL": {"price": 180.0, "source": "MANUAL", "timestamp": "2024-01-15"}}
        overview = get_portfolio_overview(price_data=prices, db_path=populated_db)

        assert overview.distinct_stocks_count == 1
        assert overview.total_transactions_count == 3
        assert overview.total_realized_pnl == 90.0
        # AAPL market value = 1800, cost basis = 1505, unrealized = 295
        assert overview.total_market_value == 1800.0
        assert overview.total_unrealized_pnl == 295.0
        assert overview.total_net_pnl == 385.0  # 295 + 90

    def test_dataframes_empty_and_filled(self, populated_db):
        # Empty
        df_empty_h = holdings_to_dataframe([])
        assert "Symbol" in df_empty_h.columns
        assert len(df_empty_h) == 0

        df_empty_tx = transactions_to_dataframe([])
        assert "Total Value" in df_empty_tx.columns
        assert len(df_empty_tx) == 0

        # Filled
        holdings = get_all_portfolio_holdings(db_path=populated_db)
        df_h = holdings_to_dataframe(holdings)
        assert len(df_h) == 2
        assert "AAPL" in df_h["Symbol"].values
