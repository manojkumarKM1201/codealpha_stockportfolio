"""
Integration and End-to-End Workflow Tests.

Verifies complete multi-step user workflows:
1. Initialize fresh temporary portfolio
2. Add multiple BUY transactions across different stocks
3. Execute partial and full SELL transactions
4. Verify accurate cost basis, realized & unrealized PnL
5. Confirm fee handling and cash flow consistency
6. Export CSV and TXT reports and verify contents
"""

import os
import tempfile
import pytest

from src.database import init_db, add_transaction, get_all_transactions
from src.portfolio import (
    get_all_portfolio_holdings,
    get_active_holdings,
    get_closed_holdings,
    get_portfolio_overview,
)
from src.exports import (
    export_holdings_to_csv,
    export_transactions_to_csv,
    export_portfolio_summary_to_csv,
    generate_portfolio_summary_txt,
)


@pytest.fixture
def clean_portfolio_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    if os.path.exists(path):
        os.remove(path)


class TestFullPortfolioLifecycle:
    def test_complete_portfolio_lifecycle_and_exports(self, clean_portfolio_db):
        db = clean_portfolio_db

        # Step 1: Buy 100 AAPL @ $150 with $10 fee
        add_transaction(
            {
                "symbol": "AAPL",
                "company_name": "Apple Inc.",
                "transaction_type": "BUY",
                "quantity": 100.0,
                "price": 150.0,
                "fees": 10.0,
                "date": "2024-01-02",
                "notes": "Tranche 1",
            },
            db_path=db,
        )

        # Step 2: Buy 50 AAPL @ $180 with $5 fee
        # Total AAPL = 150 shares
        # Total cost basis = (100 * 150 + 10) + (50 * 180 + 5) = 15010 + 9005 = 24015
        # Weighted average cost = 24015 / 150 = $160.10
        add_transaction(
            {
                "symbol": "AAPL",
                "company_name": "Apple Inc.",
                "transaction_type": "BUY",
                "quantity": 50.0,
                "price": 180.0,
                "fees": 5.0,
                "date": "2024-02-01",
                "notes": "Tranche 2",
            },
            db_path=db,
        )

        # Step 3: Buy 20 MSFT @ $300 with $0 fee
        add_transaction(
            {
                "symbol": "MSFT",
                "company_name": "Microsoft Corp.",
                "transaction_type": "BUY",
                "quantity": 20.0,
                "price": 300.0,
                "fees": 0.0,
                "date": "2024-02-15",
            },
            db_path=db,
        )

        # Step 4: Sell 50 AAPL @ $200 with $8 fee (Partial Sale)
        # Cost basis of 50 AAPL sold = 50 * 160.10 = $8005.00
        # Net proceeds = (50 * 200) - 8 = $9992.00
        # Realized PnL = 9992 - 8005 = $1987.00
        # Remaining AAPL = 100 shares
        # Remaining AAPL cost basis = 24015 - 8005 = $16010.00
        add_transaction(
            {
                "symbol": "AAPL",
                "company_name": "Apple Inc.",
                "transaction_type": "SELL",
                "quantity": 50.0,
                "price": 200.0,
                "fees": 8.0,
                "date": "2024-03-01",
            },
            db_path=db,
        )

        # Step 5: Sell 20 MSFT @ $350 with $10 fee (Full Sale)
        # Cost basis sold = 20 * 300 = $6000.00
        # Net proceeds = (20 * 350) - 10 = $6990.00
        # Realized PnL = 6990 - 6000 = $990.00
        # Remaining MSFT = 0 shares, cost basis = 0
        add_transaction(
            {
                "symbol": "MSFT",
                "company_name": "Microsoft Corp.",
                "transaction_type": "SELL",
                "quantity": 20.0,
                "price": 350.0,
                "fees": 10.0,
                "date": "2024-03-10",
            },
            db_path=db,
        )

        # Verify Database state
        txs = get_all_transactions(db_path=db)
        assert len(txs) == 5

        # Simulate market price for AAPL = $210
        prices = {
            "AAPL": {"price": 210.0, "source": "MANUAL", "timestamp": "2024-03-15 15:30:00"}
        }

        # Calculate Active & Closed Holdings
        active = get_active_holdings(price_data=prices, db_path=db)
        closed = get_closed_holdings(price_data=prices, db_path=db)

        assert len(active) == 1
        assert active[0].symbol == "AAPL"
        assert active[0].quantity == 100.0
        assert active[0].average_purchase_price == 160.10
        assert active[0].total_cost_basis == 16010.00
        assert active[0].latest_price == 210.0
        assert active[0].market_value == 21000.00
        assert active[0].unrealized_pnl == 4990.00
        assert active[0].realized_pnl == 1987.00

        assert len(closed) == 1
        assert closed[0].symbol == "MSFT"
        assert closed[0].quantity == 0.0
        assert closed[0].realized_pnl == 990.00

        # Calculate Aggregate Portfolio Metrics
        overview = get_portfolio_overview(price_data=prices, db_path=db)
        assert overview.distinct_stocks_count == 1
        assert overview.total_transactions_count == 5
        assert overview.total_invested_cost_basis == 16010.00
        assert overview.total_market_value == 21000.00
        assert overview.total_unrealized_pnl == 4990.00
        assert overview.total_realized_pnl == 2977.00  # 1987 + 990
        assert overview.total_net_pnl == 7967.00  # 4990 + 2977
        assert overview.total_fees_paid == 33.00  # 10 + 5 + 0 + 8 + 10

        # Verify Exports
        all_holdings = get_all_portfolio_holdings(price_data=prices, db_path=db)
        csv_h = export_holdings_to_csv(all_holdings)
        assert "AAPL" in csv_h
        assert "21000.0" in csv_h

        csv_tx = export_transactions_to_csv(txs)
        assert "Tranche 1" in csv_tx
        assert "Tranche 2" in csv_tx

        csv_sum = export_portfolio_summary_to_csv(overview)
        assert "16,010.00" in csv_sum
        assert "21,000.00" in csv_sum
        assert "2,977.00" in csv_sum

        txt_rep = generate_portfolio_summary_txt(overview, all_holdings)
        assert "STOCK PORTFOLIO PERFORMANCE REPORT" in txt_rep
        assert "21,000.00" in txt_rep
        assert "MSFT" in txt_rep
        assert "Realized P&L: $    990.00" in txt_rep
