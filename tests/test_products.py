"""Tests for adding, reading, repricing and deleting products."""

import pytest

import inventory_db

GOOD_PRODUCT = {
    "sku": "NEW-001",
    "name": "Pipe Wrench",
    "category": "Hand Tools",
    "supplier_id": 1,
    "unit_price_cents": 2499,
    "quantity_in_stock": 7,
    "reorder_level": 3,
}

# In the sample data the hammer has sales and the drywall anchors have none.
SOLD_PRODUCT_ID = 1
NEVER_SOLD_PRODUCT_ID = 11
MISSING_PRODUCT_ID = 999


def add_good_product(connection, **overrides):
    """Add GOOD_PRODUCT with any fields overridden and return the new id."""
    return inventory_db.add_product(connection, **{**GOOD_PRODUCT, **overrides})


def test_add_product_returns_the_new_id(seeded_db):
    new_id = add_good_product(seeded_db)
    query = "SELECT sku FROM products WHERE id = ?"
    assert seeded_db.execute(query, (new_id,)).fetchone()["sku"] == "NEW-001"


def test_add_product_refuses_a_duplicate_sku(seeded_db):
    with pytest.raises(inventory_db.DuplicateSkuError, match="HT-HAM-16"):
        add_good_product(seeded_db, sku="HT-HAM-16")


def test_add_product_refuses_an_unknown_supplier(seeded_db):
    with pytest.raises(inventory_db.UnknownSupplierError, match="999"):
        add_good_product(seeded_db, supplier_id=999)


@pytest.mark.parametrize(
    "bad_values",
    [
        pytest.param({"unit_price_cents": -1}, id="negative price"),
        pytest.param({"quantity_in_stock": -1}, id="negative quantity"),
        pytest.param({"reorder_level": -1}, id="negative reorder level"),
    ],
)
def test_add_product_refuses_negative_numbers(seeded_db, bad_values):
    with pytest.raises(inventory_db.InvalidValueError):
        add_good_product(seeded_db, **bad_values)


def test_get_product_includes_the_supplier_name(seeded_db):
    product = inventory_db.get_product(seeded_db, SOLD_PRODUCT_ID)
    assert product["sku"] == "HT-HAM-16"
    assert product["supplier_name"] == "Northline Hardware Supply"


def test_get_product_returns_none_for_a_missing_product(seeded_db):
    assert inventory_db.get_product(seeded_db, MISSING_PRODUCT_ID) is None


def test_change_price_updates_the_price(seeded_db):
    assert inventory_db.change_price(seeded_db, SOLD_PRODUCT_ID, 1799) is True
    product = inventory_db.get_product(seeded_db, SOLD_PRODUCT_ID)
    assert product["unit_price_cents"] == 1799


def test_change_price_returns_false_for_a_missing_product(seeded_db):
    assert inventory_db.change_price(seeded_db, MISSING_PRODUCT_ID, 1799) is False


def test_change_price_refuses_a_negative_price(seeded_db):
    with pytest.raises(inventory_db.InvalidValueError):
        inventory_db.change_price(seeded_db, SOLD_PRODUCT_ID, -1)
    product = inventory_db.get_product(seeded_db, SOLD_PRODUCT_ID)
    assert product["unit_price_cents"] == 1599


def test_delete_product_refuses_a_product_with_sales(seeded_db):
    with pytest.raises(inventory_db.ProductHasSalesError):
        inventory_db.delete_product(seeded_db, SOLD_PRODUCT_ID)
    assert inventory_db.get_product(seeded_db, SOLD_PRODUCT_ID) is not None


def test_delete_product_removes_a_product_that_was_never_sold(seeded_db):
    assert inventory_db.delete_product(seeded_db, NEVER_SOLD_PRODUCT_ID) is True
    assert inventory_db.get_product(seeded_db, NEVER_SOLD_PRODUCT_ID) is None


def test_delete_product_returns_false_for_a_missing_product(seeded_db):
    assert inventory_db.delete_product(seeded_db, MISSING_PRODUCT_ID) is False


@pytest.mark.parametrize(
    "error_name",
    [
        "DuplicateSkuError",
        "UnknownSupplierError",
        "InvalidValueError",
        "ProductHasSalesError",
        "UnknownProductError",
        "InsufficientStockError",
        "DuplicateLineError",
    ],
)
def test_every_error_can_be_caught_as_an_inventory_error(error_name):
    error_class = getattr(inventory_db, error_name)
    assert issubclass(error_class, inventory_db.InventoryError)