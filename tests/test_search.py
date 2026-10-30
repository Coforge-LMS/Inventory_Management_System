"""Tests for search_products."""

import pytest

import inventory_db


def search_skus(connection, text="", **filters):
    """Search and return just the SKUs, sorted, so tests can compare them easily."""
    results = inventory_db.search_products(connection, text, **filters)
    return sorted(row["sku"] for row in results)


@pytest.mark.parametrize(
    "text, expected_skus",
    [
        pytest.param("hammer", ["HT-HAM-16"], id="name"),
        pytest.param("ht-ham", ["HT-HAM-16"], id="sku"),
        pytest.param(
            "PIONEER",
            ["HT-WRN-ADJ", "PT-DRL-18V", "PT-SAW-7Q"],
            id="supplier name",
        ),
    ],
)
def test_search_matches_name_sku_and_supplier_ignoring_case(
    seeded_db, text, expected_skus
):
    assert search_skus(seeded_db, text) == expected_skus


def test_search_filters_by_category(seeded_db):
    assert search_skus(seeded_db, category="Electrical") == [
        "EL-BULB-4",
        "EL-EXT-25",
        "EL-OUT-GFCI",
    ]


def test_search_filters_by_maximum_price_including_the_limit(seeded_db):
    # The LED bulbs cost exactly 899, so they must be included.
    assert search_skus(seeded_db, max_price_cents=899) == [
        "EL-BULB-4",
        "FA-ANC-50",
        "FA-NAIL-1LB",
        "FA-SCR-100",
    ]


def test_search_in_stock_only_leaves_out_products_with_no_stock(seeded_db):
    skus = search_skus(seeded_db, in_stock_only=True)
    assert len(skus) == 11
    assert "EL-OUT-GFCI" not in skus


def test_search_low_stock_only_includes_products_exactly_at_their_level(seeded_db):
    # The circular saw has 4 in stock and a reorder level of 4.
    assert search_skus(seeded_db, low_stock_only=True) == [
        "EL-OUT-GFCI",
        "HT-SCR-SET",
        "PT-SAW-7Q",
    ]


@pytest.mark.parametrize(
    "text, filters, expected_skus",
    [
        pytest.param(
            "pioneer",
            {"max_price_cents": 8000},
            ["HT-WRN-ADJ", "PT-SAW-7Q"],
            id="supplier and price",
        ),
        pytest.param(
            "",
            {"category": "Hand Tools", "low_stock_only": True},
            ["HT-SCR-SET"],
            id="category and low stock",
        ),
    ],
)
def test_search_filters_can_be_combined(seeded_db, text, filters, expected_skus):
    assert search_skus(seeded_db, text, **filters) == expected_skus


def test_results_are_sorted_by_name(seeded_db):
    results = inventory_db.search_products(seeded_db, "")
    names = [row["name"] for row in results]
    assert names == sorted(names)


def test_dangerous_looking_text_is_searched_as_plain_text(seeded_db):
    results = inventory_db.search_products(seeded_db, "'; DROP TABLE products; --")
    assert results == []
    # The products table still exists and still holds every row.
    assert inventory_db.table_row_counts(seeded_db)["products"] == 12