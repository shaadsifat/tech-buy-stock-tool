from app.db import get_connection


# ---------- shareable summary ----------

def get_summary_stats():
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]

        stockout = conn.execute(
            "SELECT COUNT(*) AS c FROM fetch_results WHERE other_stock = 'Out of Stock'"
        ).fetchone()["c"]

        already_updated = conn.execute(
            "SELECT COUNT(*) AS c FROM fetch_results WHERE need_action = 'No'"
        ).fetchone()["c"]

        flagged_total = conn.execute(
            "SELECT COUNT(*) AS c FROM fetch_results WHERE need_action = 'Yes'"
        ).fetchone()["c"]

        updated_today = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM products p
            JOIN fetch_results fr ON fr.product_id = p.id
            WHERE p.reviewed = 1 AND fr.need_action = 'Yes'
            """
        ).fetchone()["c"]

        remaining = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM products p
            JOIN fetch_results fr ON fr.product_id = p.id
            WHERE p.reviewed = 0 AND fr.need_action = 'Yes'
            """
        ).fetchone()["c"]

        return {
            "total": total,
            "stockout": stockout,
            "already_updated": already_updated,
            "flagged_total": flagged_total,
            "updated_today": updated_today,
            "remaining": remaining,
        }
    finally:
        conn.close()


# ---------- dashboard ----------

def get_dashboard_stats():
    conn = get_connection()
    try:
        total_products = conn.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]
        total_categories = conn.execute("SELECT COUNT(*) AS c FROM categories").fetchone()["c"]
        need_action = conn.execute(
            "SELECT COUNT(*) AS c FROM fetch_results WHERE need_action = 'Yes'"
        ).fetchone()["c"]
        return {
            "total_products": total_products,
            "total_categories": total_categories,
            "need_action": need_action,
        }
    finally:
        conn.close()


FETCHED_STATUS_ORDER = ["Fetched", "TechBuy Prob", "Other Prob", "Both Prob", "Not Fetched"]
STOCK_ORDER = ["In Stock", "Out of Stock", "Not Fetched"]
YES_NO_ORDER = ["Yes", "No", "Not Fetched"]


def get_dashboard_report():
    conn = get_connection()
    try:
        def counts(col, order):
            rows = conn.execute(
                f"""
                SELECT {col} AS v, COUNT(*) AS c
                FROM products p
                LEFT JOIN fetch_results fr ON fr.product_id = p.id
                GROUP BY {col}
                """
            ).fetchall()
            raw = {(r["v"] if r["v"] is not None else "Not Fetched"): r["c"] for r in rows}
            return {label: raw.get(label, 0) for label in order}

        reviewed_yes = conn.execute("SELECT COUNT(*) AS c FROM products WHERE reviewed = 1").fetchone()["c"]
        reviewed_no = conn.execute("SELECT COUNT(*) AS c FROM products WHERE reviewed = 0").fetchone()["c"]

        return {
            "fetched_status": counts("fr.fetched_status", FETCHED_STATUS_ORDER),
            "techbuy_stock": counts("fr.techbuy_stock", STOCK_ORDER),
            "other_stock": counts("fr.other_stock", STOCK_ORDER),
            "need_action": counts("fr.need_action", YES_NO_ORDER),
            "updated": counts("fr.updated", YES_NO_ORDER),
            "reviewed": {"Reviewed": reviewed_yes, "Not Reviewed": reviewed_no},
        }
    finally:
        conn.close()


# ---------- categories ----------

def list_categories_with_counts():
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT c.id, c.name, COUNT(p.id) AS product_count
            FROM categories c
            LEFT JOIN products p ON p.category_id = c.id
            GROUP BY c.id, c.name
            ORDER BY c.name COLLATE NOCASE
            """
        ).fetchall()
        return rows
    finally:
        conn.close()


def list_categories():
    conn = get_connection()
    try:
        return conn.execute("SELECT id, name FROM categories ORDER BY name COLLATE NOCASE").fetchall()
    finally:
        conn.close()


def add_category(name):
    name = name.strip()
    if not name:
        return False, "Category name cannot be empty."
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM categories WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        if existing:
            return False, f'Category "{name}" already exists.'
        conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
        return True, None
    finally:
        conn.close()


def delete_category(category_id):
    conn = get_connection()
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM products WHERE category_id = ?", (category_id,)
        ).fetchone()["c"]
        if count > 0:
            return False, f"Cannot delete: {count} product(s) still assigned to this category."
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        conn.commit()
        return True, None
    finally:
        conn.close()


# ---------- products ----------

def _find_duplicate_product(conn, name, techbuy_link, exclude_id=None):
    """Returns an error message if name or Tech Buy Link is already used by another product."""
    exclude_clause = "AND id != ?" if exclude_id is not None else ""
    params_suffix = (exclude_id,) if exclude_id is not None else ()

    if conn.execute(
        f"SELECT id FROM products WHERE name = ? COLLATE NOCASE {exclude_clause}",
        (name,) + params_suffix,
    ).fetchone():
        return f'This is a duplicate — a product named "{name}" already exists.'

    if conn.execute(
        f"SELECT id FROM products WHERE techbuy_link = ? COLLATE NOCASE {exclude_clause}",
        (techbuy_link,) + params_suffix,
    ).fetchone():
        return "This is a duplicate — that Tech Buy Link is already used by another product."

    return None


def add_product(category_id, name, techbuy_link, other_link):
    name = name.strip()
    techbuy_link = techbuy_link.strip()
    other_link = other_link.strip()
    if not (category_id and name and techbuy_link and other_link):
        return False, "All fields are required."
    conn = get_connection()
    try:
        duplicate_error = _find_duplicate_product(conn, name, techbuy_link)
        if duplicate_error:
            return False, duplicate_error

        conn.execute(
            "INSERT INTO products (category_id, name, techbuy_link, other_link) VALUES (?, ?, ?, ?)",
            (category_id, name, techbuy_link, other_link),
        )
        conn.commit()
        return True, None
    finally:
        conn.close()


def is_reviewed_locked(product_id):
    """Reviewed is auto-ticked and locked when Need Action is No — nothing to review."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT need_action FROM fetch_results WHERE product_id = ?", (product_id,)
        ).fetchone()
        return row is not None and row["need_action"] == "No"
    finally:
        conn.close()


def set_reviewed(product_id, reviewed):
    conn = get_connection()
    try:
        conn.execute("UPDATE products SET reviewed = ? WHERE id = ?", (1 if reviewed else 0, product_id))
        conn.commit()
    finally:
        conn.close()


def get_product(product_id):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT id, category_id, name, techbuy_link, other_link FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
    finally:
        conn.close()


def update_product(product_id, category_id, name, techbuy_link, other_link):
    name = name.strip()
    techbuy_link = techbuy_link.strip()
    other_link = other_link.strip()
    if not (category_id and name and techbuy_link and other_link):
        return False, "All fields are required."
    conn = get_connection()
    try:
        duplicate_error = _find_duplicate_product(conn, name, techbuy_link, exclude_id=product_id)
        if duplicate_error:
            return False, duplicate_error

        existing = conn.execute(
            "SELECT techbuy_link, other_link FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        links_changed = existing is not None and (
            existing["techbuy_link"] != techbuy_link or existing["other_link"] != other_link
        )

        conn.execute(
            """
            UPDATE products
            SET category_id = ?, name = ?, techbuy_link = ?, other_link = ?
            WHERE id = ?
            """,
            (category_id, name, techbuy_link, other_link, product_id),
        )

        if links_changed:
            # old fetched price/stock no longer corresponds to the corrected link
            conn.execute("DELETE FROM fetch_results WHERE product_id = ?", (product_id,))

        conn.commit()
        return True, None
    finally:
        conn.close()


SORTABLE_COLUMNS = {
    "name": "p.name",
    "category": "c.name",
    "fetched_status": "fr.fetched_status",
    "need_action": "fr.need_action",
}

# Excel-style checkbox filters only make sense on columns with a small set of
# repeated values (categorical), not continuous numbers like prices/diffs.
FILTERABLE_COLUMNS = {
    "category": "c.name",
    "techbuy_stock": "fr.techbuy_stock",
    "other_stock": "fr.other_stock",
    "need_action": "fr.need_action",
    "fetched_status": "fr.fetched_status",
}

NULL_FILTER_VALUE = "__NULL__"

# "reviewed" is boolean (products.reviewed), not a text column like the others,
# so it's filterable but handled separately from FILTERABLE_COLUMNS.
ALL_FILTER_KEYS = set(FILTERABLE_COLUMNS) | {"reviewed"}


def get_filter_options():
    """Distinct values available for each filterable column, for populating the filter dropdowns."""
    conn = get_connection()
    try:
        options = {}
        for key, col in FILTERABLE_COLUMNS.items():
            rows = conn.execute(
                f"""
                SELECT DISTINCT {col} AS v
                FROM products p
                JOIN categories c ON c.id = p.category_id
                LEFT JOIN fetch_results fr ON fr.product_id = p.id
                ORDER BY {col} COLLATE NOCASE
                """
            ).fetchall()
            values = [r["v"] for r in rows if r["v"] is not None]
            has_null = any(r["v"] is None for r in rows)
            options[key] = {"values": values, "has_null": has_null}

        options["reviewed"] = {"values": ["Yes", "No"], "has_null": False}
        return options
    finally:
        conn.close()


def _build_filter_clauses(filters):
    clauses = []
    params = []
    for key, values in (filters or {}).items():
        if not values:
            continue

        if key == "reviewed":
            mapped = [1 if v == "Yes" else 0 for v in values if v in ("Yes", "No")]
            if mapped:
                placeholders = ",".join("?" for _ in mapped)
                clauses.append(f"p.reviewed IN ({placeholders})")
                params.extend(mapped)
            continue

        col = FILTERABLE_COLUMNS.get(key)
        if not col:
            continue
        include_null = NULL_FILTER_VALUE in values
        real_values = [v for v in values if v != NULL_FILTER_VALUE]
        sub_clauses = []
        if real_values:
            placeholders = ",".join("?" for _ in real_values)
            sub_clauses.append(f"{col} IN ({placeholders})")
            params.extend(real_values)
        if include_null:
            sub_clauses.append(f"{col} IS NULL")
        if sub_clauses:
            clauses.append("(" + " OR ".join(sub_clauses) + ")")
    return clauses, params


def list_products(query="", sort="name", direction="asc", page=1, page_size=20, filters=None):
    sort_col = SORTABLE_COLUMNS.get(sort, "p.name")
    direction = "DESC" if direction.lower() == "desc" else "ASC"
    offset = (page - 1) * page_size

    conn = get_connection()
    try:
        clauses = []
        params = []
        if query:
            clauses.append("p.name LIKE ?")
            params.append(f"%{query}%")

        filter_clauses, filter_params = _build_filter_clauses(filters)
        clauses.extend(filter_clauses)
        params.extend(filter_params)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        total = conn.execute(
            f"""
            SELECT COUNT(*) AS c
            FROM products p
            JOIN categories c ON c.id = p.category_id
            LEFT JOIN fetch_results fr ON fr.product_id = p.id
            {where}
            """,
            params,
        ).fetchone()["c"]

        rows = conn.execute(
            f"""
            SELECT p.id, p.name, c.name AS category, p.techbuy_link, p.other_link, p.reviewed,
                   fr.techbuy_regular, fr.techbuy_sale, fr.techbuy_stock,
                   fr.other_regular, fr.other_sale, fr.other_stock,
                   fr.need_action, fr.fetched_status
            FROM products p
            JOIN categories c ON c.id = p.category_id
            LEFT JOIN fetch_results fr ON fr.product_id = p.id
            {where}
            ORDER BY {sort_col} COLLATE NOCASE {direction}
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        ).fetchall()

        return rows, total
    finally:
        conn.close()


def delete_product(product_id):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM fetch_results WHERE product_id = ?", (product_id,))
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
    finally:
        conn.close()


def get_all_products():
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT id, category_id, name, techbuy_link, other_link FROM products"
        ).fetchall()
    finally:
        conn.close()


def get_all_products_with_category():
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT p.name, c.name AS category, p.techbuy_link, p.other_link
            FROM products p
            JOIN categories c ON c.id = p.category_id
            ORDER BY p.name COLLATE NOCASE
            """
        ).fetchall()
    finally:
        conn.close()


# ---------- fetch_results ----------

def upsert_fetch_result(product_id, data):
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO fetch_results
                (product_id, techbuy_regular, techbuy_sale, techbuy_stock,
                 other_regular, other_sale, other_stock,
                 need_action, updated, fetched_status, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(product_id) DO UPDATE SET
                techbuy_regular=excluded.techbuy_regular,
                techbuy_sale=excluded.techbuy_sale,
                techbuy_stock=excluded.techbuy_stock,
                other_regular=excluded.other_regular,
                other_sale=excluded.other_sale,
                other_stock=excluded.other_stock,
                need_action=excluded.need_action,
                updated=excluded.updated,
                fetched_status=excluded.fetched_status,
                fetched_at=excluded.fetched_at
            """,
            (
                product_id,
                data.get("techbuy_regular"),
                data.get("techbuy_sale"),
                data.get("techbuy_stock"),
                data.get("other_regular"),
                data.get("other_sale"),
                data.get("other_stock"),
                data.get("need_action"),
                data.get("updated"),
                data.get("fetched_status"),
            ),
        )

        if data.get("need_action") == "No":
            # nothing to review — auto-tick and lock it
            conn.execute("UPDATE products SET reviewed = 1 WHERE id = ?", (product_id,))

        conn.commit()
    finally:
        conn.close()


def count_fetch_results():
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) AS c FROM fetch_results").fetchone()["c"]
    finally:
        conn.close()


def clear_fetch_results():
    conn = get_connection()
    try:
        conn.execute("DELETE FROM fetch_results")
        conn.execute("UPDATE products SET reviewed = 0")
        conn.commit()
    finally:
        conn.close()


def reset_all_reviewed():
    conn = get_connection()
    try:
        conn.execute("UPDATE products SET reviewed = 0")
        conn.commit()
    finally:
        conn.close()


def get_export_data():
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT p.name, c.name AS category, p.techbuy_link, p.other_link,
                   fr.techbuy_stock, fr.other_stock,
                   fr.techbuy_regular, fr.techbuy_sale,
                   fr.other_regular, fr.other_sale,
                   fr.need_action,
                   CASE WHEN p.reviewed = 1 AND fr.product_id IS NOT NULL THEN 'Yes' ELSE fr.updated END AS updated,
                   fr.fetched_status
            FROM products p
            JOIN categories c ON c.id = p.category_id
            LEFT JOIN fetch_results fr ON fr.product_id = p.id
            ORDER BY p.name COLLATE NOCASE
            """
        ).fetchall()
    finally:
        conn.close()
