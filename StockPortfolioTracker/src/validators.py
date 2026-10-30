"""
Input Validation Module for Stock Portfolio Tracker.

Provides comprehensive validation for transaction attributes:
- Stock symbols (e.g. AAPL, MSFT, BRK.B)
- Transaction types (BUY, SELL)
- Quantities, prices, fees
- Transaction dates (valid format and not in the future)
- Portfolio sell constraints (cannot sell more than available)
"""

from datetime import date, datetime
import re
from typing import Any, Dict, Optional, Union


class ValidationError(ValueError):
    """Custom exception raised when user input fails business rule validation."""
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message)
        self.field = field


def validate_symbol(symbol: Any) -> str:
    """
    Validate and normalize a stock ticker symbol.

    Rules:
    - Must be a non-empty string.
    - Stripped and converted to uppercase.
    - 1 to 10 characters long.
    - Allowed characters: uppercase letters, digits, dots, and hyphens (e.g. BRK.B, BF-B).
    """
    if symbol is None:
        raise ValidationError("Stock symbol cannot be empty.", field="symbol")

    clean_symbol = str(symbol).strip().upper()
    if not clean_symbol:
        raise ValidationError("Stock symbol cannot be empty or blank.", field="symbol")

    if len(clean_symbol) > 10:
        raise ValidationError(
            f"Stock symbol '{clean_symbol}' exceeds maximum length of 10 characters.",
            field="symbol",
        )

    # Standard ticker pattern: letters, numbers, dot, hyphen (e.g., AAPL, 005930.KS, BRK.B)
    pattern = r"^[A-Z0-9.\-]+$"
    if not re.match(pattern, clean_symbol):
        raise ValidationError(
            f"Invalid stock symbol '{clean_symbol}'. Symbols can only contain letters, numbers, dots, and hyphens.",
            field="symbol",
        )

    return clean_symbol


def validate_company_name(name: Any) -> str:
    """
    Validate and clean company name.
    Optional field; returns empty string if not provided, trimmed to max 100 characters.
    """
    if name is None:
        return ""
    clean_name = str(name).strip()
    if len(clean_name) > 100:
        return clean_name[:100]
    return clean_name


def validate_transaction_type(tx_type: Any) -> str:
    """
    Validate transaction type. Must be either 'BUY' or 'SELL'.
    """
    if tx_type is None:
        raise ValidationError("Transaction type is required.", field="transaction_type")

    clean_type = str(tx_type).strip().upper()
    if clean_type not in ("BUY", "SELL"):
        raise ValidationError(
            f"Invalid transaction type '{clean_type}'. Allowed types are 'BUY' or 'SELL'.",
            field="transaction_type",
        )
    return clean_type


def validate_quantity(quantity: Any) -> float:
    """
    Validate share quantity.
    Must be a positive numeric value greater than zero. Supports fractional shares.
    """
    if quantity is None:
        raise ValidationError("Quantity is required.", field="quantity")

    try:
        qty = float(quantity)
    except (ValueError, TypeError):
        raise ValidationError(
            f"Quantity must be a valid number, got '{quantity}'.", field="quantity"
        )

    if qty <= 0:
        raise ValidationError("Quantity must be strictly greater than 0.", field="quantity")

    if not (qty == qty):  # NaN check
        raise ValidationError("Quantity cannot be NaN.", field="quantity")

    # Round to reasonable precision (e.g., 6 decimal places for fractional shares)
    return round(qty, 6)


def validate_price(price: Any) -> float:
    """
    Validate price per share.
    Must be a non-negative number (>= 0.0).
    """
    if price is None:
        raise ValidationError("Price per share is required.", field="price")

    try:
        val = float(price)
    except (ValueError, TypeError):
        raise ValidationError(f"Price must be a valid number, got '{price}'.", field="price")

    if val < 0:
        raise ValidationError("Price per share cannot be negative.", field="price")

    if not (val == val):  # NaN check
        raise ValidationError("Price cannot be NaN.", field="price")

    return round(val, 4)


def validate_fee(fee: Any = 0.0) -> float:
    """
    Validate brokerage / transaction fees.
    Defaults to 0.0, must be non-negative.
    """
    if fee is None or fee == "":
        return 0.0

    try:
        val = float(fee)
    except (ValueError, TypeError):
        raise ValidationError(f"Fee must be a valid number, got '{fee}'.", field="fee")

    if val < 0:
        raise ValidationError("Brokerage/transaction fees cannot be negative.", field="fee")

    if not (val == val):  # NaN check
        raise ValidationError("Fee cannot be NaN.", field="fee")

    return round(val, 4)


def validate_date(date_val: Any) -> str:
    """
    Validate transaction date.
    Must be in YYYY-MM-DD format (or date/datetime object) and cannot be in the future.
    Returns ISO formatted date string 'YYYY-MM-DD'.
    """
    if date_val is None:
        raise ValidationError("Transaction date is required.", field="date")

    parsed_date: date
    if isinstance(date_val, datetime):
        parsed_date = date_val.date()
    elif isinstance(date_val, date):
        parsed_date = date_val
    elif isinstance(date_val, str):
        clean_str = date_val.strip()
        try:
            parsed_date = datetime.strptime(clean_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError(
                f"Invalid date format '{clean_str}'. Expected 'YYYY-MM-DD'.", field="date"
            )
    else:
        raise ValidationError(
            f"Unsupported date type: {type(date_val).__name__}", field="date"
        )

    today = date.today()
    if parsed_date > today:
        raise ValidationError(
            f"Transaction date ({parsed_date}) cannot be in the future (today is {today}).",
            field="date",
        )

    return parsed_date.strftime("%Y-%m-%d")


def validate_notes(notes: Any) -> str:
    """Validate optional notes. Trims and limits to 500 characters."""
    if notes is None:
        return ""
    clean = str(notes).strip()
    if len(clean) > 500:
        return clean[:500]
    return clean


def validate_sell_quantity(sell_qty: float, available_qty: float, symbol: str) -> None:
    """
    Verify that user is not attempting to sell more shares than they currently own.
    """
    # Small tolerance for floating point imprecision
    tolerance = 1e-7
    if sell_qty > (available_qty + tolerance):
        raise ValidationError(
            f"Cannot sell {sell_qty:g} shares of {symbol}. "
            f"You only own {available_qty:g} shares.",
            field="quantity",
        )


def validate_transaction(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate an entire transaction dictionary and return clean, typed data.
    """
    if not isinstance(data, dict):
        raise ValidationError("Transaction data must be a dictionary.")

    symbol = validate_symbol(data.get("symbol"))
    company_name = validate_company_name(data.get("company_name", ""))
    tx_type = validate_transaction_type(data.get("transaction_type"))
    quantity = validate_quantity(data.get("quantity"))
    price = validate_price(data.get("price"))
    fees = validate_fee(data.get("fees", 0.0))
    tx_date = validate_date(data.get("date", date.today()))
    notes = validate_notes(data.get("notes", ""))

    return {
        "symbol": symbol,
        "company_name": company_name,
        "transaction_type": tx_type,
        "quantity": quantity,
        "price": price,
        "fees": fees,
        "date": tx_date,
        "notes": notes,
    }
