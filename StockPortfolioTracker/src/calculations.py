"""
Financial Calculation Engine for Stock Portfolio Tracker.

Implements the Weighted-Average Cost Basis (WACB) accounting method,
handling:
- Purchase cost and purchase fee allocation
- Proportional cost-basis reduction on partial and full sales
- Realized profit/loss calculation accounting for sale fees
- Unrealized profit/loss calculation based on market prices
- Portfolio-wide metrics and return percentages with zero-division safety
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class HoldingSummary:
    """Represents calculated state for a single stock holding."""
    symbol: str
    company_name: str = ""
    quantity: float = 0.0
    total_cost_basis: float = 0.0
    average_purchase_price: float = 0.0
    latest_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_return_pct: Optional[float] = None
    realized_pnl: float = 0.0
    total_purchase_fees: float = 0.0
    total_sale_fees: float = 0.0
    price_source: str = "UNAVAILABLE"  # LIVE, CACHED, MANUAL, UNAVAILABLE
    price_timestamp: Optional[str] = None


@dataclass
class PortfolioSummary:
    """Represents aggregate summary across the entire portfolio."""
    total_invested_cost_basis: float = 0.0
    total_market_value: float = 0.0
    total_unrealized_pnl: float = 0.0
    total_realized_pnl: float = 0.0
    total_net_pnl: float = 0.0
    overall_unrealized_return_pct: float = 0.0
    distinct_stocks_count: int = 0
    total_transactions_count: int = 0
    holdings_with_price_count: int = 0
    holdings_missing_price_count: int = 0
    total_fees_paid: float = 0.0


def calculate_buy_cost(quantity: float, price: float, fee: float = 0.0) -> float:
    """
    Calculate total purchase cost including brokerage and transaction fees.
    Total Purchase Cost = (Quantity * Price) + Fee
    """
    if quantity < 0 or price < 0 or fee < 0:
        raise ValueError("Quantity, price, and fee must be non-negative.")
    return round((quantity * price) + fee, 4)


def calculate_sale_proceeds(quantity: float, price: float, fee: float = 0.0) -> float:
    """
    Calculate net sale proceeds after deducting transaction fees.
    Net Proceeds = (Quantity * Price) - Fee
    """
    if quantity < 0 or price < 0 or fee < 0:
        raise ValueError("Quantity, price, and fee must be non-negative.")
    return round((quantity * price) - fee, 4)


def calculate_realized_pnl(
    sold_quantity: float,
    sale_price: float,
    sale_fee: float,
    average_cost_basis_per_share: float,
) -> Dict[str, float]:
    """
    Calculate realized profit or loss on the sale of shares.

    Methodology:
    1. Gross Sale Value = sold_quantity * sale_price
    2. Net Sale Proceeds = Gross Sale Value - sale_fee
    3. Cost Basis of Shares Sold = sold_quantity * average_cost_basis_per_share
    4. Realized PnL = Net Sale Proceeds - Cost Basis of Shares Sold

    Returns dictionary with:
    - cost_basis_sold
    - gross_proceeds
    - net_proceeds
    - realized_pnl
    """
    if sold_quantity <= 0:
        raise ValueError("Sold quantity must be greater than 0.")
    if sale_price < 0 or sale_fee < 0 or average_cost_basis_per_share < 0:
        raise ValueError("Sale price, fees, and average cost basis must be non-negative.")

    cost_basis_sold = sold_quantity * average_cost_basis_per_share
    gross_proceeds = sold_quantity * sale_price
    net_proceeds = gross_proceeds - sale_fee
    realized_pnl = net_proceeds - cost_basis_sold

    return {
        "cost_basis_sold": round(cost_basis_sold, 4),
        "gross_proceeds": round(gross_proceeds, 4),
        "net_proceeds": round(net_proceeds, 4),
        "realized_pnl": round(realized_pnl, 4),
    }


def calculate_return_percentage(profit_or_loss: float, capital_invested: float) -> float:
    """
    Safely calculate percentage return.
    Return % = (Profit_or_Loss / Capital_Invested) * 100.
    Returns 0.0 if capital_invested <= 0.
    """
    if not capital_invested or capital_invested <= 0:
        return 0.0
    return round((profit_or_loss / capital_invested) * 100, 2)


def process_transactions_for_symbol(
    transactions: List[Dict[str, Any]],
    current_price: Optional[float] = None,
    price_source: str = "UNAVAILABLE",
    price_timestamp: Optional[str] = None,
) -> HoldingSummary:
    """
    Process a chronological sequence of transactions for a single stock symbol
    using the Weighted-Average Cost Basis (WACB) method.

    Transactions list must contain dicts with:
    - symbol
    - company_name (optional)
    - transaction_type ('BUY' or 'SELL')
    - quantity (positive number)
    - price (non-negative number)
    - fees (non-negative number)
    - date (string or date)
    """
    if not transactions:
        return HoldingSummary(symbol="")

    symbol = transactions[0].get("symbol", "").upper()
    company_name = transactions[0].get("company_name", "")

    current_qty = 0.0
    cost_basis = 0.0
    realized_pnl_acc = 0.0
    purchase_fees_acc = 0.0
    sale_fees_acc = 0.0

    for tx in transactions:
        tx_type = tx.get("transaction_type", "").upper()
        qty = float(tx.get("quantity", 0.0))
        price = float(tx.get("price", 0.0))
        fee = float(tx.get("fees", 0.0))
        c_name = tx.get("company_name")
        if c_name:
            company_name = c_name

        if qty <= 0:
            continue

        if tx_type == "BUY":
            buy_cost = (qty * price) + fee
            current_qty += qty
            cost_basis += buy_cost
            purchase_fees_acc += fee

        elif tx_type == "SELL":
            sale_fees_acc += fee
            if current_qty > 0:
                avg_cost = cost_basis / current_qty
                # Cost of shares being sold
                sold_cost = qty * avg_cost
                # Realized PnL = (qty * price) - fee - sold_cost
                pnl = (qty * price) - fee - sold_cost
                realized_pnl_acc += pnl

                current_qty -= qty
                cost_basis -= sold_cost

                # Handle full closure and micro floating point remnants
                if current_qty <= 1e-7:
                    current_qty = 0.0
                    cost_basis = 0.0
                else:
                    cost_basis = max(0.0, cost_basis)

    # Average cost per remaining share
    avg_price = (cost_basis / current_qty) if current_qty > 0 else 0.0

    # Market evaluation
    market_val = None
    unrealized_pnl = None
    unrealized_return = None

    if current_price is not None and current_price >= 0:
        market_val = round(current_qty * current_price, 4)
        unrealized_pnl = round(market_val - cost_basis, 4)
        unrealized_return = calculate_return_percentage(unrealized_pnl, cost_basis)

    return HoldingSummary(
        symbol=symbol,
        company_name=company_name,
        quantity=round(current_qty, 6),
        total_cost_basis=round(cost_basis, 4),
        average_purchase_price=round(avg_price, 4),
        latest_price=current_price,
        market_value=market_val,
        unrealized_pnl=unrealized_pnl,
        unrealized_return_pct=unrealized_return,
        realized_pnl=round(realized_pnl_acc, 4),
        total_purchase_fees=round(purchase_fees_acc, 4),
        total_sale_fees=round(sale_fees_acc, 4),
        price_source=price_source,
        price_timestamp=price_timestamp,
    )


def calculate_portfolio_summary(
    holdings: List[HoldingSummary],
    total_transactions_count: int = 0,
) -> PortfolioSummary:
    """
    Aggregate portfolio-level metrics from a list of holding summaries.
    Only active holdings (quantity > 0) contribute to total invested cost basis
    and current market value.
    Realized profit/loss includes closed and partially closed positions.
    """
    total_cost_basis = 0.0
    total_market_val = 0.0
    total_unrealized_pnl = 0.0
    total_realized_pnl = 0.0
    distinct_stocks = 0
    priced_holdings = 0
    unpriced_holdings = 0
    total_fees = 0.0

    for h in holdings:
        total_realized_pnl += h.realized_pnl
        total_fees += (h.total_purchase_fees + h.total_sale_fees)

        if h.quantity > 0:
            distinct_stocks += 1
            total_cost_basis += h.total_cost_basis

            if h.market_value is not None:
                priced_holdings += 1
                total_market_val += h.market_value
                if h.unrealized_pnl is not None:
                    total_unrealized_pnl += h.unrealized_pnl
            else:
                unpriced_holdings += 1

    total_net_pnl = total_unrealized_pnl + total_realized_pnl
    overall_return_pct = calculate_return_percentage(total_unrealized_pnl, total_cost_basis)

    return PortfolioSummary(
        total_invested_cost_basis=round(total_cost_basis, 2),
        total_market_value=round(total_market_val, 2),
        total_unrealized_pnl=round(total_unrealized_pnl, 2),
        total_realized_pnl=round(total_realized_pnl, 2),
        total_net_pnl=round(total_net_pnl, 2),
        overall_unrealized_return_pct=overall_return_pct,
        distinct_stocks_count=distinct_stocks,
        total_transactions_count=total_transactions_count,
        holdings_with_price_count=priced_holdings,
        holdings_missing_price_count=unpriced_holdings,
        total_fees_paid=round(total_fees, 2),
    )
