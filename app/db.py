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
