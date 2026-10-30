"""Create the database and load the sample data.

Run it with:  python seed_db.py
The database file comes from the INVENTORY_DB environment variable, or is created
next to the code when the variable is not set.
"""

from contextlib import closing

import inventory_db

SUPPLIERS = [
    (1, "Northline Hardware Supply"),
    (2, "Pioneer Tool Co."),
    (3, "BrightWire Electrical"),
    (4, "Summit Building Supply"),
]

# id, sku, name, category, supplier_id, unit_price_cents, quantity_in_stock,
# reorder_level
PRODUCTS = [
    (1, "HT-HAM-16", "16oz Claw Hammer", "Hand Tools", 1, 1599, 24, 10),
    (2, "HT-SCR-SET", "Screwdriver Set (6 piece)", "Hand Tools", 1, 1299, 3, 8),
    (3, "FA-NAIL-1LB", "Common Nails 1 lb", "Fasteners", 1, 499, 60, 20),
    (4, "PT-DRL-18V", "18V Cordless Drill", "Power Tools", 2, 8999, 6, 4),
    (5, "PT-SAW-7Q", "7-1/4 in Circular Saw", "Power Tools", 2, 7499, 4, 4),
    (6, "HT-WRN-ADJ", "Adjustable Wrench 10 in", "Hand Tools", 2, 1899, 15, 6),
    (7, "EL-EXT-25", "Extension Cord 25 ft", "Electrical", 3, 1999, 12, 5),
    (8, "EL-BULB-4", "LED Bulbs 4-pack", "Electrical", 3, 899, 40, 15),
    (9, "EL-OUT-GFCI", "GFCI Outlet", "Electrical", 3, 1699, 0, 3),
    (10, "FA-SCR-100", "Wood Screws Box of 100", "Fasteners", 4, 799, 80, 25),
    (11, "FA-ANC-50", "Drywall Anchors 50 ct", "Fasteners", 4, 649, 30, 10),
    (12, "HT-TAPE-25", "Tape Measure 25 ft", "Hand Tools", 4, 1249, 18, 8),
]

SALES = [
    (1, "2026-10-20T09:15:00"),
    (2, "2026-10-21T14:40:00"),
    (3, "2026-10-23T11:05:00"),
    (4, "2026-10-25T16:30:00"),
    (5, "2026-10-27T10:20:00"),
]

# sale_id, product_id, quantity, unit_price_cents (the price charged at the time).
SALE_ITEMS = [
    (1, 1, 2, 1499),  # the hammer cost less before its price went up
    (1, 3, 5, 499),
    (1, 10, 2, 799),
    (2, 4, 1, 8999),
    (2, 8, 4, 899),
    (3, 2, 1, 1299),
    (3, 6, 1, 1899),
    (3, 7, 2, 1999),
    (4, 5, 1, 7499),
    (4, 10, 3, 799),
    (5, 1, 1, 1599),
    (5, 9, 2, 1699),
]


def load_sample_data(connection):
    """Insert every sample row in one transaction: all of it loads, or none."""
    with connection:
        connection.executemany(
            "INSERT INTO suppliers (id, name) VALUES (?, ?)", SUPPLIERS
        )
        connection.executemany(
            """
            INSERT INTO products (id, sku, name, category, supplier_id,
                                  unit_price_cents, quantity_in_stock, reorder_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            PRODUCTS,
        )
        connection.executemany("INSERT INTO sales (id, sold_at) VALUES (?, ?)", SALES)
        connection.executemany(
            """
            INSERT INTO sale_items (sale_id, product_id, quantity, unit_price_cents)
            VALUES (?, ?, ?, ?)
            """,
            SALE_ITEMS,
        )


def print_row_counts(connection):
    for table_name, row_count in inventory_db.table_row_counts(connection).items():
        print(f"{table_name}: {row_count}")


def main():
    with closing(inventory_db.connect(inventory_db.get_db_path())) as connection:
        inventory_db.init_schema(connection)
        if any(inventory_db.table_row_counts(connection).values()):
            print("The database already has data, so nothing was loaded.")
        else:
            load_sample_data(connection)
            print("Sample data loaded.")
        print_row_counts(connection)


if __name__ == "__main__":
    main()