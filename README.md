# Inventory Management System

A small inventory tracker for a hardware supplier. It keeps suppliers, products, sales and every stock change in a SQLite database, and gives you a terminal menu to search products, restock, record sales and run four reports. It runs locally in a virtual environment or in a Docker container, and the data survives the container being thrown away.

Current release: **1.1.0** (see [CHANGELOG.md](CHANGELOG.md)). The design and the order I built things in are in [PLAN.md](PLAN.md).

## What's in the repo

| File | What it is |
| --- | --- |
| `schema.sql` | The five tables, constraints and the one index |
| `inventory_db.py` | All the database code. Every SQL statement lives here |
| `seed_db.py` | Loads sample data (and refuses to load it twice) |
| `main.py` | The terminal menu |
| `tests/` | The pytest suite |
| `Dockerfile` | The image |
| `.github/workflows/ci.yml` | CI: lint and tests, plus a Docker build job |

## Running it locally

You need Python 3.11 or newer (I used 3.14). Error handling reads `sqlite_errorname`, which older versions don't have.

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python seed_db.py
python main.py
```

The menu looks like this:

```
Low stock products: 3

Inventory menu
  1. Search products
  2. Look up a product
  3. Add a product
  4. Restock a product
  5. Record a sale
  6. Report: stock value by supplier
  7. Report: low stock
  8. Report: sales by product
  9. Report: never sold
  10. Back up the database
  0. Quit
Choose an option:
```

The first line is the startup banner added in 1.1.0. It counts the products at or below their reorder level.

## Configuration

The database location comes from one environment variable, `INVENTORY_DB`. If it isn't set, the program uses an `inventory.db` file next to the code. The Docker image sets it to `/data/inventory.db`, which is where the volume is mounted.

```
INVENTORY_DB=/tmp/scratch.db python seed_db.py
```

## Tests

```
pytest
ruff check .
```

```
collected 84 items

tests/test_backup.py .                                                                  [  1%]
tests/test_banner.py .                                                                  [  2%]
tests/test_db_helpers.py .....                                                          [  8%]
tests/test_products.py .....................                                            [ 33%]
tests/test_reports.py .......                                                           [ 41%]
tests/test_schema.py ......................                                             [ 67%]
tests/test_search.py ...........                                                        [ 80%]
tests/test_seed.py .....                                                                [ 86%]
tests/test_stock_and_sales.py ...........                                               [100%]

===================================== 84 passed in 0.11s ======================================
All checks passed!
```

I wrote the tests first. For every code change, the commit with the failing tests comes before the commit that makes them pass, so `git log` shows it. CI runs the same tests, and a second job builds the Docker image and runs the tests inside it.

## The database

Five tables: `suppliers`, `products`, `sales`, `sale_items` and `stock_movements`. A few decisions worth knowing about:

- All tables are `STRICT`, so SQLite rejects a value of the wrong type instead of quietly storing it.
- Money is stored as whole cents and only turned into dollars when printed. That avoids floating point rounding.
- SQLite doesn't enforce foreign keys unless you ask, so `connect()` turns them on for every connection. Everything in the project goes through that one function.
- A product that has been sold can't be deleted (`ON DELETE RESTRICT` on `sale_items`). Its stock movements are removed along with it (`ON DELETE CASCADE`).
- Prices, quantities and the movement reason have `CHECK` constraints, so bad data fails in the database even if the Python code forgets to check.
- Values never get pasted into SQL strings. Every query uses placeholders.
- `sale_items` has an index on `product_id`. Without it, deleting a product or finding which products have sales means reading the whole table. SQLite uses it like this:

```
EXPLAIN QUERY PLAN SELECT 1 FROM sale_items WHERE product_id = 1

SEARCH sale_items USING COVERING INDEX idx_sale_items_product_id (product_id=?)
```

## Seeding and the reports

The seed loads 4 suppliers, 12 products, 5 sales and 12 sale lines. Running it a second time is refused so it can't double the data:

```
$ python seed_db.py
Sample data loaded.
suppliers: 4
products: 12
sales: 5
sale_items: 12
stock_movements: 0

$ python seed_db.py   (second run)
The database already has data, so nothing was loaded.
suppliers: 4
products: 12
sales: 5
sale_items: 12
stock_movements: 0
```

The four reports, run from the menu (options 6, 7, 8 and 9):

```
Low stock products: 3

(menu omitted)
Choose an option: Supplier                   Stock value
-------------------------  -----------
Pioneer Tool Co.           1124.75
Summit Building Supply     1058.72
Northline Hardware Supply  722.13
BrightWire Electrical      599.48

(menu omitted)
Choose an option: SKU          Name                       In stock  Reorder level  Short by
-----------  -------------------------  --------  -------------  --------
HT-SCR-SET   Screwdriver Set (6 piece)  3         8              5
EL-OUT-GFCI  GFCI Outlet                0         3              3
PT-SAW-7Q    7-1/4 in Circular Saw      4         4              0

(menu omitted)
Choose an option: SKU          Name                       Units sold  Revenue
-----------  -------------------------  ----------  -------
PT-DRL-18V   18V Cordless Drill         1           89.99
PT-SAW-7Q    7-1/4 in Circular Saw      1           74.99
HT-HAM-16    16oz Claw Hammer           3           45.97
EL-EXT-25    Extension Cord 25 ft       2           39.98
FA-SCR-100   Wood Screws Box of 100     5           39.95
EL-BULB-4    LED Bulbs 4-pack           4           35.96
EL-OUT-GFCI  GFCI Outlet                2           33.98
FA-NAIL-1LB  Common Nails 1 lb          5           24.95
HT-WRN-ADJ   Adjustable Wrench 10 in    1           18.99
HT-SCR-SET   Screwdriver Set (6 piece)  1           12.99

(menu omitted)
Choose an option: SKU         Name
----------  ---------------------
FA-ANC-50   Drywall Anchors 50 ct
HT-TAPE-25  Tape Measure 25 ft

(menu omitted)
Choose an option: Goodbye.
```

A few things to notice in those numbers:

- **Stock value by supplier:** Pioneer Tool Co. holds the most, BrightWire Electrical the least.
- **Low stock:** a product exactly at its reorder level counts as low, which is why the circular saw (4 in stock, level 4) is listed with a shortfall of 0.
- **Sales by product:** revenue uses the price each sale was made at, not today's price. The hammer sold three units for $45.97, not 3 × $15.99 = $47.97, because its price changed after the first sale.
- **Never sold:** two products appear in no sale at all.

## What happens when a sale fails halfway

Recording a sale does several things: create the sale, then for each line reduce the stock, store the line at the current price, and log a stock movement. All of it runs inside one `with connection:` block. If any line fails, the exception rolls back everything, including the sale row and the lines already written.

To show it, this script sells 1 hammer (24 in stock) and then 99 screwdriver sets (only 3 in stock). The first line is fine and the second can't succeed. It prints the table counts and the stock levels before and after:

```python
import inventory_db as db
import seed_db

c = db.connect(":memory:")
db.init_schema(c)
seed_db.load_sample_data(c)

def snapshot(label):
    print(label)
    print("  rows:", db.table_row_counts(c))
    for pid in (1, 2):
        p = db.get_product(c, pid)
        print("  product", pid, p["name"], "in stock:", p["quantity_in_stock"])

snapshot("before")
print("recording a sale: 1 of product 1, then 99 of product 2")
try:
    db.record_sale(c, [(1, 1), (2, 99)])
except Exception as exc:
    print("failed:", type(exc).__name__ + ":", exc)
snapshot("after")
```

```
before
  rows: {'suppliers': 4, 'products': 12, 'sales': 5, 'sale_items': 12, 'stock_movements': 0}
  product 1 16oz Claw Hammer in stock: 24
  product 2 Screwdriver Set (6 piece) in stock: 3
recording a sale: 1 of product 1, then 99 of product 2
failed: InsufficientStockError: Not enough stock of product 2 for a change of -99.
after
  rows: {'suppliers': 4, 'products': 12, 'sales': 5, 'sale_items': 12, 'stock_movements': 0}
  product 1 16oz Claw Hammer in stock: 24
  product 2 Screwdriver Set (6 piece) in stock: 3
```

Nothing is left behind. There's no new sale, no new sale line, no stock movement, and the hammer's stock is back to 24 even though its line was written before the second line failed.

## Docker

The image starts from a pinned `python:3.14.10-slim`. `requirements.txt` is copied and installed before the code, so changing the code doesn't reinstall the packages. The image sets `INVENTORY_DB=/data/inventory.db` and declares `/data` as a volume. It starts the menu with `CMD`, so I can run other commands in the same image, like the seed script or the tests.

```
docker build -t inventory:1.1.0 .
```

```
[+] Building 0.5s (10/10) FINISHED                                        docker:desktop-linux
 => [internal] load build definition from Dockerfile                                      0.0s
 => => transferring dockerfile: 616B                                                      0.0s
 => [internal] load metadata for docker.io/library/python:3.14.10-slim                    0.3s
 => [internal] load .dockerignore                                                         0.0s
 => => transferring context: 107B                                                         0.0s
 => [1/5] FROM docker.io/library/python:3.14.10-slim@sha256:930e1abba7c4e8f96ed93e8012c3  0.0s
 => => resolve docker.io/library/python:3.14.10-slim@sha256:930e1abba7c4e8f96ed93e8012c3  0.0s
 => [internal] load build context                                                         0.0s
 => => transferring context: 11.57kB                                                      0.0s
 => CACHED [2/5] WORKDIR /app                                                             0.0s
 => CACHED [3/5] COPY requirements.txt .                                                  0.0s
 => CACHED [4/5] RUN pip install --no-cache-dir -r requirements.txt                       0.0s
 => [5/5] COPY . .                                                                        0.0s
 => exporting to image                                                                    0.1s
 => => exporting layers                                                                   0.0s
 => => naming to docker.io/library/inventory:1.1.0                                        0.0s
 => => unpacking to docker.io/library/inventory:1.1.0                                     0.0s
```

(The layers were cached because only the code changed since 1.0.0. I removed the manifest lines at the end.)

To use it, keep the data in a named volume:

```
docker run --rm -v inventory-data:/data inventory:1.1.0 python seed_db.py   # once
docker run -it --rm -v inventory-data:/data inventory:1.1.0                 # the menu
docker run --rm inventory:1.1.0 python -m pytest                            # the tests
```

`-it` is needed for the menu because it reads from the keyboard. The container is deleted when it exits (`--rm`), but the data isn't, because it lives in the volume. The transcript in the next section shows that.

## Rolling back from 1.1.0 to 1.0.0

Both versions are tagged in git (`v1.0.0`, `v1.1.0`) and built as images (`inventory:1.0.0`, `inventory:1.1.0`). 1.1.0 only adds the startup banner and doesn't touch the schema, so 1.0.0 can open a database that 1.1.0 has written to. To show it, I restocked a product under 1.1.0, then started 1.0.0 on the same volume. `CHECK` is a one-line script that prints a product, the table row counts and the result of SQLite's integrity check:

```
CHECK="import inventory_db as db; c = db.connect(db.get_db_path()); p = db.get_product(c, 2); print(p['name'], p['quantity_in_stock']); print(db.table_row_counts(c)); print('integrity:', db.integrity_check(c))"
```

```
$ run 1.1.0 and restock product 2 by 10 (the banner shows at start)
Low stock products: 3

(menu omitted)
Choose an option: Product id: Amount to add: Restocked. Screwdriver Set (6 piece) now has 13.

(menu omitted)
Choose an option: Goodbye.

$ data under 1.1.0
Screwdriver Set (6 piece) 13
{'suppliers': 4, 'products': 12, 'sales': 5, 'sale_items': 12, 'stock_movements': 2}
integrity: ok

$ roll back: run 1.0.0 on the same volume (no banner)

(menu omitted)
Choose an option: Goodbye.

$ data under 1.0.0
Screwdriver Set (6 piece) 13
{'suppliers': 4, 'products': 12, 'sales': 5, 'sale_items': 12, 'stock_movements': 2}
integrity: ok
```

(Input was piped in, so the prompts run together on one line.) The stock change made under 1.1.0 is still there under 1.0.0, nothing was lost, and the integrity check passes. This also shows the data outliving the containers: each `docker run --rm` is a new container reading the same volume.

This only works because 1.1.0 didn't change the schema. A release that does would need its own rollback note in the changelog and a backup before upgrading.

## Backup and restore

Menu option 10 copies the live database with SQLite's backup API, which gives a consistent copy even while the database is open. It then opens the copy, runs an integrity check on it and prints its row counts, so you can compare them against the original straight away. The default file name carries a timestamp (the container clock, which is UTC).

```
$ original database
Screwdriver Set (6 piece) 13
{'suppliers': 4, 'products': 12, 'sales': 5, 'sale_items': 12, 'stock_movements': 2}
integrity: ok

$ back up from the menu (option 10, default file name)
Low stock products: 2

(menu omitted)
Choose an option: Backup file (Enter for /data/inventory_backup_20261104_183251.db): Backup saved to /data/inventory_backup_20261104_183251.db
Integrity check: ok
Row counts: {'suppliers': 4, 'products': 12, 'sales': 5, 'sale_items': 12, 'stock_movements': 2}

(menu omitted)
Choose an option: Goodbye.

$ files in the volume
total 84
-rw-r--r-- 1 root root 40960 Nov  4 18:32 inventory.db
-rw-r--r-- 1 root root 40960 Nov  4 18:32 inventory_backup_20261104_183251.db
```

The row counts of the copy match the original, and the integrity check says `ok`.

Restoring is a file copy, done while the app isn't running. To show that it actually undoes something, I changed the live database after the backup (a restock, so the stock goes up and one more movement is logged), then copied the backup back over `inventory.db`:

```
$ restock product 2 by 10 so the live database differs from the backup
Low stock products: 2

(menu omitted)
Choose an option: Product id: Amount to add: Restocked. Screwdriver Set (6 piece) now has 23.

(menu omitted)
Choose an option: Goodbye.

$ check the live database
Screwdriver Set (6 piece) 23
{'suppliers': 4, 'products': 12, 'sales': 5, 'sale_items': 12, 'stock_movements': 3}
integrity: ok

$ restore: copy the backup over inventory.db
docker run --rm -v inventory-data:/data inventory:1.1.0 sh -c "cp /data/inventory_backup_*.db /data/inventory.db"

$ check after restore
Screwdriver Set (6 piece) 13
{'suppliers': 4, 'products': 12, 'sales': 5, 'sale_items': 12, 'stock_movements': 2}
integrity: ok
```

After the restore the stock and the movement count are back to the backup's values (13 and 2). If there are several backups in the volume, name the file you want instead of using the `*` wildcard.

## Self-review

**What I'd do differently.** The movement log says that a sale reduced stock but not which sale, because `stock_movements` has no `sale_id`. Adding that column would let me trace any change back to its cause. The menu is also the least tested part. The logic that matters is in `inventory_db.py` and is covered, but the input loops and printing in `main.py` I only checked by running them, and I'd split the parsing from the printing so they could be tested. Last, search uses `LIKE`, so a `%` or `_` typed into a search acts as a wildcard instead of a literal character. It's harmless here, but I know about it and haven't fixed it.

**One thing for a reviewer to check.** `stock_movements.product_id` is `ON DELETE CASCADE`, so deleting a product also deletes its movement history. I chose that so a product that was never sold can still be deleted cleanly, but it means audit rows disappear. I'm not sure that's right for a table whose job is to be a record, and I'd like a second opinion on whether it should be `RESTRICT`, or a soft delete instead.