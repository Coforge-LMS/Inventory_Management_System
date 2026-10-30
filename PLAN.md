# Inventory Management System: Plan

This is the plan for the Week 3 inventory project. The program is a terminal app for a small hardware store, and everything is stored in one SQLite file. I'm writing this before any code so the tables and the rules for changing stock are settled first. If I find something wrong while building, I'll fix this file and say so in the commit message.

A few choices apply everywhere. Money is stored as whole cents in INTEGER columns and only turned into dollars when it's displayed. Dates and times are stored as ISO 8601 text like `2026-10-29T21:16:00`, because STRICT tables don't have a date type and that format sorts correctly as plain text. I'm using Python 3.14 and SQLite 3.50, so every table can be STRICT.

## 1. Tables

`schema.sql` uses `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS`, so running it again does nothing and keeps the data. SQLite doesn't enforce foreign keys unless asked, so `connect()` turns them on for every connection.

**suppliers** (id, name)
- name is required, unique and can't be blank.
- It exists so each supplier's name is stored once. Products point at it, and the search and the stock value report both use the name.

**products** (id, sku, name, category, supplier_id, unit_price_cents, quantity_in_stock, reorder_level)
- sku is required, unique and can't be blank. name and category are required and can't be blank.
- supplier_id is required and references suppliers.
- unit_price_cents, quantity_in_stock and reorder_level must be 0 or more.
- This is the catalogue plus the current stock level. The reorder level lives here so "low stock" is just a comparison between two columns.

**sales** (id, sold_at)
- sold_at is required.
- One row per checkout. There is no total column because the total can be worked out from the lines, and a stored total could drift out of sync.

**sale_items** (id, sale_id, product_id, quantity, unit_price_cents)
- sale_id references sales and product_id references products. Both are required.
- quantity must be more than 0. unit_price_cents must be 0 or more.
- (sale_id, product_id) is unique, so one product can't appear twice in the same sale.
- unit_price_cents is a copy of the product's price at the moment of the sale. If the price changes next week, old sales and the revenue report still show what was really charged.
- product_id uses ON DELETE RESTRICT, which is what stops a sold product from being deleted.

**stock_movements** (id, product_id, quantity_change, reason, moved_at)
- product_id references products and is required.
- quantity_change is signed and can't be 0. Restocks are positive, sales are negative, and adjustments can be either.
- reason must be 'restock', 'adjustment' or 'sale'.
- moved_at is required.
- This is the log that answers "what changed and when". It starts empty and fills up as the program is used.
- product_id uses ON DELETE CASCADE. I thought about refusing to delete any product that has movements, but the assignment only protects products that have been sold, and a product that was restocked and never sold should still be deletable. The cost is that its log rows go with it. I'll say so in the README.

**Index.** `idx_sale_items_product_id` on sale_items(product_id). SQLite doesn't index the child side of a foreign key on its own, and the unique index on (sale_id, product_id) starts with sale_id, so it can't help with product lookups. This index is used by the sales-by-product report, the never-sold report, and the check SQLite runs when a product is deleted.

## 2. How the tables connect

- One supplier has many products (products.supplier_id).
- One sale has many sale_items (sale_items.sale_id).
- One product can appear in many sale_items (sale_items.product_id). Sales and products are many-to-many, and sale_items is the table in the middle.
- One product has many stock_movements (stock_movements.product_id).

A product's sale_items block it from being deleted. Its stock_movements are deleted along with it. Nothing in the program deletes sales or suppliers.

## 3. Public functions

All of these live in `inventory_db.py`. Every function except `get_db_path` and `format_cents` takes the connection as its first argument, so tests can pass in an in-memory database. "Row" means a `sqlite3.Row`, which can be read by column name.

| Function | Inputs | Returns | Raises |
|---|---|---|---|
| `get_db_path()` | none | database path from INVENTORY_DB, or a file next to the code | |
| `connect(db_path)` | path or `":memory:"` | connection with foreign keys on and Row results | |
| `init_schema(connection)` | none | None | |
| `table_row_counts(connection)` | none | dict of table name to row count | |
| `integrity_check(connection)` | none | `"ok"` or the first problem found | |
| `add_product(connection, sku, name, category, supplier_id, unit_price_cents, quantity_in_stock, reorder_level)` | the product's fields | the new product id | DuplicateSkuError, UnknownSupplierError, InvalidValueError |
| `get_product(connection, product_id)` | id | Row including supplier_name, or None | |
| `change_price(connection, product_id, new_price_cents)` | id, cents | True, or False if no such product | InvalidValueError |
| `delete_product(connection, product_id)` | id | True, or False if no such product | ProductHasSalesError |
| `search_products(connection, text, category=None, max_price_cents=None, in_stock_only=False, low_stock_only=False)` | text and optional filters | list of Rows sorted by name | |
| `stock_value_by_supplier(connection)` | none | Rows: supplier_name, stock_value_cents, highest first | |
| `low_stock_report(connection)` | none | Rows: sku, name, quantity_in_stock, reorder_level, units_short | |
| `sales_by_product(connection)` | none | Rows: sku, name, units_sold, revenue_cents, highest revenue first | |
| `never_sold_products(connection)` | none | Rows: sku, name | |
| `restock(connection, product_id, amount, now=None)` | id, amount above 0 | None | InvalidValueError, UnknownProductError |
| `adjust_stock(connection, product_id, change, now=None)` | id, signed amount | None | InvalidValueError, UnknownProductError, InsufficientStockError |
| `record_sale(connection, items, now=None)` | list of (product_id, quantity) pairs | the new sale id | InvalidValueError, UnknownProductError, InsufficientStockError, DuplicateLineError |
| `backup_database(connection, destination_path)` | path for the copy | None | |
| `format_cents(cents)` | whole cents | text like `"12.50"` | |

**Errors.** Each rule that can be broken has its own exception, and they all inherit from InventoryError so the menu can catch one type and print the message. The seven are DuplicateSkuError, UnknownSupplierError, InvalidValueError, ProductHasSalesError, UnknownProductError, InsufficientStockError and DuplicateLineError. When the database refuses something, the function catches sqlite3.IntegrityError and checks `exc.sqlite_errorname`. In add_product, a UNIQUE failure is a duplicate SKU, a FOREIGNKEY failure is an unknown supplier, and anything else (CHECK, NOT NULL, wrong data type) is an InvalidValueError. In delete_product, a FOREIGNKEY failure means the product has sales, because that is the only foreign key that can block a delete (movements cascade). `sqlite_errorname` needs Python 3.11 or newer, so CI and Docker use 3.14 as well.

**SQL rule.** No value ever goes into SQL text. search_products is one fixed query with named placeholders, and the optional filters are written like `(:category IS NULL OR p.category = :category)`, so there is nothing to put together. table_row_counts is also one fixed query instead of a loop that builds SQL from table names.

**Reports.** Ties are broken by name so the results are the same on every run. Revenue uses sale_items.unit_price_cents, not the product's current price.

## 4. Restock, adjust and record a sale

Each of these runs inside one `with connection:` block. The block commits when it ends normally and rolls back if an exception leaves it. The helpers, `_change_stock` and `_log_movement`, only run SQL and never commit, so they can't save half a change. `now` is a datetime that defaults to None, and a small helper fills in the current time inside the function. A default of `datetime.now()` would be fixed once, when the function is defined.

### restock(connection, product_id, amount, now=None)
1. If amount is 0 or less, raise InvalidValueError. Nothing has been written yet.
2. Open the transaction.
3. Add amount to the product's stock. If no row was updated, the product doesn't exist, so raise UnknownProductError. Nothing to undo.
4. Insert a 'restock' movement with +amount.
5. If step 4 fails, the stock increase from step 3 is rolled back.

### adjust_stock(connection, product_id, change, now=None)
1. If change is 0, raise InvalidValueError.
2. Open the transaction.
3. Add change (it can be negative) to the stock. No row updated means UnknownProductError. If stock would drop below 0, the CHECK constraint refuses it and I raise InsufficientStockError. Nothing has changed in either case.
4. Insert an 'adjustment' movement with the signed change.
5. If step 4 fails, step 3 is rolled back.

### record_sale(connection, items, now=None)
`items` is a list of (product_id, quantity) pairs.
1. If the list is empty, or a quantity isn't a whole number above 0, raise InvalidValueError before anything is written.
2. Open the transaction.
3. Insert the sales row with sold_at set to now, and keep its id.
4. For each pair, in order:
   - Look up the product's current price. No row means UnknownProductError.
   - Insert the sale_items row with that price. A UNIQUE failure means the product was listed twice, so raise DuplicateLineError.
   - Reduce the product's stock by the quantity. A CHECK failure means there wasn't enough, so raise InsufficientStockError.
   - Insert a 'sale' movement with the negative quantity.
5. Return the sale id.

I'm not checking stock or duplicates up front on purpose. I let the database reject them in the middle of the sale, so the rollback is what protects the data and I can test that directly. If line 3 fails, the exception leaves the with block and SQLite undoes the sales row, every sale_items row so far, every stock reduction so far and every movement so far. The earlier lines were written and then removed, so the database ends up exactly as it was before the call.

## 5. Release plan

Six pull requests, each from its own branch with a green CI run before I merge, and each branch deleted after merging.

1. **feature/database-and-seed**: schema.sql, connect, get_db_path, init_schema, table_row_counts, integrity_check, seed_db.py, the first tests, and the CI workflow (ruff and pytest). The workflow goes here because it isn't one of the files allowed straight on main.
2. **feature/products-and-search**: the error classes, add, get, change price, delete, search_products, and tests including the SQL injection test.
3. **feature/reports**: the four reports and their tests.
4. **feature/stock-and-sales**: restock, adjust_stock, record_sale and their tests.
5. **feature/menu-and-container**: main.py, backup_database and its test, the Dockerfile, .dockerignore, the docker-build CI job, and the CHANGELOG entry for 1.0.0. The menu handles bad numbers, blank input, Ctrl-D and Ctrl-C without a traceback. After merging I tag v1.0.0 and tag the image inventory:1.0.0.
6. **feature/low-stock-banner**: the banner showing the number of low stock products, and the CHANGELOG entry for 1.1.0. After merging I tag v1.1.0 and tag the image inventory:1.1.0.


**Container.** The Dockerfile uses a pinned Python 3.14 patch version (I'll confirm the exact tag on Docker Hub when I write it). It copies requirements.txt first and installs it, then copies the code, so the install layer is cached when only the code changes. The image keeps pytest and the tests so CI can run them inside it, which means .dockerignore leaves tests/ alone and excludes .git, .venv, caches and *.db. The database path comes from INVENTORY_DB, set to /data/inventory.db in the image, with a named volume mounted at /data. I use CMD instead of ENTRYPOINT so the same image can run other commands (seed, tests, backup). main.py runs init_schema on start, so an empty volume works.

**Backup and restore.** backup_database copies the live database into a new file with SQLite's backup function (connection.backup), opened through connect(). To restore, I stop the app and copy the backup over the database file. To check a backup, I run integrity_check on it and compare table_row_counts for the original and the copy, and paste that output into the README.

**Rollback.** 1.1.0 only adds the banner and doesn't touch the schema, so one volume works with both versions. I'll run 1.1.0 and add some data, stop it, run 1.0.0 against the same volume, and check the data is still there.

**Tags.** Annotated tags v1.0.0 and v1.1.0 are created on main after the matching PR merges and pushed to GitHub. The Docker image tags 1.0.0 and 1.1.0 match them.