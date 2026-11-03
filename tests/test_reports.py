""" Tests for the four reports and for money formatting, using the sample data. """

import pytest

import inventory_db

def as_tuples(rows):
    """Turn Row objects into plain tuples, so they can be compared with ==."""
    return [tuple(row) for row in rows]

def test_stock_value_by_supplier_lists_the_highest_value_first(seeded_db):
    rows = inventory_db.stock_value_by_supplier(seeded_db)
    assert as_tuples(rows) == [
        ("Pioneer Tool Co.", 112475),
        ("Summit Building Supply", 105872),
        ("Northline Hardware Supply", 72213),
        ("BrightWire Electrical", 59948),
    ]

def test_low_stock_report_shows_how_many_units_short(seeded_db):
    rows = inventory_db.low_stock_report(seeded_db)
    # Columns: sku, name, quantity_in_stock, reorder_level, units_short.
    assert as_tuples(rows) == [
        ("HT-SCR-SET", "Screwdriver Set (6 piece)", 3, 8, 5),
        ("EL-OUT-GFCI", "GFCI Outlet", 0, 3, 3),
        ("PT-SAW-7Q", "7-1/4 in Circular Saw", 4, 4, 0),
    ]

def test_sales_by_product_uses_the_price_charged_at_the_time(seeded_db):
    rows = inventory_db.sales_by_product(seeded_db)
    # Columns: sku, name, units_sold, revenue_cents. The hammer sold twice at 1499
    # and once at 1599, so its revenue is 4597. Using today's price would give 4797.
    assert as_tuples(rows) == [
        ("PT-DRL-18V", "18V Cordless Drill", 1, 8999),
        ("PT-SAW-7Q", "7-1/4 in Circular Saw", 1, 7499),
        ("HT-HAM-16", "16oz Claw Hammer", 3, 4597),
        ("EL-EXT-25", "Extension Cord 25 ft", 2, 3998),
        ("FA-SCR-100", "Wood Screws Box of 100", 5, 3995),
        ("EL-BULB-4", "LED Bulbs 4-pack", 4, 3596),
        ("EL-OUT-GFCI", "GFCI Outlet", 2, 3398),
        ("FA-NAIL-1LB", "Common Nails 1 lb", 5, 2495),
        ("HT-WRN-ADJ", "Adjustable Wrench 10 in", 1, 1899),
        ("HT-SCR-SET", "Screwdriver Set (6 piece)", 1, 1299),
    ]

def test_never_sold_lists_products_in_no_sale(seeded_db):
    rows = inventory_db.never_sold_products(seeded_db)
    assert as_tuples(rows) == [
        ("FA-ANC-50", "Drywall Anchors 50 ct"),
        ("HT-TAPE-25", "Tape Measure 25 ft"),
    ]

@pytest.mark.parametrize(
    "cents,expected",
    [(1250, "12.50"), (5, "0.05"), (0, "0.00")],
)
def test_format_cents_shows_dollars_and_cents(cents, expected):
    assert inventory_db.format_cents(cents) == expected