"""
Unit Tests for Validators Module.
"""

from datetime import date, timedelta
import pytest
from src.validators import (
    ValidationError,
    validate_symbol,
    validate_company_name,
    validate_transaction_type,
    validate_quantity,
    validate_price,
    validate_fee,
    validate_date,
    validate_notes,
    validate_sell_quantity,
    validate_transaction,
)


class TestValidators:
    def test_validate_symbol_valid(self):
        assert validate_symbol("aapl") == "AAPL"
        assert validate_symbol("msft ") == "MSFT"
        assert validate_symbol("BRK.B") == "BRK.B"
        assert validate_symbol("BF-B") == "BF-B"
        assert validate_symbol("7203.T") == "7203.T"

    def test_validate_symbol_invalid(self):
        with pytest.raises(ValidationError):
            validate_symbol("")
        with pytest.raises(ValidationError):
            validate_symbol("   ")
        with pytest.raises(ValidationError):
            validate_symbol(None)
        with pytest.raises(ValidationError):
            validate_symbol("TOOLONGSYMBOLNAME")
        with pytest.raises(ValidationError):
            validate_symbol("AAPL@!")

    def test_validate_company_name(self):
        assert validate_company_name(" Apple Inc. ") == "Apple Inc."
        assert validate_company_name(None) == ""
        long_name = "A" * 150
        assert len(validate_company_name(long_name)) == 100

    def test_validate_transaction_type_valid(self):
        assert validate_transaction_type("buy") == "BUY"
        assert validate_transaction_type("SELL") == "SELL"
        assert validate_transaction_type(" Buy ") == "BUY"

    def test_validate_transaction_type_invalid(self):
        with pytest.raises(ValidationError):
            validate_transaction_type("HOLD")
        with pytest.raises(ValidationError):
            validate_transaction_type("")
        with pytest.raises(ValidationError):
            validate_transaction_type(None)

    def test_validate_quantity_valid(self):
        assert validate_quantity(10) == 10.0
        assert validate_quantity("5.5") == 5.5
        assert validate_quantity(0.0001) == 0.0001

    def test_validate_quantity_invalid(self):
        with pytest.raises(ValidationError):
            validate_quantity(0)
        with pytest.raises(ValidationError):
            validate_quantity(-10)
        with pytest.raises(ValidationError):
            validate_quantity("not_a_number")
        with pytest.raises(ValidationError):
            validate_quantity(None)

    def test_validate_price_valid(self):
        assert validate_price(150.25) == 150.25
        assert validate_price("0") == 0.0
        assert validate_price(0.0) == 0.0

    def test_validate_price_invalid(self):
        with pytest.raises(ValidationError):
            validate_price(-5)
        with pytest.raises(ValidationError):
            validate_price("invalid")
        with pytest.raises(ValidationError):
            validate_price(None)

    def test_validate_fee(self):
        assert validate_fee(0) == 0.0
        assert validate_fee("2.50") == 2.50
        assert validate_fee(None) == 0.0
        assert validate_fee("") == 0.0
        with pytest.raises(ValidationError):
            validate_fee(-1.0)
        with pytest.raises(ValidationError):
            validate_fee("invalid")

    def test_validate_date(self):
        today = date.today()
        past = today - timedelta(days=10)
        future = today + timedelta(days=5)

        assert validate_date(past.strftime("%Y-%m-%d")) == past.strftime("%Y-%m-%d")
        assert validate_date(today) == today.strftime("%Y-%m-%d")

        with pytest.raises(ValidationError, match="cannot be in the future"):
            validate_date(future.strftime("%Y-%m-%d"))

        with pytest.raises(ValidationError, match="Invalid date format"):
            validate_date("12/31/2023")

        with pytest.raises(ValidationError):
            validate_date(None)

    def test_validate_notes(self):
        assert validate_notes("  Test note  ") == "Test note"
        assert validate_notes(None) == ""
        assert len(validate_notes("X" * 600)) == 500

    def test_validate_sell_quantity(self):
        # Selling available amount or less should succeed
        validate_sell_quantity(10.0, 10.0, "AAPL")
        validate_sell_quantity(5.0, 10.0, "AAPL")

        # Selling more than owned should raise ValidationError
        with pytest.raises(ValidationError, match="Cannot sell 15 shares"):
            validate_sell_quantity(15.0, 10.0, "AAPL")

    def test_validate_transaction_dict(self):
        raw = {
            "symbol": "aapl",
            "company_name": "Apple",
            "transaction_type": "buy",
            "quantity": "10",
            "price": "150.00",
            "fees": "1.50",
            "date": "2024-01-01",
            "notes": "First trade",
        }
        clean = validate_transaction(raw)
        assert clean["symbol"] == "AAPL"
        assert clean["company_name"] == "Apple"
        assert clean["transaction_type"] == "BUY"
        assert clean["quantity"] == 10.0
        assert clean["price"] == 150.0
        assert clean["fees"] == 1.5
        assert clean["date"] == "2024-01-01"
        assert clean["notes"] == "First trade"
