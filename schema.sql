-- Inventory database schema.
-- Safe to run more than once: every statement uses IF NOT EXISTS, so running it
-- again changes nothing and keeps the data.
-- Money is stored as whole cents. Times are stored as ISO 8601 text.

CREATE TABLE IF NOT EXISTS suppliers (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    CONSTRAINT supplier_name_not_blank CHECK (length(trim(name)) > 0)
) STRICT;

CREATE TABLE IF NOT EXISTS products (
    id                INTEGER PRIMARY KEY,
    sku               TEXT    NOT NULL UNIQUE,
    name              TEXT    NOT NULL,
    category          TEXT    NOT NULL,
    supplier_id       INTEGER NOT NULL REFERENCES suppliers (id) ON DELETE RESTRICT,
    unit_price_cents  INTEGER NOT NULL,
    quantity_in_stock INTEGER NOT NULL,
    reorder_level     INTEGER NOT NULL,
    CONSTRAINT sku_not_blank        CHECK (length(trim(sku)) > 0),
    CONSTRAINT name_not_blank       CHECK (length(trim(name)) > 0),
    CONSTRAINT category_not_blank   CHECK (length(trim(category)) > 0),
    CONSTRAINT price_not_negative   CHECK (unit_price_cents >= 0),
    CONSTRAINT stock_not_negative   CHECK (quantity_in_stock >= 0),
    CONSTRAINT reorder_not_negative CHECK (reorder_level >= 0)
) STRICT;

CREATE TABLE IF NOT EXISTS sales (
    id      INTEGER PRIMARY KEY,
    sold_at TEXT NOT NULL
) STRICT;

-- unit_price_cents is the price charged at the time of the sale, copied from the
-- product, so later price changes do not rewrite sales history.
CREATE TABLE IF NOT EXISTS sale_items (
    id               INTEGER PRIMARY KEY,
    sale_id          INTEGER NOT NULL REFERENCES sales (id) ON DELETE RESTRICT,
    product_id       INTEGER NOT NULL REFERENCES products (id) ON DELETE RESTRICT,
    quantity         INTEGER NOT NULL,
    unit_price_cents INTEGER NOT NULL,
    CONSTRAINT quantity_positive       CHECK (quantity > 0),
    CONSTRAINT sale_price_not_negative CHECK (unit_price_cents >= 0),
    CONSTRAINT one_line_per_product    UNIQUE (sale_id, product_id)
) STRICT;

-- The log of every stock change. quantity_change is signed: restocks are
-- positive, sales are negative, adjustments can be either.
-- Deleting a product deletes its log rows (a product with sales cannot be
-- deleted at all, because of the RESTRICT on sale_items).
CREATE TABLE IF NOT EXISTS stock_movements (
    id              INTEGER PRIMARY KEY,
    product_id      INTEGER NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    quantity_change INTEGER NOT NULL,
    reason          TEXT    NOT NULL,
    moved_at        TEXT    NOT NULL,
    CONSTRAINT change_not_zero CHECK (quantity_change <> 0),
    CONSTRAINT reason_is_valid CHECK (reason IN ('restock', 'adjustment', 'sale'))
) STRICT;

-- SQLite does not index the child side of a foreign key by itself. This index
-- serves the sales-by-product report, the never-sold report, and the check
-- SQLite makes when a product is deleted.
CREATE INDEX IF NOT EXISTS idx_sale_items_product_id ON sale_items (product_id);