"""
Unit Tests for Database Module.
"""

from datetime import date, timedelta
import os
import tempfile
import pytest

from src.database import (
    init_db,
    add_transaction,
    get_transaction,
    get_all_transactions,
    get_holding_quantity,
    update_transaction,
    delete_transaction,
    backup_database,
)
from src.validators import ValidationError


@pytest.fixture
def temp_db():
    """Create a temporary database file for isolated testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    if os.path.exists(path):
        os.remove(path)


class TestDatabase:
    def test_database_initialization(self, temp_db):
        # Database initialized by fixture; verify transactions table is empty
        txs = get_all_transactions(db_path=temp_db)
        assert txs == []

    def test_add_buy_transaction(self, temp_db):
        tx_id = add_transaction(
            {
                "symbol": "AAPL",
                "company_name": "Apple Inc.",
                "transaction_type": "BUY",
                "quantity": 10.0,
                "price": 150.0,
                "fees": 5.0,
                "date": "2024-01-10",
                "notes": "Initial purchase",
            },
            db_path=temp_db,
        )
        assert tx_id > 0

        saved = get_transaction(tx_id, db_path=temp_db)
        assert saved is not None
        assert saved["symbol"] == "AAPL"
        assert saved["quantity"] == 10.0
        assert saved["price"] == 150.0
        assert saved["fees"] == 5.0
        assert get_holding_quantity("AAPL", db_path=temp_db) == 10.0

    def test_add_sell_transaction_success(self, temp_db):
        # First buy 10 shares
        add_transaction(
            {
                "symbol": "MSFT",
                "company_name": "Microsoft",
                "transaction_type": "BUY",
                "quantity": 10.0,
                "price": 300.0,
                "fees": 2.0,
                "date": "2024-01-10",
            },
            db_path=temp_db,
        )
        # Sell 4 shares
        sell_id = add_transaction(
            {
                "symbol": "MSFT",
                "transaction_type": "SELL",
                "quantity": 4.0,
                "price": 350.0,
                "fees": 2.0,
                "date": "2024-01-15",
            },
            db_path=temp_db,
        )
        assert sell_id > 0
        assert get_holding_quantity("MSFT", db_path=temp_db) == 6.0

    def test_prevent_overselling(self, temp_db):
        # Buy 5 shares of NVDA
        add_transaction(
            {
                "symbol": "NVDA",
                "transaction_type": "BUY",
                "quantity": 5.0,
                "price": 500.0,
                "fees": 1.0,
                "date": "2024-01-10",
            },
            db_path=temp_db,
        )

        # Attempt to sell 6 shares
        with pytest.raises(ValidationError, match="Cannot sell 6 shares"):
            add_transaction(
                {
                    "symbol": "NVDA",
                    "transaction_type": "SELL",
                    "quantity": 6.0,
                    "price": 600.0,
                    "fees": 1.0,
                    "date": "2024-01-15",
                },
                db_path=temp_db,
            )

        # Holdings should still remain 5
        assert get_holding_quantity("NVDA", db_path=temp_db) == 5.0

    def test_reject_invalid_transactions(self, temp_db):
        # Invalid symbol
        with pytest.raises(ValidationError):
            add_transaction(
                {"symbol": "", "transaction_type": "BUY", "quantity": 10, "price": 100, "date": "2024-01-01"},
                db_path=temp_db,
            )

        # Zero quantity
        with pytest.raises(ValidationError):
            add_transaction(
                {"symbol": "AAPL", "transaction_type": "BUY", "quantity": 0, "price": 100, "date": "2024-01-01"},
                db_path=temp_db,
            )

        # Future date
        future = (date.today() + timedelta(days=2)).strftime("%Y-%m-%d")
        with pytest.raises(ValidationError):
            add_transaction(
                {"symbol": "AAPL", "transaction_type": "BUY", "quantity": 10, "price": 100, "date": future},
                db_path=temp_db,
            )

    def test_update_and_delete_transaction(self, temp_db):
        tx_id = add_transaction(
            {
                "symbol": "GOOGL",
                "transaction_type": "BUY",
                "quantity": 10.0,
                "price": 100.0,
                "fees": 0.0,
                "date": "2024-01-10",
            },
            db_path=temp_db,
        )

        # Update quantity to 12
        update_transaction(
            tx_id,
            {
                "symbol": "GOOGL",
                "transaction_type": "BUY",
                "quantity": 12.0,
                "price": 100.0,
                "fees": 0.0,
                "date": "2024-01-10",
            },
            db_path=temp_db,
        )
        assert get_holding_quantity("GOOGL", db_path=temp_db) == 12.0

        # Now delete transaction
        delete_transaction(tx_id, db_path=temp_db)
        assert get_holding_quantity("GOOGL", db_path=temp_db) == 0.0
        assert get_transaction(tx_id, db_path=temp_db) is None

    def test_prevent_destructive_update_or_delete(self, temp_db):
        # Buy 10, Sell 8
        buy_id = add_transaction(
            {"symbol": "AMZN", "transaction_type": "BUY", "quantity": 10.0, "price": 100.0, "date": "2024-01-01"},
            db_path=temp_db,
        )
        add_transaction(
            {"symbol": "AMZN", "transaction_type": "SELL", "quantity": 8.0, "price": 120.0, "date": "2024-01-05"},
            db_path=temp_db,
        )

        # Attempt to delete the BUY - would leave SELL with -8 shares!
        with pytest.raises(ValidationError, match="negative holdings"):
            delete_transaction(buy_id, db_path=temp_db)

        # Attempt to reduce the BUY to 5 shares - would leave SELL with -3 shares!
        with pytest.raises(ValidationError, match="negative share balance"):
            update_transaction(
                buy_id,
                {"symbol": "AMZN", "transaction_type": "BUY", "quantity": 5.0, "price": 100.0, "date": "2024-01-01"},
                db_path=temp_db,
            )

    def test_filter_transactions(self, temp_db):
        add_transaction({"symbol": "AAPL", "transaction_type": "BUY", "quantity": 10, "price": 100, "date": "2024-01-01"}, db_path=temp_db)
        add_transaction({"symbol": "MSFT", "transaction_type": "BUY", "quantity": 5, "price": 200, "date": "2024-01-10"}, db_path=temp_db)
        add_transaction({"symbol": "AAPL", "transaction_type": "SELL", "quantity": 2, "price": 110, "date": "2024-01-20"}, db_path=temp_db)

        # Filter by symbol
        aapl_txs = get_all_transactions(symbol="AAPL", db_path=temp_db)
        assert len(aapl_txs) == 2

        # Filter by type
        sell_txs = get_all_transactions(tx_type="SELL", db_path=temp_db)
        assert len(sell_txs) == 1
        assert sell_txs[0]["symbol"] == "AAPL"

        # Filter by date range
        jan_early = get_all_transactions(start_date="2024-01-01", end_date="2024-01-05", db_path=temp_db)
        assert len(jan_early) == 1
        assert jan_early[0]["symbol"] == "AAPL"

    def test_database_backup(self, temp_db):
        add_transaction({"symbol": "TSLA", "transaction_type": "BUY", "quantity": 10, "price": 200, "date": "2024-01-01"}, db_path=temp_db)
        fd, backup_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            saved_path = backup_database(backup_path, db_path=temp_db)
            assert os.path.exists(saved_path)
            # Verify backup has the data
            txs = get_all_transactions(db_path=backup_path)
            assert len(txs) == 1
            assert txs[0]["symbol"] == "TSLA"
        finally:
            if os.path.exists(backup_path):
                os.remove(backup_path)
