"""Terminal menu for the inventory system. Run it with:  python main.py"""

import sqlite3
from contextlib import closing
from datetime import datetime
from decimal import Decimal, DecimalException
from pathlib import Path

import inventory_db
from inventory_db import format_cents

PRODUCT_HEADERS = [
    "ID", "SKU", "Name", "Category", "Supplier", "Price", "In stock", "Reorder at",
]  # fmt: skip


# ----------------------------------------------------------- reading input


def ask_whole_number(prompt, optional=False):
    """Keep asking until the user types a whole number.

    With optional=True, a blank answer returns None instead.
    """
    while True:
        answer = input(prompt).strip()
        if optional and not answer:
            return None
        try:
            return int(answer)
        except ValueError:
            print("Please type a whole number, for example 5.")


def ask_dollars_as_cents(prompt, optional=False):
    """Keep asking until the user types a dollar amount, and return it in cents."""
    while True:
        answer = input(prompt).strip()
        if optional and not answer:
            return None
        try:
            cents = Decimal(answer) * 100
            if cents.is_finite() and cents == cents.to_integral_value():
                return int(cents)
        except DecimalException:
            pass
        print("Please type an amount in dollars with at most two decimals, e.g. 12.50.")


def ask_yes_no(prompt):
    """Return True only if the user answers y or yes."""
    return input(prompt).strip().lower() in ("y", "yes")


# ---------------------------------------------------------------- printing


def print_table(headers, rows):
    """Print rows as aligned columns under the headers."""
    if not rows:
        print("No results.")
        return
    widths = [max(len(str(cell)) for cell in column) for column in zip(headers, *rows)]
    print("  ".join(header.ljust(width) for header, width in zip(headers, widths)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(str(cell).ljust(width) for cell, width in zip(row, widths)))


def product_row(product):
    """Turn a product row from a search into a list of display values."""
    return [
        product["id"],
        product["sku"],
        product["name"],
        product["category"],
        product["supplier_name"],
        format_cents(product["unit_price_cents"]),
        product["quantity_in_stock"],
        product["reorder_level"],
    ]


# ------------------------------------------------------------ menu actions


def search_menu(connection):
    text = input("Search text (name, SKU or supplier; Enter for everything): ").strip()
    category = input("Category (Enter for any): ").strip() or None
    max_price = ask_dollars_as_cents(
        "Maximum price in dollars (Enter for no limit): ", optional=True
    )
    in_stock_only = ask_yes_no("Only products in stock? (y/n): ")
    low_stock_only = ask_yes_no("Only low stock products? (y/n): ")
    products = inventory_db.search_products(
        connection, text, category, max_price, in_stock_only, low_stock_only
    )
    print_table(PRODUCT_HEADERS, [product_row(product) for product in products])


def lookup_menu(connection):
    product_id = ask_whole_number("Product id: ")
    product = inventory_db.get_product(connection, product_id)
    if product is None:
        print(f"There is no product with id {product_id}.")
        return
    details = [
        ("ID", product["id"]),
        ("SKU", product["sku"]),
        ("Name", product["name"]),
        ("Category", product["category"]),
        ("Supplier", f"{product['supplier_name']} (id {product['supplier_id']})"),
        ("Price", format_cents(product["unit_price_cents"])),
        ("In stock", product["quantity_in_stock"]),
        ("Reorder level", product["reorder_level"]),
    ]
    for label, value in details:
        print(f"{label + ':':<15}{value}")


def add_menu(connection):
    sku = input("SKU: ").strip()
    name = input("Name: ").strip()
    category = input("Category: ").strip()
    supplier_id = ask_whole_number("Supplier id (shown when you look up a product): ")
    price = ask_dollars_as_cents("Price in dollars: ")
    quantity = ask_whole_number("Quantity in stock: ")
    reorder_level = ask_whole_number("Reorder level: ")
    product_id = inventory_db.add_product(
        connection, sku, name, category, supplier_id, price, quantity, reorder_level
    )
    print(f"Added product {product_id}.")


def restock_menu(connection):
    product_id = ask_whole_number("Product id: ")
    amount = ask_whole_number("Amount to add: ")
    inventory_db.restock(connection, product_id, amount)
    product = inventory_db.get_product(connection, product_id)
    print(f"Restocked. {product['name']} now has {product['quantity_in_stock']}.")


def sale_menu(connection):
    items = []
    while True:
        product_id = ask_whole_number("Product id (Enter when finished): ", optional=True)
        if product_id is None:
            break
        quantity = ask_whole_number("Quantity: ")
        items.append((product_id, quantity))
    if not items:
        print("Nothing to sell.")
        return
    sale_id = inventory_db.record_sale(connection, items)
    print(f"Sale {sale_id} recorded with {len(items)} line(s).")


def stock_value_menu(connection):
    rows = inventory_db.stock_value_by_supplier(connection)
    print_table(
        ["Supplier", "Stock value"],
        [[row["supplier_name"], format_cents(row["stock_value_cents"])] for row in rows],
    )


def low_stock_menu(connection):
    rows = inventory_db.low_stock_report(connection)
    print_table(
        ["SKU", "Name", "In stock", "Reorder level", "Short by"],
        [
            [
                row["sku"],
                row["name"],
                row["quantity_in_stock"],
                row["reorder_level"],
                row["units_short"],
            ]
            for row in rows
        ],
    )


def sales_by_product_menu(connection):
    rows = inventory_db.sales_by_product(connection)
    print_table(
        ["SKU", "Name", "Units sold", "Revenue"],
        [
            [row["sku"], row["name"], row["units_sold"], format_cents(row["revenue_cents"])]
            for row in rows
        ],
    )


def never_sold_menu(connection):
    rows = inventory_db.never_sold_products(connection)
    print_table(["SKU", "Name"], [[row["sku"], row["name"]] for row in rows])


def default_backup_path():
    """Return a timestamped backup file path next to the database file."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(inventory_db.get_db_path()).with_name(f"inventory_backup_{stamp}.db")


def backup_menu(connection):
    default_path = default_backup_path()
    answer = input(f"Backup file (Enter for {default_path}): ").strip()
    destination = Path(answer) if answer else default_path
    inventory_db.backup_database(connection, destination)
    with closing(inventory_db.connect(destination)) as copy:
        print(f"Backup saved to {destination}")
        print(f"Integrity check: {inventory_db.integrity_check(copy)}")
        print(f"Row counts: {inventory_db.table_row_counts(copy)}")


# --------------------------------------------------------------- main loop

MENU = [
    ("Search products", search_menu),
    ("Look up a product", lookup_menu),
    ("Add a product", add_menu),
    ("Restock a product", restock_menu),
    ("Record a sale", sale_menu),
    ("Report: stock value by supplier", stock_value_menu),
    ("Report: low stock", low_stock_menu),
    ("Report: sales by product", sales_by_product_menu),
    ("Report: never sold", never_sold_menu),
    ("Back up the database", backup_menu),
]
ACTIONS = {str(number): action for number, (_, action) in enumerate(MENU, start=1)}

def print_banner(connection):
    """Show how many products are at or below their reorder level."""
    low_stock_count = len(inventory_db.low_stock_report(connection))
    print(f"Low stock products: {low_stock_count}")

def print_menu():
    print("\nInventory menu")
    for number, (label, _) in enumerate(MENU, start=1):
        print(f"  {number}. {label}")
    print("  0. Quit")


def run_menu(connection):
    """Show the menu until the user quits. Every error is reported, never raised."""
    while True:
        print_menu()
        choice = input("Choose an option: ").strip()
        if choice == "0":
            return
        action = ACTIONS.get(choice)
        if action is None:
            print(f"Please type a number from 0 to {len(MENU)}.")
            continue
        try:
            action(connection)
        except inventory_db.InventoryError as error:
            print(error)
        except sqlite3.Error as error:
            print(f"Database problem: {error}")
        except OverflowError:
            print("That number is too large.")


def main():
    with closing(inventory_db.connect(inventory_db.get_db_path())) as connection:
        inventory_db.init_schema(connection)
        print_banner(connection)
        try:
            run_menu(connection)
        except (EOFError, KeyboardInterrupt):
            print()  # finish the line the user was typing on
        print("Goodbye.")


if __name__ == "__main__":
    main()