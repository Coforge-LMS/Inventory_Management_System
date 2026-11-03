"""Tests for restock, adjust_stock and record_sale."""

from datetime import datetime

import pytest

import inventory_db

HAMMER_ID = 1  # 24 in stock, price 1599
SCREWDRIVER_SET_ID = 2  # only 3 in stock
DRILL_ID = 4  # 6 in stock, price 8999
MISSING_ID = 999

# A fixed time, so the tests can check exactly what gets logged.
NOW = datetime(2026, 11, 3, 10, 30, 0)
NOW_TEXT = "2026-11-03T10:30:00"


def stock_of(connection, product_id):
    return inventory_db.get_product(connection, product_id)["quantity_in_stock"]


def movements(connection):
    """Return every logged movement as (product_id, change, reason, moved_at)."""
    rows = connection.execute(
        """
        SELECT product_id, quantity_change, reason, moved_at
        FROM stock_movements
        ORDER BY id
        """
    ).fetchall()
    return [tuple(row) for row in rows]


def database_state(connection):
    """Snapshot every table's row count and every product's stock level."""
    stock = connection.execute(
        "SELECT id, quantity_in_stock FROM products ORDER BY id"
    ).fetchall()
    return inventory_db.table_row_counts(connection), [tuple(row) for row in stock]


def make_sale(connection):
    """Sell 2 hammers and 1 drill, after raising the hammer's price to 1799."""
    inventory_db.change_price(connection, HAMMER_ID, 1799)
    items = [(HAMMER_ID, 2), (DRILL_ID, 1)]
    return inventory_db.record_sale(connection, items, now=NOW)


def test_restock_increases_stock_and_logs_one_movement(seeded_db):
    inventory_db.restock(seeded_db, HAMMER_ID, 10, now=NOW)

    assert stock_of(seeded_db, HAMMER_ID) == 34
    assert movements(seeded_db) == [(HAMMER_ID, 10, "restock", NOW_TEXT)]


@pytest.mark.parametrize("amount", [0, -5])
def test_restock_refuses_an_amount_of_zero_or_less(seeded_db, amount):
    before = database_state(seeded_db)

    with pytest.raises(inventory_db.InvalidValueError):
        inventory_db.restock(seeded_db, HAMMER_ID, amount, now=NOW)

    assert database_state(seeded_db) == before


def test_adjust_stock_changes_stock_by_a_signed_amount_and_logs_it(seeded_db):
    inventory_db.adjust_stock(seeded_db, HAMMER_ID, -3, now=NOW)

    assert stock_of(seeded_db, HAMMER_ID) == 21
    assert movements(seeded_db) == [(HAMMER_ID, -3, "adjustment", NOW_TEXT)]


def test_adjust_stock_cannot_make_stock_negative_and_changes_nothing(seeded_db):
    before = database_state(seeded_db)

    with pytest.raises(inventory_db.InsufficientStockError):
        inventory_db.adjust_stock(seeded_db, SCREWDRIVER_SET_ID, -4, now=NOW)

    assert database_state(seeded_db) == before


def test_a_sale_records_its_lines_at_the_current_prices(seeded_db):
    sale_id = make_sale(seeded_db)

    sale = seeded_db.execute(
        "SELECT sold_at FROM sales WHERE id = ?", (sale_id,)
    ).fetchone()
    lines = seeded_db.execute(
        """
        SELECT product_id, quantity, unit_price_cents
        FROM sale_items
        WHERE sale_id = ?
        ORDER BY id
        """,
        (sale_id,),
    ).fetchall()
    assert sale["sold_at"] == NOW_TEXT
    # The hammer line uses the new price (1799), not the original 1599.
    assert [tuple(line) for line in lines] == [(HAMMER_ID, 2, 1799), (DRILL_ID, 1, 8999)]


def test_a_sale_reduces_the_stock_of_each_product(seeded_db):
    make_sale(seeded_db)

    assert stock_of(seeded_db, HAMMER_ID) == 22
    assert stock_of(seeded_db, DRILL_ID) == 5


def test_a_sale_logs_one_movement_per_line(seeded_db):
    make_sale(seeded_db)

    assert movements(seeded_db) == [
        (HAMMER_ID, -2, "sale", NOW_TEXT),
        (DRILL_ID, -1, "sale", NOW_TEXT),
    ]


def test_a_sale_that_fails_halfway_changes_nothing(seeded_db):
    before = database_state(seeded_db)
    # The first line is fine and gets fully written. The second asks for more
    # screwdriver sets than exist, so the whole sale has to be undone.
    items = [(HAMMER_ID, 2), (SCREWDRIVER_SET_ID, 99)]

    with pytest.raises(inventory_db.InsufficientStockError):
        inventory_db.record_sale(seeded_db, items, now=NOW)

    assert database_state(seeded_db) == before


def test_a_sale_for_an_unknown_product_changes_nothing(seeded_db):
    before = database_state(seeded_db)
    items = [(HAMMER_ID, 1), (MISSING_ID, 1)]

    with pytest.raises(inventory_db.UnknownProductError):
        inventory_db.record_sale(seeded_db, items, now=NOW)

    assert database_state(seeded_db) == before


def test_a_sale_listing_the_same_product_twice_changes_nothing(seeded_db):
    before = database_state(seeded_db)
    items = [(HAMMER_ID, 1), (HAMMER_ID, 1)]

    with pytest.raises(inventory_db.DuplicateLineError):
        inventory_db.record_sale(seeded_db, items, now=NOW)

    assert database_state(seeded_db) == before