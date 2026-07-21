import sqlite3
import os
from app.config import DATA_DIR, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    name TEXT NOT NULL,
    techbuy_link TEXT NOT NULL,
    other_link TEXT NOT NULL,
    reviewed INTEGER NOT NULL DEFAULT 0,
    shopify_handle TEXT,
    shopify_variant_id TEXT,
    shopify_status TEXT,
    shopify_removed INTEGER NOT NULL DEFAULT 0,
    variant_issue TEXT,
    no_price_sync INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS fetch_results (
    product_id INTEGER PRIMARY KEY REFERENCES products(id),
    techbuy_regular REAL,
    techbuy_sale REAL,
    techbuy_stock TEXT,
    other_regular REAL,
    other_sale REAL,
    other_stock TEXT,
    need_action TEXT,
    updated TEXT,
    fetched_status TEXT,
    fetched_at TEXT DEFAULT (datetime('now'))
);

-- A product with 2+ real Shopify variants gets ONE row in `products` (the parent —
-- carries the shared Other-site link, name, category, etc.) plus one row here per
-- variant. Matched by shopify_variant_id on every sync (like `products` is matched by
-- shopify_handle), so Reviewed and the Other-site comparison fields survive a re-sync —
-- only the Tech Buy name/price/stock get refreshed.
CREATE TABLE IF NOT EXISTS product_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    shopify_variant_id TEXT,
    variant_path TEXT NOT NULL,
    techbuy_regular REAL,
    techbuy_sale REAL,
    techbuy_stock TEXT,
    other_regular REAL,
    other_sale REAL,
    other_stock TEXT,
    need_action TEXT,
    updated TEXT,
    fetched_status TEXT,
    reviewed INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    match_status TEXT,
    match_note TEXT
);

-- Without these, every product-list query (search/sort/filter, and the filter-dropdown
-- population that runs on every page load) full-scans products/product_variants to
-- resolve the category_id join and the "does this product have variants" lookup —
-- measured at ~550ms+~225ms per Single Product List load on ~3700 products before these
-- existed. With them, both queries drop to single-digit milliseconds.
CREATE INDEX IF NOT EXISTS idx_products_category_id ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_product_variants_product_id ON product_variants(product_id);
CREATE INDEX IF NOT EXISTS idx_products_shopify_handle ON products(shopify_handle);

-- Every listing page's WHERE clause filters on no_price_sync (ANDed into nearly every
-- query in models.py), and other_link is the split point for paired vs unpaired
-- products everywhere from the dashboard tiles to Sync Tracking's Missing Other Link
-- tab. shopify_removed/reviewed back their own Sync Tracking tab and filter dropdown.
-- On the product_variants side, shopify_variant_id distinguishes real rows from
-- synthetic Found-OT ones, and match_status/need_action back the Variant Products tab
-- counts and filter dropdowns -- all queried on every page load.
CREATE INDEX IF NOT EXISTS idx_products_no_price_sync ON products(no_price_sync);
CREATE INDEX IF NOT EXISTS idx_products_other_link ON products(other_link);
CREATE INDEX IF NOT EXISTS idx_products_shopify_removed ON products(shopify_removed);
CREATE INDEX IF NOT EXISTS idx_products_reviewed ON products(reviewed);
CREATE INDEX IF NOT EXISTS idx_product_variants_shopify_variant_id ON product_variants(shopify_variant_id);
CREATE INDEX IF NOT EXISTS idx_product_variants_match_status ON product_variants(match_status);
CREATE INDEX IF NOT EXISTS idx_product_variants_need_action ON product_variants(need_action);
"""


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate(conn):
    """Add columns to tables that already existed before this column was introduced."""
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(products)")}
    if "reviewed" not in existing_columns:
        conn.execute("ALTER TABLE products ADD COLUMN reviewed INTEGER NOT NULL DEFAULT 0")

    # Shopify catalog sync (get_product_api_call.py) tracking columns.
    if "shopify_handle" not in existing_columns:
        conn.execute("ALTER TABLE products ADD COLUMN shopify_handle TEXT")
    if "shopify_variant_id" not in existing_columns:
        conn.execute("ALTER TABLE products ADD COLUMN shopify_variant_id TEXT")
    if "shopify_status" not in existing_columns:
        conn.execute("ALTER TABLE products ADD COLUMN shopify_status TEXT")
    if "shopify_removed" not in existing_columns:
        conn.execute("ALTER TABLE products ADD COLUMN shopify_removed INTEGER NOT NULL DEFAULT 0")
    if "variant_issue" not in existing_columns:
        conn.execute("ALTER TABLE products ADD COLUMN variant_issue TEXT")
    if "no_price_sync" not in existing_columns:
        conn.execute("ALTER TABLE products ADD COLUMN no_price_sync INTEGER NOT NULL DEFAULT 0")
    # Dead column from an earlier (fully replaced) variant-matching design — never
    # read anywhere anymore, dropped to stop carrying it forward on every DB.
    if "other_extra_variants" in existing_columns:
        conn.execute("ALTER TABLE products DROP COLUMN other_extra_variants")

    variant_columns = {row["name"] for row in conn.execute("PRAGMA table_info(product_variants)")}
    if variant_columns:  # table may not exist yet on a fresh install — CREATE TABLE handles that
        for col, ddl in [
            ("other_regular", "REAL"),
            ("other_sale", "REAL"),
            ("other_stock", "TEXT"),
            ("need_action", "TEXT"),
            ("updated", "TEXT"),
            ("fetched_status", "TEXT"),
            ("reviewed", "INTEGER NOT NULL DEFAULT 0"),
            ("match_status", "TEXT"),
            ("match_note", "TEXT"),
        ]:
            if col not in variant_columns:
                conn.execute(f"ALTER TABLE product_variants ADD COLUMN {col} {ddl}")


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = get_connection()
    try:
        # WAL lets concurrent fetch-worker threads write without blocking each
        # other on "database is locked" — persists in the DB file, only needs setting once.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()
