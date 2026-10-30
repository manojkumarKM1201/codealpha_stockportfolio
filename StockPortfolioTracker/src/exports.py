"""
Data Export and Reporting Module for Stock Portfolio Tracker.

Provides CSV and TXT report generation for:
- Current holdings
- Historical transactions
- High-level portfolio summary metrics
"""

from datetime import datetime
import io
from typing import Any, Dict, List, Optional
import pandas as pd

from src.calculations import HoldingSummary, PortfolioSummary
from src.portfolio import holdings_to_dataframe, transactions_to_dataframe


def export_holdings_to_csv(holdings: List[HoldingSummary], file_path: Optional[str] = None) -> str:
    """
    Export holdings to a clean CSV formatted string, optionally saving to file_path.
    """
    df = holdings_to_dataframe(holdings)
    csv_str = df.to_csv(index=False)
    if file_path:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(csv_str)
    return csv_str


def export_transactions_to_csv(
    transactions: List[Dict[str, Any]], file_path: Optional[str] = None
) -> str:
    """
    Export transactions to CSV string, optionally saving to file_path.
    """
    df = transactions_to_dataframe(transactions)
    csv_str = df.to_csv(index=False)
    if file_path:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(csv_str)
    return csv_str


def export_portfolio_summary_to_csv(
    summary: PortfolioSummary,
    currency: str = "$",
    file_path: Optional[str] = None,
) -> str:
    """
    Export executive portfolio metrics as a structured CSV.
    """
    rows = [
        {"Metric": "Report Generated At", "Value": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        {"Metric": "Distinct Stocks Held", "Value": summary.distinct_stocks_count},
        {"Metric": "Total Transactions Completed", "Value": summary.total_transactions_count},
        {"Metric": f"Total Invested Cost Basis ({currency})", "Value": f"{summary.total_invested_cost_basis:,.2f}"},
        {"Metric": f"Portfolio Current Market Value ({currency})", "Value": f"{summary.total_market_value:,.2f}"},
        {"Metric": f"Unrealized Profit/Loss ({currency})", "Value": f"{summary.total_unrealized_pnl:,.2f}"},
        {"Metric": "Overall Unrealized Return (%)", "Value": f"{summary.overall_unrealized_return_pct:.2f}%"},
        {"Metric": f"Realized Profit/Loss ({currency})", "Value": f"{summary.total_realized_pnl:,.2f}"},
        {"Metric": f"Total Net Profit/Loss ({currency})", "Value": f"{summary.total_net_pnl:,.2f}"},
        {"Metric": f"Total Brokerage & Fees Paid ({currency})", "Value": f"{summary.total_fees_paid:,.2f}"},
        {"Metric": "Holdings with Known Price", "Value": summary.holdings_with_price_count},
        {"Metric": "Holdings with Missing Price", "Value": summary.holdings_missing_price_count},
    ]
    df = pd.DataFrame(rows)
    csv_str = df.to_csv(index=False)
    if file_path:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(csv_str)
    return csv_str


def generate_portfolio_summary_txt(
    summary: PortfolioSummary,
    holdings: List[HoldingSummary],
    currency: str = "$",
    file_path: Optional[str] = None,
) -> str:
    """
    Generate a human-readable plain text executive summary report.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    divider = "=" * 80
    sub_divider = "-" * 80

    lines = [
        divider,
        "                   STOCK PORTFOLIO PERFORMANCE REPORT",
        f"                   Generated on: {now_str}",
        divider,
        "",
        "1. EXECUTIVE SUMMARY",
        sub_divider,
        f"  Total Invested (Cost Basis) : {currency}{summary.total_invested_cost_basis:,.2f}",
        f"  Current Market Value        : {currency}{summary.total_market_value:,.2f}",
        f"  Unrealized Profit / Loss    : {currency}{summary.total_unrealized_pnl:,.2f} ({summary.overall_unrealized_return_pct:+.2f}%)",
        f"  Realized Profit / Loss      : {currency}{summary.total_realized_pnl:,.2f}",
        f"  Total Net Profit / Loss     : {currency}{summary.total_net_pnl:,.2f}",
        f"  Total Fees Incurred         : {currency}{summary.total_fees_paid:,.2f}",
        f"  Distinct Active Stocks      : {summary.distinct_stocks_count}",
        f"  Total Transactions Count    : {summary.total_transactions_count}",
        f"  Holdings With Live Price    : {summary.holdings_with_price_count}",
        f"  Holdings Without Price      : {summary.holdings_missing_price_count}",
        "",
        "2. CURRENT HOLDINGS BREAKDOWN",
        sub_divider,
        f"{'Symbol':<8} {'Qty':>10} {'Avg Cost':>12} {'Cost Basis':>12} {'Price':>12} {'Mkt Value':>12} {'P&L':>12} {'Source':<10}",
        sub_divider,
    ]

    active_holdings = [h for h in holdings if h.quantity > 0]
    if not active_holdings:
        lines.append("  (No active holdings currently in portfolio)")
    else:
        for h in active_holdings:
            price_str = f"{currency}{h.latest_price:,.2f}" if h.latest_price is not None else "N/A"
            mkt_str = f"{currency}{h.market_value:,.2f}" if h.market_value is not None else "N/A"
            pnl_str = f"{currency}{h.unrealized_pnl:,.2f}" if h.unrealized_pnl is not None else "N/A"
            lines.append(
                f"{h.symbol:<8} {h.quantity:>10.4f} {currency}{h.average_purchase_price:>11.2f} "
                f"{currency}{h.total_cost_basis:>11.2f} {price_str:>12} {mkt_str:>12} {pnl_str:>12} {h.price_source:<10}"
            )

    lines.extend([
        "",
        "3. CLOSED POSITIONS SUMMARY (REALIZED P&L)",
        sub_divider,
    ])

    closed_holdings = [h for h in holdings if h.quantity == 0 and h.realized_pnl != 0]
    if not closed_holdings:
        lines.append("  (No realized gains/losses from closed positions)")
    else:
        for h in closed_holdings:
            lines.append(
                f"  {h.symbol:<8} Realized P&L: {currency}{h.realized_pnl:>10.2f}  "
                f"(Fees: {currency}{h.total_purchase_fees + h.total_sale_fees:,.2f})"
            )

    lines.extend([
        "",
        divider,
        "DISCLAIMER: This report is generated by CodeAlpha Stock Portfolio Tracker.",
        "Calculations use the Weighted-Average Cost Basis (WACB) method.",
        "Past market performance is no guarantee of future returns.",
        divider,
    ])

    txt_content = "\n".join(lines)
    if file_path:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(txt_content)
    return txt_content
