"""Tests for the rules the database enforces on its own (schema.sql)."""

import sqlite3

import pytest

import inventory_db

GOOD_PRODUCT = {
    "sku": "HAM-001",
    "name": "Claw Hammer",
    "category": "Hand Tools",
    "unit_price_cents": 1500,
    "quantity_in_stock": 10,
    "reorder_level": 5,
}


def insert_supplier(connection, name="Acme Tools"):
    """Insert a supplier and return its id."""
    cursor = connection.execute("INSERT INTO suppliers (name) VALUES (?)", (name,))
    return cursor.lastrowid


def insert_product(connection, supplier_id, **overrides):
    """Insert GOOD_PRODUCT with any overrides applied and return the new id."""
    values = {**GOOD_PRODUCT, "supplier_id": supplier_id, **overrides}
    cursor = connection.execute(
        """
        INSERT INTO products (sku, name, category, supplier_id,
                              unit_price_cents, quantity_in_stock, reorder_level)
        VALUES (:sku, :name, :category, :supplier_id,
                :unit_price_cents, :quantity_in_stock, :reorder_level)
        """,
        values,
    )
    return cursor.lastrowid


def insert_sale_line(connection, product_id, quantity=1):
    """Create a sale containing one line for the product."""
    sale_id = connection.execute(
        "INSERT INTO sales (sold_at) VALUES (?)", ("2026-10-29T10:00:00",)
    ).lastrowid
    connection.execute(
        """
        INSERT INTO sale_items (sale_id, product_id, quantity, unit_price_cents)
        VALUES (?, ?, ?, ?)
        """,
        (sale_id, product_id, quantity, 1500),
    )
    return sale_id


def insert_movement(connection, product_id, change=5, reason="restock"):
    """Log one stock movement for the product."""
    connection.execute(
        """
        INSERT INTO stock_movements (product_id, quantity_change, reason, moved_at)
        VALUES (?, ?, ?, ?)
        """,
        (product_id, change, reason, "2026-10-29T10:00:00"),
    )


def movement_count(connection):
    return connection.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0]


def test_foreign_keys_are_switched_on(db):
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_rows_can_be_read_by_column_name(db):
    insert_supplier(db, "Acme Tools")
    row = db.execute("SELECT name FROM suppliers").fetchone()
    assert row["name"] == "Acme Tools"


def test_running_the_schema_twice_keeps_existing_data(db):
    insert_supplier(db)
    inventory_db.init_schema(db)
    assert db.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0] == 1


@pytest.mark.parametrize(
    "bad_values",
    [
        pytest.param({"unit_price_cents": -1}, id="negative price"),
        pytest.param({"quantity_in_stock": -1}, id="negative stock"),
        pytest.param({"reorder_level": -1}, id="negative reorder level"),
        pytest.param({"sku": "   "}, id="blank sku"),
        pytest.param({"name": ""}, id="empty name"),
        pytest.param({"category": ""}, id="empty category"),
        pytest.param({"unit_price_cents": "cheap"}, id="text in a number column"),
    ],
)
def test_products_table_refuses_bad_values(db, bad_values):
    supplier_id = insert_supplier(db)
    with pytest.raises(sqlite3.IntegrityError):
        insert_product(db, supplier_id, **bad_values)


def test_products_table_refuses_a_duplicate_sku(db):
    supplier_id = insert_supplier(db)
    insert_product(db, supplier_id)
    with pytest.raises(sqlite3.IntegrityError):
        insert_product(db, supplier_id, name="Another Hammer")


def test_products_table_refuses_an_unknown_supplier(db):
    with pytest.raises(sqlite3.IntegrityError):
        insert_product(db, supplier_id=999)


@pytest.mark.parametrize(
    "reason, change",
    [
        pytest.param("theft", 5, id="invalid reason"),
        pytest.param("restock", 0, id="zero change"),
    ],
)
def test_stock_movements_refuse_bad_values(db, reason, change):
    product_id = insert_product(db, insert_supplier(db))
    with pytest.raises(sqlite3.IntegrityError):
        insert_movement(db, product_id, change=change, reason=reason)


@pytest.mark.parametrize("reason", ["restock", "adjustment", "sale"])
def test_stock_movements_accept_each_valid_reason(db, reason):
    product_id = insert_product(db, insert_supplier(db))
    insert_movement(db, product_id, reason=reason)
    assert movement_count(db) == 1


def test_sale_items_refuse_a_zero_quantity(db):
    product_id = insert_product(db, insert_supplier(db))
    with pytest.raises(sqlite3.IntegrityError):
        insert_sale_line(db, product_id, quantity=0)


def test_sale_items_refuse_the_same_product_twice_in_one_sale(db):
    product_id = insert_product(db, insert_supplier(db))
    sale_id = insert_sale_line(db, product_id)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO sale_items (sale_id, product_id, quantity, unit_price_cents)
            VALUES (?, ?, ?, ?)
            """,
            (sale_id, product_id, 1, 1500),
        )


def test_a_product_with_sale_lines_cannot_be_deleted(db):
    product_id = insert_product(db, insert_supplier(db))
    insert_sale_line(db, product_id)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM products WHERE id = ?", (product_id,))


def test_a_refused_delete_keeps_the_movements_of_a_sold_product(db):
    product_id = insert_product(db, insert_supplier(db))
    insert_sale_line(db, product_id)
    insert_movement(db, product_id)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    assert movement_count(db) == 1


def test_deleting_an_unsold_product_removes_its_movements(db):
    product_id = insert_product(db, insert_supplier(db))
    insert_movement(db, product_id)
    db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    assert movement_count(db) == 0