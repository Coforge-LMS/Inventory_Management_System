"""Database access for the inventory system."""

import os
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DEFAULT_DB_PATH = Path(__file__).with_name("inventory.db")


def get_db_path():
    """Return INVENTORY_DB if it is set, otherwise a file next to the code."""
    # "or" also skips an empty value, which SQLite would treat as a temporary file.
    return os.environ.get("INVENTORY_DB") or str(DEFAULT_DB_PATH)


def connect(db_path):
    """Open the database with foreign keys on and rows readable by column name."""
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    # SQLite ignores foreign keys unless this is switched on for every connection.
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_schema(connection):
    """Create any missing tables and indexes. Running it again keeps the data."""
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def table_row_counts(connection):
    """Return how many rows each table holds, as {table name: count}."""
    rows = connection.execute(
        """
        SELECT 'suppliers' AS table_name, COUNT(*) AS row_count FROM suppliers
        UNION ALL SELECT 'products', COUNT(*) FROM products
        UNION ALL SELECT 'sales', COUNT(*) FROM sales
        UNION ALL SELECT 'sale_items', COUNT(*) FROM sale_items
        UNION ALL SELECT 'stock_movements', COUNT(*) FROM stock_movements
        """
    ).fetchall()
    return {row["table_name"]: row["row_count"] for row in rows}


def integrity_check(connection):
    """Return 'ok' if SQLite finds no damage, else the first problem it reports."""
    return connection.execute("PRAGMA integrity_check").fetchone()[0]