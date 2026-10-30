"""Database access for the inventory system."""

import os
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DEFAULT_DB_PATH = Path(__file__).with_name("inventory.db")

# How SQLite names the rule behind an IntegrityError, so we can tell them apart.
UNIQUE_FAILED = "SQLITE_CONSTRAINT_UNIQUE"
FOREIGN_KEY_FAILED = "SQLITE_CONSTRAINT_FOREIGNKEY"


class InventoryError(Exception):
    """Base class for broken business rules. The message is written for the user."""


class DuplicateSkuError(InventoryError):
    """A product with that SKU already exists."""


class UnknownSupplierError(InventoryError):
    """The supplier does not exist."""


class InvalidValueError(InventoryError):
    """A value is missing, blank, negative or not a whole number."""


class ProductHasSalesError(InventoryError):
    """The product has sales history, so it cannot be deleted."""


class UnknownProductError(InventoryError):
    """The product does not exist."""


class InsufficientStockError(InventoryError):
    """There is not enough stock for the change."""


class DuplicateLineError(InventoryError):
    """The same product appears twice in one sale."""


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


# ---------------------------------------------------------------- products


def add_product(
    connection,
    sku,
    name,
    category,
    supplier_id,
    unit_price_cents,
    quantity_in_stock,
    reorder_level,
):
    """Add a product and return its new id. Raises an InventoryError if a rule fails."""
    try:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO products (sku, name, category, supplier_id,
                                      unit_price_cents, quantity_in_stock,
                                      reorder_level)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sku,
                    name,
                    category,
                    supplier_id,
                    unit_price_cents,
                    quantity_in_stock,
                    reorder_level,
                ),
            )
    except sqlite3.IntegrityError as exc:
        if exc.sqlite_errorname == UNIQUE_FAILED:
            raise DuplicateSkuError(f"A product with SKU '{sku}' already exists.") from exc
        if exc.sqlite_errorname == FOREIGN_KEY_FAILED:
            raise UnknownSupplierError(
                f"There is no supplier with id {supplier_id}."
            ) from exc
        raise InvalidValueError(
            "SKU, name and category must be filled in, and price, quantity and "
            "reorder level must be whole numbers of 0 or more."
        ) from exc
    return cursor.lastrowid


def get_product(connection, product_id):
    """Return the product with its supplier's name, or None if it does not exist."""
    return connection.execute(
        """
        SELECT p.id, p.sku, p.name, p.category, p.supplier_id,
               s.name AS supplier_name, p.unit_price_cents,
               p.quantity_in_stock, p.reorder_level
        FROM products AS p
        JOIN suppliers AS s ON s.id = p.supplier_id
        WHERE p.id = ?
        """,
        (product_id,),
    ).fetchone()


def change_price(connection, product_id, new_price_cents):
    """Set a product's price. Return True if it changed, False if no such product."""
    try:
        with connection:
            cursor = connection.execute(
                "UPDATE products SET unit_price_cents = ? WHERE id = ?",
                (new_price_cents, product_id),
            )
    except sqlite3.IntegrityError as exc:
        raise InvalidValueError(
            "The price must be a whole number of cents, 0 or more."
        ) from exc
    return cursor.rowcount > 0


def delete_product(connection, product_id):
    """Delete a product. Return True if deleted, False if no such product."""
    try:
        with connection:
            cursor = connection.execute(
                "DELETE FROM products WHERE id = ?", (product_id,)
            )
    except sqlite3.IntegrityError as exc:
        # sale_items is the only table that can block this delete: the movements
        # log cascades, so a refusal always means the product has been sold.
        raise ProductHasSalesError(
            f"Product {product_id} has sales history, so it cannot be deleted."
        ) from exc
    return cursor.rowcount > 0

    # ------------------------------------------------------------------ search


def search_products(
    connection,
    text,
    category=None,
    max_price_cents=None,
    in_stock_only=False,
    low_stock_only=False,
):
    """Find products whose name, SKU or supplier name contains the text.

    The optional filters can be combined. Results are sorted by name.
    """
    # One fixed query. A filter is switched off by passing None or False, so no SQL
    # text is ever built from the values: they all travel as named placeholders.
    return connection.execute(
        """
        SELECT p.id, p.sku, p.name, p.category, s.name AS supplier_name,
               p.unit_price_cents, p.quantity_in_stock, p.reorder_level
        FROM products AS p
        JOIN suppliers AS s ON s.id = p.supplier_id
        WHERE (p.name LIKE '%' || :text || '%'
               OR p.sku LIKE '%' || :text || '%'
               OR s.name LIKE '%' || :text || '%')
          AND (:category IS NULL OR p.category = :category)
          AND (:max_price_cents IS NULL OR p.unit_price_cents <= :max_price_cents)
          AND (:in_stock_only = 0 OR p.quantity_in_stock > 0)
          AND (:low_stock_only = 0 OR p.quantity_in_stock <= p.reorder_level)
        ORDER BY p.name
        """,
        {
            "text": text,
            "category": category,
            "max_price_cents": max_price_cents,
            "in_stock_only": in_stock_only,
            "low_stock_only": low_stock_only,
        },
    ).fetchall()