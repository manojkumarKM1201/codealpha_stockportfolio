"""
Unit Tests for Exports Module.
"""

import os
import tempfile
import pytest

from src.calculations import HoldingSummary, PortfolioSummary
from src.exports import (
    export_holdings_to_csv,
    export_transactions_to_csv,
    export_portfolio_summary_to_csv,
    generate_portfolio_summary_txt,
)


class TestExports:
    def test_export_holdings_to_csv(self):
        holdings = [
            HoldingSummary(
                symbol="AAPL",
                company_name="Apple Inc.",
                quantity=10.0,
                total_cost_basis=1500.0,
                average_purchase_price=150.0,
                latest_price=175.0,
                market_value=1750.0,
                unrealized_pnl=250.0,
                unrealized_return_pct=16.67,
                realized_pnl=0.0,
                price_source="LIVE",
                price_timestamp="2024-01-15 10:30:00",
            )
        ]

        csv_content = export_holdings_to_csv(holdings)
        assert "AAPL" in csv_content
        assert "Apple Inc." in csv_content
        assert "1750.0" in csv_content
        assert "LIVE" in csv_content

        # Test writing to file
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            export_holdings_to_csv(holdings, file_path=path)
            assert os.path.exists(path)
            with open(path, "r", encoding="utf-8") as f:
                saved = f.read()
            assert "AAPL" in saved
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_export_transactions_to_csv(self):
        txs = [
            {
                "id": 1,
                "transaction_date": "2024-01-01",
                "symbol": "MSFT",
                "company_name": "Microsoft",
                "transaction_type": "BUY",
                "quantity": 5.0,
                "price": 300.0,
                "fees": 2.5,
                "notes": "Starter pos",
            }
        ]
        csv_content = export_transactions_to_csv(txs)
        assert "MSFT" in csv_content
        assert "Starter pos" in csv_content
        assert "1502.5" in csv_content

    def test_export_portfolio_summary_to_csv(self):
        summary = PortfolioSummary(
            total_invested_cost_basis=5000.0,
            total_market_value=5500.0,
            total_unrealized_pnl=500.0,
            total_realized_pnl=100.0,
            total_net_pnl=600.0,
            overall_unrealized_return_pct=10.0,
            distinct_stocks_count=2,
            total_transactions_count=4,
        )
        csv_content = export_portfolio_summary_to_csv(summary)
        assert "Total Invested Cost Basis" in csv_content
        assert "5,500.00" in csv_content
        assert "10.00%" in csv_content

    def test_generate_portfolio_summary_txt(self):
        summary = PortfolioSummary(
            total_invested_cost_basis=1000.0,
            total_market_value=1200.0,
            total_unrealized_pnl=200.0,
            total_realized_pnl=50.0,
            total_net_pnl=250.0,
            overall_unrealized_return_pct=20.0,
            distinct_stocks_count=1,
            total_transactions_count=2,
            holdings_with_price_count=1,
        )
        holdings = [
            HoldingSummary(
                symbol="NVDA",
                quantity=2.0,
                total_cost_basis=1000.0,
                average_purchase_price=500.0,
                latest_price=600.0,
                market_value=1200.0,
                unrealized_pnl=200.0,
                unrealized_return_pct=20.0,
                price_source="LIVE",
            )
        ]
        txt = generate_portfolio_summary_txt(summary, holdings)
        assert "STOCK PORTFOLIO PERFORMANCE REPORT" in txt
        assert "EXECUTIVE SUMMARY" in txt
        assert "NVDA" in txt
        assert "1,200.00" in txt
        assert "Weighted-Average Cost Basis" in txt
