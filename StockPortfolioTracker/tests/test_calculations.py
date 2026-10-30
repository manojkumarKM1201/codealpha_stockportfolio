"""
Unit Tests for Financial Calculations Module.
"""

import pytest
from src.calculations import (
    HoldingSummary,
    PortfolioSummary,
    calculate_buy_cost,
    calculate_sale_proceeds,
    calculate_realized_pnl,
    calculate_return_percentage,
    process_transactions_for_symbol,
    calculate_portfolio_summary,
)


class TestFinancialCalculations:
    def test_calculate_buy_cost(self):
        # 10 shares @ $150 + $5 fee = $1505
        assert calculate_buy_cost(10.0, 150.0, 5.0) == 1505.0
        # Zero fee
        assert calculate_buy_cost(10.0, 150.0, 0.0) == 1500.0

    def test_calculate_sale_proceeds(self):
        # 10 shares @ $200 - $10 fee = $1990
        assert calculate_sale_proceeds(10.0, 200.0, 10.0) == 1990.0
        # Zero fee
        assert calculate_sale_proceeds(10.0, 200.0, 0.0) == 2000.0

    def test_calculate_realized_pnl(self):
        # Sold 5 shares @ $200, fee $5, avg cost basis per share = $150
        # Gross = $1000, Net = $995, Cost of sold = $750, Realized PnL = $245
        res = calculate_realized_pnl(
            sold_quantity=5.0,
            sale_price=200.0,
            sale_fee=5.0,
            average_cost_basis_per_share=150.0,
        )
        assert res["gross_proceeds"] == 1000.0
        assert res["net_proceeds"] == 995.0
        assert res["cost_basis_sold"] == 750.0
        assert res["realized_pnl"] == 245.0

    def test_calculate_return_percentage(self):
        # Normal positive return: 50 profit on 200 investment = 25%
        assert calculate_return_percentage(50.0, 200.0) == 25.0
        # Loss: -50 on 200 = -25%
        assert calculate_return_percentage(-50.0, 200.0) == -25.0
        # Zero investment / zero denominator safety
        assert calculate_return_percentage(50.0, 0.0) == 0.0
        assert calculate_return_percentage(0.0, -100.0) == 0.0

    def test_process_transactions_weighted_average_cost_and_partial_sale(self):
        """
        Scenario:
        1. BUY 10 AAPL @ $100, fee $10 -> Qty=10, Basis=$1010, Avg=$101
        2. BUY 10 AAPL @ $120, fee $10 -> Qty=20, Basis=$1010 + $1210 = $2220, Avg=$111
        3. SELL 5 AAPL @ $150, fee $5:
           - Sold cost = 5 * $111 = $555
           - Net proceeds = 5 * $150 - $5 = $745
           - Realized PnL = $745 - $555 = $190
           - Remaining Qty = 15
           - Remaining Basis = $2220 - $555 = $1665
           - Avg price remains $1665 / 15 = $111
        4. Market Price is $160:
           - Market Value = 15 * 160 = $2400
           - Unrealized PnL = $2400 - $1665 = $735
           - Unrealized Return = (735 / 1665) * 100 = 44.14%
        """
        txs = [
            {"symbol": "AAPL", "transaction_type": "BUY", "quantity": 10.0, "price": 100.0, "fees": 10.0},
            {"symbol": "AAPL", "transaction_type": "BUY", "quantity": 10.0, "price": 120.0, "fees": 10.0},
            {"symbol": "AAPL", "transaction_type": "SELL", "quantity": 5.0, "price": 150.0, "fees": 5.0},
        ]

        holding = process_transactions_for_symbol(
            txs, current_price=160.0, price_source="LIVE", price_timestamp="2026-03-30 10:00:00"
        )

        assert holding.symbol == "AAPL"
        assert holding.quantity == 15.0
        assert holding.total_cost_basis == 1665.0
        assert holding.average_purchase_price == 111.0
        assert holding.realized_pnl == 190.0
        assert holding.latest_price == 160.0
        assert holding.market_value == 2400.0
        assert holding.unrealized_pnl == 735.0
        assert holding.unrealized_return_pct == 44.14
        assert holding.price_source == "LIVE"

    def test_process_transactions_full_sale(self):
        """
        Scenario:
        1. BUY 10 MSFT @ $200, fee $0 -> Qty=10, Basis=$2000
        2. SELL 10 MSFT @ $250, fee $10 ->
           - Sold cost = $2000
           - Net proceeds = $2500 - $10 = $2490
           - Realized PnL = $490
           - Remaining Qty = 0.0
           - Remaining Basis = 0.0
        """
        txs = [
            {"symbol": "MSFT", "transaction_type": "BUY", "quantity": 10.0, "price": 200.0, "fees": 0.0},
            {"symbol": "MSFT", "transaction_type": "SELL", "quantity": 10.0, "price": 250.0, "fees": 10.0},
        ]

        holding = process_transactions_for_symbol(txs, current_price=300.0)
        assert holding.quantity == 0.0
        assert holding.total_cost_basis == 0.0
        assert holding.average_purchase_price == 0.0
        assert holding.realized_pnl == 490.0
        assert holding.market_value == 0.0
        assert holding.unrealized_pnl == 0.0

    def test_process_transactions_missing_price(self):
        txs = [
            {"symbol": "TSLA", "transaction_type": "BUY", "quantity": 5.0, "price": 200.0, "fees": 0.0},
        ]
        holding = process_transactions_for_symbol(txs, current_price=None, price_source="UNAVAILABLE")
        assert holding.quantity == 5.0
        assert holding.total_cost_basis == 1000.0
        assert holding.latest_price is None
        assert holding.market_value is None
        assert holding.unrealized_pnl is None
        assert holding.price_source == "UNAVAILABLE"

    def test_empty_portfolio_summary(self):
        summary = calculate_portfolio_summary([])
        assert summary.total_invested_cost_basis == 0.0
        assert summary.total_market_value == 0.0
        assert summary.total_unrealized_pnl == 0.0
        assert summary.total_realized_pnl == 0.0
        assert summary.distinct_stocks_count == 0
        assert summary.holdings_with_price_count == 0
        assert summary.overall_unrealized_return_pct == 0.0

    def test_multi_stock_portfolio_summary(self):
        h1 = HoldingSummary(
            symbol="AAPL",
            quantity=10.0,
            total_cost_basis=1500.0,
            average_purchase_price=150.0,
            latest_price=180.0,
            market_value=1800.0,
            unrealized_pnl=300.0,
            unrealized_return_pct=20.0,
            realized_pnl=50.0,
            total_purchase_fees=10.0,
            total_sale_fees=5.0,
        )
        h2 = HoldingSummary(
            symbol="GOOGL",
            quantity=5.0,
            total_cost_basis=1000.0,
            average_purchase_price=200.0,
            latest_price=None,  # Missing market price
            market_value=None,
            unrealized_pnl=None,
            unrealized_return_pct=None,
            realized_pnl=0.0,
            total_purchase_fees=5.0,
            total_sale_fees=0.0,
        )
        # Closed holding (qty = 0)
        h3 = HoldingSummary(
            symbol="AMZN",
            quantity=0.0,
            total_cost_basis=0.0,
            average_purchase_price=0.0,
            latest_price=150.0,
            market_value=0.0,
            unrealized_pnl=0.0,
            realized_pnl=200.0,
            total_purchase_fees=10.0,
            total_sale_fees=10.0,
        )

        summary = calculate_portfolio_summary([h1, h2, h3], total_transactions_count=6)
        assert summary.distinct_stocks_count == 2  # AAPL & GOOGL active
        assert summary.total_invested_cost_basis == 2500.0  # 1500 + 1000
        assert summary.total_market_value == 1800.0  # Only AAPL has price
        assert summary.total_unrealized_pnl == 300.0
        assert summary.total_realized_pnl == 250.0  # 50 + 200
        assert summary.total_net_pnl == 550.0  # 300 + 250
        assert summary.holdings_with_price_count == 1
        assert summary.holdings_missing_price_count == 1
        assert summary.total_fees_paid == 40.0  # 15 + 5 + 20
        assert summary.total_transactions_count == 6
