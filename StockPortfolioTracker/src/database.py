"""
Database Management Module for Stock Portfolio Tracker.

Handles SQLite storage with:
- Schema initialization and index creation
- Parameterized CRUD operations for transactions
- Transactional integrity and rollback on failure
- Holdings consistency enforcement (preventing overselling)
- Safe live database backup using SQLite's backup API
"""

from datetime import datetime
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from src.validators import (
    ValidationError,
    validate_sell_quantity,
    validate_transaction,
)

DEFAULT_DB_PATH = os.environ.get("DATABASE_PATH", os.path.join("data", "portfolio.db"))


def resolve_db_path(db_path: Optional[str] = None) -> str:
    """Resolve database path, falling back to environment or default."""
    if db_path:
        return db_path
    return os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH)


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Establish and return a SQLite database connection with row factory enabled.
    Creates parent directories if necessary for file-based paths.
    """
    path = resolve_db_path(db_path)
    if path != ":memory:":
        parent = Path(path).parent
        if parent and not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """
    Initialize SQLite database schema and indices.
    Safe to call multiple times (idempotent).
    """
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    company_name TEXT,
                    transaction_type TEXT NOT NULL CHECK(transaction_type IN ('BUY', 'SELL')),
                    quantity REAL NOT NULL CHECK(quantity > 0),
                    price REAL NOT NULL CHECK(price >= 0),
                    fees REAL NOT NULL DEFAULT 0.0 CHECK(fees >= 0),
                    transaction_date TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_transactions_symbol
                ON transactions(symbol);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_transactions_date
                ON transactions(transaction_date);
                """
            )
    finally:
        conn.close()


def get_holding_quantity(symbol: str, conn: Optional[sqlite3.Connection] = None, db_path: Optional[str] = None) -> float:
    """
    Calculate the net currently owned shares for a symbol (total BUY - total SELL).
    """
    close_after = False
    if conn is None:
        conn = get_db_connection(db_path)
        close_after = True

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN transaction_type = 'BUY' THEN quantity ELSE 0 END), 0) -
                COALESCE(SUM(CASE WHEN transaction_type = 'SELL' THEN quantity ELSE 0 END), 0) AS net_qty
            FROM transactions
            WHERE symbol = ?;
            """,
            (symbol.upper(),),
        )
        row = cursor.fetchone()
        net = float(row["net_qty"]) if row and row["net_qty"] is not None else 0.0
        return max(0.0, round(net, 6))
    finally:
        if close_after:
            conn.close()


def add_transaction(transaction_data: Dict[str, Any], db_path: Optional[str] = None) -> int:
    """
    Validate and insert a new transaction into the database.
    If transaction_type is 'SELL', verifies that sufficient shares are available.
    """
    clean_data = validate_transaction(transaction_data)
    symbol = clean_data["symbol"]
    tx_type = clean_data["transaction_type"]
    qty = clean_data["quantity"]

    conn = get_db_connection(db_path)
    try:
        with conn:
            if tx_type == "SELL":
                available_qty = get_holding_quantity(symbol, conn=conn)
                validate_sell_quantity(qty, available_qty, symbol)

            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO transactions (
                    symbol, company_name, transaction_type, quantity, price, fees, transaction_date, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    clean_data["symbol"],
                    clean_data["company_name"],
                    clean_data["transaction_type"],
                    clean_data["quantity"],
                    clean_data["price"],
                    clean_data["fees"],
                    clean_data["date"],
                    clean_data["notes"],
                ),
            )
            return cursor.lastrowid
    finally:
        conn.close()


def get_transaction(tx_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve a single transaction by ID."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transactions WHERE id = ?;", (tx_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def check_symbol_chronology_valid(symbol: str, conn: sqlite3.Connection) -> bool:
    """
    Verify that in chronological order of transactions for symbol,
    running share balance never drops below zero.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT transaction_type, quantity
        FROM transactions
        WHERE symbol = ?
        ORDER BY transaction_date ASC, id ASC;
        """,
        (symbol,),
    )
    running = 0.0
    for row in cursor.fetchall():
        if row["transaction_type"] == "BUY":
            running += float(row["quantity"])
        elif row["transaction_type"] == "SELL":
            running -= float(row["quantity"])
            if running < -1e-7:
                return False
    return True


def update_transaction(tx_id: int, updated_data: Dict[str, Any], db_path: Optional[str] = None) -> bool:
    """
    Update an existing transaction with input validation and portfolio integrity verification.
    Rolls back if update results in negative holdings at any chronological point.
    """
    clean_data = validate_transaction(updated_data)
    conn = get_db_connection(db_path)
    try:
        with conn:
            # Check transaction exists
            cursor = conn.cursor()
            cursor.execute("SELECT symbol FROM transactions WHERE id = ?;", (tx_id,))
            existing = cursor.fetchone()
            if not existing:
                raise ValidationError(f"Transaction ID {tx_id} not found.")

            old_symbol = existing["symbol"]
            new_symbol = clean_data["symbol"]

            cursor.execute(
                """
                UPDATE transactions
                SET symbol = ?,
                    company_name = ?,
                    transaction_type = ?,
                    quantity = ?,
                    price = ?,
                    fees = ?,
                    transaction_date = ?,
                    notes = ?,
                    updated_at = datetime('now')
                WHERE id = ?;
                """,
                (
                    clean_data["symbol"],
                    clean_data["company_name"],
                    clean_data["transaction_type"],
                    clean_data["quantity"],
                    clean_data["price"],
                    clean_data["fees"],
                    clean_data["date"],
                    clean_data["notes"],
                    tx_id,
                ),
            )

            # Verify chronology for affected symbols
            symbols_to_check = {old_symbol, new_symbol}
            for sym in symbols_to_check:
                if not check_symbol_chronology_valid(sym, conn):
                    raise ValidationError(
                        f"Cannot update transaction: this change leaves {sym} with a negative share balance at a subsequent transaction."
                    )
            return True
    finally:
        conn.close()


def delete_transaction(tx_id: int, db_path: Optional[str] = None) -> bool:
    """
    Delete a transaction by ID.
    Validates that deleting a BUY does not leave subsequent SELLs with negative balance.
    """
    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT symbol FROM transactions WHERE id = ?;", (tx_id,))
            existing = cursor.fetchone()
            if not existing:
                raise ValidationError(f"Transaction ID {tx_id} not found.")

            symbol = existing["symbol"]
            cursor.execute("DELETE FROM transactions WHERE id = ?;", (tx_id,))

            if not check_symbol_chronology_valid(symbol, conn):
                raise ValidationError(
                    f"Cannot delete transaction: deleting this transaction results in negative holdings for {symbol}."
                )
            return True
    finally:
        conn.close()


def get_all_transactions(
    symbol: Optional[str] = None,
    tx_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    order_by_desc: bool = True,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve transactions with optional filtering by symbol, transaction type, and date range.
    Uses parameterized queries for security.
    """
    conn = get_db_connection(db_path)
    try:
        query = "SELECT * FROM transactions WHERE 1=1"
        params: List[Any] = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol.strip().upper())

        if tx_type:
            query += " AND transaction_type = ?"
            params.append(tx_type.strip().upper())

        if start_date:
            query += " AND transaction_date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND transaction_date <= ?"
            params.append(end_date)

        order_dir = "DESC" if order_by_desc else "ASC"
        query += f" ORDER BY transaction_date {order_dir}, id {order_dir};"

        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_distinct_symbols(db_path: Optional[str] = None) -> List[str]:
    """Retrieve list of distinct stock symbols recorded in transactions."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT symbol FROM transactions ORDER BY symbol ASC;")
        return [row["symbol"] for row in cursor.fetchall()]
    finally:
        conn.close()


def backup_database(destination_path: str, db_path: Optional[str] = None) -> str:
    """
    Safely backup the active SQLite database to destination_path using SQLite backup API.
    """
    source_conn = get_db_connection(db_path)
    dest_path_obj = Path(destination_path)
    if dest_path_obj.parent:
        dest_path_obj.parent.mkdir(parents=True, exist_ok=True)

    dest_conn = sqlite3.connect(destination_path)
    try:
        with dest_conn:
            source_conn.backup(dest_conn)
        return str(dest_path_obj.resolve())
    finally:
        dest_conn.close()
        source_conn.close()
