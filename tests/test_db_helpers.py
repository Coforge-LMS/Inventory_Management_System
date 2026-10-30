"""Tests for the small helper functions in inventory_db."""

from pathlib import Path

import inventory_db


def test_get_db_path_uses_the_environment_variable(monkeypatch):
    monkeypatch.setenv("INVENTORY_DB", "/data/custom.db")
    assert inventory_db.get_db_path() == "/data/custom.db"


def test_get_db_path_falls_back_to_a_file_next_to_the_code(monkeypatch):
    monkeypatch.delenv("INVENTORY_DB", raising=False)
    expected = Path(inventory_db.__file__).with_name("inventory.db")
    assert Path(inventory_db.get_db_path()) == expected


def test_get_db_path_ignores_an_empty_environment_variable(monkeypatch):
    monkeypatch.setenv("INVENTORY_DB", "")
    assert Path(inventory_db.get_db_path()).name == "inventory.db"


def test_table_row_counts_are_zero_for_an_empty_database(db):
    assert inventory_db.table_row_counts(db) == {
        "suppliers": 0,
        "products": 0,
        "sales": 0,
        "sale_items": 0,
        "stock_movements": 0,
    }


def test_integrity_check_says_ok_for_a_healthy_database(db):
    assert inventory_db.integrity_check(db) == "ok"