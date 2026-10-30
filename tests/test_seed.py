"""Tests that the sample data meets the assignment's requirements."""

from contextlib import closing

import inventory_db
import seed_db


def test_seed_loads_the_expected_row_counts(seeded_db):
    assert inventory_db.table_row_counts(seeded_db) == {
        "suppliers": 4,
        "products": 12,
        "sales": 5,
        "sale_items": 12,
        "stock_movements": 0,
    }


def test_seed_products_cover_at_least_three_categories(seeded_db):
    query = "SELECT COUNT(DISTINCT category) FROM products"
    assert seeded_db.execute(query).fetchone()[0] >= 3


def test_seed_has_at_least_two_low_stock_products(seeded_db):
    query = "SELECT COUNT(*) FROM products WHERE quantity_in_stock <= reorder_level"
    assert seeded_db.execute(query).fetchone()[0] >= 2


def test_seed_has_at_least_two_products_that_were_never_sold(seeded_db):
    query = """
        SELECT COUNT(*) FROM products
        WHERE id NOT IN (SELECT product_id FROM sale_items)
    """
    assert seeded_db.execute(query).fetchone()[0] >= 2


def test_running_the_seed_script_twice_does_not_duplicate_data(
    tmp_path, monkeypatch, capsys
):
    db_file = tmp_path / "inventory.db"
    monkeypatch.setenv("INVENTORY_DB", str(db_file))

    seed_db.main()
    seed_db.main()

    assert "already has data" in capsys.readouterr().out
    with closing(inventory_db.connect(db_file)) as connection:
        assert inventory_db.table_row_counts(connection)["products"] == 12