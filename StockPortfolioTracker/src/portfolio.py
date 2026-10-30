"""
Portfolio Management and Aggregation Module.

Connects database transactions with market price data and calculation engines
to produce holding-level and portfolio-wide reporting models.
"""

from typing import Any, Dict, List, Optional
import pandas as pd

from src.calculations import (
    HoldingSummary,
    PortfolioSummary,
    calculate_portfolio_summary,
    process_transactions_for_symbol,
)
from src.database import get_all_transactions


def get_all_portfolio_holdings(
    price_data: Optional[Dict[str, Dict[str, Any]]] = None,
    db_path: Optional[str] = None,
) -> List[HoldingSummary]:
    """
    Retrieve all transactions from the database and compute holding summaries
    for every recorded stock symbol (both active and closed).

    `price_data` is an optional dictionary mapping uppercase symbol to:
    {
        "price": float,
        "source": "LIVE" | "CACHED" | "MANUAL" | "UNAVAILABLE",
        "timestamp": str,
    }
    """
    if price_data is None:
        price_data = {}

    # Fetch all transactions ordered chronologically
    txs = get_all_transactions(order_by_desc=False, db_path=db_path)
    if not txs:
        return []

    # Group transactions by symbol
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for tx in txs:
        sym = tx["symbol"].upper()
        if sym not in grouped:
            grouped[sym] = []
        grouped[sym].append(tx)

    summaries: List[HoldingSummary] = []
    for symbol, symbol_txs in grouped.items():
        market_info = price_data.get(symbol, {})
        current_price = market_info.get("price")
        price_source = market_info.get("source", "UNAVAILABLE")
        price_timestamp = market_info.get("timestamp")

        summary = process_transactions_for_symbol(
            transactions=symbol_txs,
            current_price=current_price,
            price_source=price_source,
            price_timestamp=price_timestamp,
        )
        summaries.append(summary)

    # Sort: active holdings first by market value / cost basis descending, then closed holdings
    summaries.sort(
        key=lambda h: (
            1 if h.quantity > 0 else 0,
            h.market_value if h.market_value is not None else h.total_cost_basis,
        ),
        reverse=True,
    )
    return summaries


def get_active_holdings(
    price_data: Optional[Dict[str, Dict[str, Any]]] = None,
    db_path: Optional[str] = None,
) -> List[HoldingSummary]:
    """Return only active holdings (quantity > 0)."""
    all_holdings = get_all_portfolio_holdings(price_data=price_data, db_path=db_path)
    return [h for h in all_holdings if h.quantity > 0]


def get_closed_holdings(
    price_data: Optional[Dict[str, Dict[str, Any]]] = None,
    db_path: Optional[str] = None,
) -> List[HoldingSummary]:
    """Return closed positions (quantity == 0)."""
    all_holdings = get_all_portfolio_holdings(price_data=price_data, db_path=db_path)
    return [h for h in all_holdings if h.quantity == 0]


def get_portfolio_overview(
    price_data: Optional[Dict[str, Dict[str, Any]]] = None,
    db_path: Optional[str] = None,
) -> PortfolioSummary:
    """
    Compute aggregate portfolio-level summary.
    """
    all_holdings = get_all_portfolio_holdings(price_data=price_data, db_path=db_path)
    txs = get_all_transactions(db_path=db_path)
    return calculate_portfolio_summary(all_holdings, total_transactions_count=len(txs))


def holdings_to_dataframe(holdings: List[HoldingSummary]) -> pd.DataFrame:
    """
    Convert a list of HoldingSummary objects into a structured pandas DataFrame.
    """
    if not holdings:
        return pd.DataFrame(
            columns=[
                "Symbol",
                "Company Name",
                "Quantity Owned",
                "Avg Purchase Price",
                "Total Cost Basis",
                "Latest Price",
                "Market Value",
                "Unrealized P&L",
                "Return %",
                "Realized P&L",
                "Price Source",
                "Price Updated At",
            ]
        )

    rows = []
    for h in holdings:
        rows.append(
            {
                "Symbol": h.symbol,
                "Company Name": h.company_name or "-",
                "Quantity Owned": h.quantity,
                "Avg Purchase Price": h.average_purchase_price,
                "Total Cost Basis": h.total_cost_basis,
                "Latest Price": h.latest_price if h.latest_price is not None else float("nan"),
                "Market Value": h.market_value if h.market_value is not None else float("nan"),
                "Unrealized P&L": h.unrealized_pnl if h.unrealized_pnl is not None else float("nan"),
                "Return %": h.unrealized_return_pct if h.unrealized_return_pct is not None else float("nan"),
                "Realized P&L": h.realized_pnl,
                "Price Source": h.price_source,
                "Price Updated At": h.price_timestamp or "Never",
            }
        )

    return pd.DataFrame(rows)


def transactions_to_dataframe(transactions: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Convert a list of transaction dictionaries into a formatted pandas DataFrame.
    """
    if not transactions:
        return pd.DataFrame(
            columns=[
                "ID",
                "Date",
                "Symbol",
                "Company Name",
                "Type",
                "Quantity",
                "Price",
                "Fees",
                "Total Value",
                "Notes",
            ]
        )

    rows = []
    for tx in transactions:
        qty = float(tx.get("quantity", 0))
        price = float(tx.get("price", 0))
        fee = float(tx.get("fees", 0))
        tx_type = tx.get("transaction_type", "")

        # Total transaction value (cash impact):
        # BUY: (qty * price) + fee
        # SELL: (qty * price) - fee
        if tx_type == "BUY":
            total_val = round((qty * price) + fee, 2)
        else:
            total_val = round((qty * price) - fee, 2)

        rows.append(
            {
                "ID": tx.get("id"),
                "Date": tx.get("transaction_date"),
                "Symbol": tx.get("symbol"),
                "Company Name": tx.get("company_name") or "-",
                "Type": tx_type,
                "Quantity": qty,
                "Price": price,
                "Fees": fee,
                "Total Value": total_val,
                "Notes": tx.get("notes") or "",
            }
        )

    return pd.DataFrame(rows)
