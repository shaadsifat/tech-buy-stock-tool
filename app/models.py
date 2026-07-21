from urllib.parse import urlparse

from app.db import get_connection
from app.scraping import registry


# ---------- other websites ----------

def get_other_site_counts():
    """Domain (from each product's other_link) -> how many products use it."""
    conn = get_connection()
    try:
        links = [r["other_link"] for r in conn.execute("SELECT other_link FROM products").fetchall()]
    finally:
        conn.close()

    counts = {}
    for link in links:
        domain = urlparse(link).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        if not domain:
            domain = "(unrecognized link)"
        counts[domain] = counts.get(domain, 0) + 1
    return counts


# ---------- shared product-vs-variant aggregation helpers ----------

# Used by the shareable summary text AND the dashboard graphs below — a variant-parent
# product with 3 variants is still just 1 product for both, exactly like a single-variant
# product. A variant-parent's fetch_results row never carries real data (need_action/
# fetched_status/stock all live per-variant in product_variants instead), so each
# variant-parent product's per-column value is collapsed down to one aggregate value via
# _VARIANT_PRODUCT_AGG before being combined with the single-product rows. Both exclude
# No Price Sync products entirely — they're outside the whole comparison workflow.
_SINGLE_PRODUCT_FILTER = (
    "NOT EXISTS (SELECT 1 FROM product_variants pv WHERE pv.product_id = p.id) AND p.no_price_sync = 0"
)

# "Bad"/actionable states win if ANY variant has them (the whole product needs attention
# if even one variant does); an all-clear/complete state only applies once EVERY variant
# agrees; otherwise NULL ("Not Fetched" / not yet resolved) — same rule already used for
# the Variant Products page's aggregate Need Action and Reviewed columns.
_VARIANT_PRODUCT_AGG = """
    SELECT pv.product_id,
           CASE WHEN SUM(CASE WHEN pv.need_action = 'Yes' THEN 1 ELSE 0 END) > 0 THEN 'Yes'
                WHEN SUM(CASE WHEN pv.need_action = 'No' THEN 1 ELSE 0 END) = COUNT(*) THEN 'No'
                ELSE NULL END AS need_action,
           CASE WHEN SUM(CASE WHEN pv.fetched_status = 'Fetch Problem' THEN 1 ELSE 0 END) > 0 THEN 'Fetch Problem'
                WHEN SUM(CASE WHEN pv.fetched_status = 'Fetched' THEN 1 ELSE 0 END) = COUNT(*) THEN 'Fetched'
                ELSE NULL END AS fetched_status,
           CASE WHEN SUM(CASE WHEN pv.updated = 'No' THEN 1 ELSE 0 END) > 0 THEN 'No'
                WHEN SUM(CASE WHEN pv.updated = 'Yes' THEN 1 ELSE 0 END) = COUNT(*) THEN 'Yes'
                ELSE NULL END AS updated,
           CASE WHEN SUM(CASE WHEN pv.techbuy_stock = 'In Stock' THEN 1 ELSE 0 END) > 0 THEN 'In Stock'
                WHEN SUM(CASE WHEN pv.techbuy_stock = 'Out of Stock' THEN 1 ELSE 0 END) = COUNT(*) THEN 'Out of Stock'
                ELSE NULL END AS techbuy_stock,
           CASE WHEN SUM(CASE WHEN pv.other_stock = 'In Stock' THEN 1 ELSE 0 END) > 0 THEN 'In Stock'
                WHEN SUM(CASE WHEN pv.other_stock = 'Out of Stock' THEN 1 ELSE 0 END) = COUNT(*) THEN 'Out of Stock'
                ELSE NULL END AS other_stock,
           CASE WHEN COUNT(*) = SUM(CASE WHEN pv.reviewed = 1 THEN 1 ELSE 0 END) THEN 1 ELSE 0 END AS reviewed
    FROM product_variants pv
    JOIN products p ON p.id = pv.product_id
    WHERE p.no_price_sync = 0
    GROUP BY pv.product_id
"""


# ---------- dashboard ----------

FETCHED_STATUS_ORDER = ["Fetched", "Fetch Problem", "Not Fetched"]
STOCK_ORDER = ["In Stock", "Out of Stock", "Not Fetched"]
YES_NO_ORDER = ["Yes", "No", "Not Fetched"]


def get_dashboard_data():
    """Single-pass dashboard computation. The Dashboard page (and its every-1.5s poll
    while a fetch is running, via /dashboard/stats) used to call three separate
    functions that each re-ran the product_variants aggregation subquery for every
    condition they needed (14 full JOIN+GROUP BY scans per page load combined). Here
    the two underlying row sets — single products joined with their fetch_results, and
    the per-product variant aggregates — are each queried once, and every count/
    breakdown used by the summary text, the dashboard tiles, and the report page is
    derived from them in Python."""
    conn = get_connection()
    try:
        singles = conn.execute(
            f"""
            SELECT p.reviewed AS reviewed, fr.need_action AS need_action, fr.fetched_status AS fetched_status,
                   fr.other_stock AS other_stock, fr.updated AS updated, fr.techbuy_stock AS techbuy_stock
            FROM products p
            JOIN fetch_results fr ON fr.product_id = p.id
            WHERE {_SINGLE_PRODUCT_FILTER}
            """
        ).fetchall()
        variants = conn.execute(_VARIANT_PRODUCT_AGG).fetchall()
        total_products = conn.execute("SELECT COUNT(*) AS c FROM products WHERE no_price_sync = 0").fetchone()["c"]
        total_categories = conn.execute("SELECT COUNT(*) AS c FROM categories").fetchone()["c"]
        has_reference = conn.execute(
            "SELECT COUNT(*) AS c FROM products WHERE other_link != '' AND no_price_sync = 0"
        ).fetchone()["c"]
    finally:
        conn.close()

    rows = list(singles) + list(variants)

    def count_where(pred):
        return sum(1 for r in rows if pred(r))

    def breakdown(col, order):
        raw = {}
        for r in rows:
            v = r[col] if r[col] is not None else "Not Fetched"
            raw[v] = raw.get(v, 0) + 1
        return {label: raw.get(label, 0) for label in order}

    stockout = count_where(lambda r: r["other_stock"] == "Out of Stock")
    already_updated = count_where(lambda r: r["need_action"] == "No")
    flagged_total = count_where(lambda r: r["need_action"] == "Yes")
    updated_today = count_where(lambda r: r["reviewed"] == 1 and r["need_action"] == "Yes")
    remaining = count_where(lambda r: r["reviewed"] == 0 and r["need_action"] == "Yes")
    fetch_problems = count_where(lambda r: r["fetched_status"] == "Fetch Problem")
    perfectly_fetched = count_where(lambda r: r["fetched_status"] == "Fetched")
    reviewed_yes = count_where(lambda r: r["reviewed"] == 1)

    return {
        "summary": {
            "total": total_products,
            "stockout": stockout,
            "already_updated": already_updated,
            "flagged_total": flagged_total,
            "updated_today": updated_today,
            "remaining": remaining,
        },
        "stats": {
            "total_products": total_products,
            "has_reference": has_reference,
            "total_categories": total_categories,
            "need_action": flagged_total,
            "fetch_problems": fetch_problems,
            "perfectly_fetched": perfectly_fetched,
        },
        "report": {
            "fetched_status": breakdown("fetched_status", FETCHED_STATUS_ORDER),
            "techbuy_stock": breakdown("techbuy_stock", STOCK_ORDER),
            "other_stock": breakdown("other_stock", STOCK_ORDER),
            "need_action": breakdown("need_action", YES_NO_ORDER),
            "updated": breakdown("updated", YES_NO_ORDER),
            "reviewed": {"Reviewed": reviewed_yes, "Not Reviewed": total_products - reviewed_yes},
        },
    }


# ---------- categories ----------

CATEGORY_SORT_COLUMNS = {
    "name": "c.name COLLATE NOCASE",
    "count": "product_count",
}


def list_categories_with_counts(page=1, page_size=None, sort="name", direction="asc", query=""):
    sort_col = CATEGORY_SORT_COLUMNS.get(sort, CATEGORY_SORT_COLUMNS["name"])
    direction = "DESC" if direction.lower() == "desc" else "ASC"
    where = "WHERE c.name LIKE ?" if query else ""
    params = [f"%{query}%"] if query else []

    conn = get_connection()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM categories c {where}", params
        ).fetchone()["c"]

        sql = f"""
            SELECT c.id, c.name, COUNT(p.id) AS product_count
            FROM categories c
            LEFT JOIN products p ON p.category_id = c.id
            {where}
            GROUP BY c.id, c.name
            ORDER BY {sort_col} {direction}
        """

        if page_size is None:
            rows = conn.execute(sql, params).fetchall()
        else:
            offset = (page - 1) * page_size
            rows = conn.execute(sql + " LIMIT ? OFFSET ?", params + [page_size, offset]).fetchall()

        return rows, total
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


def get_product_by_handle(handle):
    """Products only ever get created by the Shopify catalog sync now — bulk upload can
    only attach an Other-site link to a product that already exists, matched by this
    handle (never by name, which isn't guaranteed unique/stable the way the handle is).
    Case-insensitive, since the handle is derived from a Tech Buy Link typed/pasted into
    an Excel file, not copied byte-for-byte from Shopify."""
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT id, shopify_handle, techbuy_link FROM products WHERE shopify_handle = ? COLLATE NOCASE",
            (handle,),
        ).fetchone()
    finally:
        conn.close()


def set_other_link(product_id, other_link):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE products SET other_link = ? WHERE id = ?", (clean_other_link(other_link), product_id)
        )
        conn.commit()
    finally:
        conn.close()


def is_reviewed_locked(product_id):
    """Reviewed is auto-ticked and locked when Need Action is No — nothing to review.
    (Need Action itself already accounts for both price and stock status matching.)"""
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
    other_link = clean_other_link(other_link)
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

# "reviewed", "shopify_status" and "other_link" are booleans/derived (products.reviewed,
# shopify_removed+shopify_status, other_link != ''), and "other_site" is derived from
# other_link's domain — none are plain text columns like the others, so all four are
# filterable but handled separately from FILTERABLE_COLUMNS.
ALL_FILTER_KEYS = set(FILTERABLE_COLUMNS) | {"reviewed", "other_site", "shopify_status", "other_link", "no_price_sync"}


def clean_other_link(url):
    """Strips query string/fragment (tracking codes, ?ref=..., #anchor, etc.) off an
    Other-site link, keeping just the clean product URL — those params are only ever
    tracking/filter noise, never anything the scraper needs to find the right page."""
    url = (url or "").strip()
    if not url:
        return url
    parsed = urlparse(url)
    return parsed._replace(query="", fragment="").geturl()


def _other_site_name(other_link):
    return registry.get_site_display_name(registry.domain_of(other_link))


def get_filter_options():
    """Distinct values available for each filterable column, for populating the filter
    dropdowns — every option offered here is checked against what the data actually
    contains, so a value that never occurs (e.g. no product is currently a Draft) simply
    doesn't appear as a choice."""
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
                WHERE {_SINGLE_PRODUCT_FILTER}
                ORDER BY {col} COLLATE NOCASE
                """
            ).fetchall()
            values = [r["v"] for r in rows if r["v"] is not None]
            has_null = any(r["v"] is None for r in rows)
            options[key] = {"values": values, "has_null": has_null}

        reviewed_rows = conn.execute(
            f"SELECT DISTINCT p.reviewed AS v FROM products p WHERE {_SINGLE_PRODUCT_FILTER}"
        ).fetchall()
        reviewed_values = []
        if any(r["v"] == 1 for r in reviewed_rows):
            reviewed_values.append("Yes")
        if any(r["v"] == 0 for r in reviewed_rows):
            reviewed_values.append("No")
        options["reviewed"] = {"values": reviewed_values, "has_null": False}

        status_rows = conn.execute(
            f"SELECT DISTINCT p.shopify_removed AS removed, p.shopify_status AS status FROM products p WHERE {_SINGLE_PRODUCT_FILTER}"
        ).fetchall()
        shopify_status_values = []
        if any(r["removed"] == 1 for r in status_rows):
            shopify_status_values.append("Removed")
        if any(r["removed"] == 0 and r["status"] == "ACTIVE" for r in status_rows):
            shopify_status_values.append("Active")
        if any(r["removed"] == 0 and r["status"] == "DRAFT" for r in status_rows):
            shopify_status_values.append("Draft")
        options["shopify_status"] = {"values": shopify_status_values, "has_null": False}

        link_rows = conn.execute(
            f"SELECT DISTINCT (p.other_link != '') AS has_link FROM products p WHERE {_SINGLE_PRODUCT_FILTER}"
        ).fetchall()
        other_link_values = []
        if any(r["has_link"] == 1 for r in link_rows):
            other_link_values.append("Has Link")
        if any(r["has_link"] == 0 for r in link_rows):
            other_link_values.append("No Link")
        options["other_link"] = {"values": other_link_values, "has_null": False}

        links = [
            r["other_link"] for r in conn.execute(
                f"SELECT DISTINCT other_link FROM products p WHERE {_SINGLE_PRODUCT_FILTER}"
            ).fetchall()
        ]
        site_names = sorted({_other_site_name(link) for link in links if link}, key=str.lower)
        options["other_site"] = {"values": site_names, "has_null": False}

        return options
    finally:
        conn.close()


def _resolve_other_site_product_ids(conn, selected_names):
    """Product ids whose Other Site display name is in selected_names."""
    selected = set(selected_names)
    rows = conn.execute("SELECT id, other_link FROM products").fetchall()
    return [r["id"] for r in rows if _other_site_name(r["other_link"]) in selected]


def _build_filter_clauses(conn, filters):
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

        if key == "shopify_status":
            sub_clauses = []
            if "Removed" in values:
                sub_clauses.append("p.shopify_removed = 1")
            if "Active" in values:
                sub_clauses.append("(p.shopify_removed = 0 AND p.shopify_status = 'ACTIVE')")
            if "Draft" in values:
                sub_clauses.append("(p.shopify_removed = 0 AND p.shopify_status = 'DRAFT')")
            if sub_clauses:
                clauses.append("(" + " OR ".join(sub_clauses) + ")")
            continue

        if key == "other_site":
            ids = _resolve_other_site_product_ids(conn, values) or [-1]
            placeholders = ",".join("?" for _ in ids)
            clauses.append(f"p.id IN ({placeholders})")
            params.extend(ids)
            continue

        if key == "other_link":
            sub_clauses = []
            if "Has Link" in values:
                sub_clauses.append("p.other_link != ''")
            if "No Link" in values:
                sub_clauses.append("p.other_link = ''")
            if sub_clauses:
                clauses.append("(" + " OR ".join(sub_clauses) + ")")
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


NO_SYNC_SORT_COLUMNS = {
    "name": "p.name COLLATE NOCASE",
    "category": "c.name COLLATE NOCASE",
}


def get_no_price_sync_filter_options():
    """Dynamic like every other filter dropdown in the app — only offers a choice that
    actually occurs in the data right now."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT DISTINCT no_price_sync AS v FROM products").fetchall()
        values = []
        if any(r["v"] == 1 for r in rows):
            values.append("Yes")
        if any(r["v"] == 0 for r in rows):
            values.append("No")
        return {"no_price_sync": {"values": values, "has_null": False}}
    finally:
        conn.close()


def list_products_for_no_sync(query="", category="", sort="name", direction="asc", page=1, page_size=20, filters=None):
    """Every product — single AND variant-parent both, unlike Single Product List/Variant
    Products which split by variant count — for the No Price Sync page. Whether a product
    has variants doesn't matter here; only whether you've flagged it as self-priced."""
    sort_col = NO_SYNC_SORT_COLUMNS.get(sort, NO_SYNC_SORT_COLUMNS["name"])
    direction = "DESC" if direction.lower() == "desc" else "ASC"

    clauses = []
    params = []
    if query:
        clauses.append("p.name LIKE ?")
        params.append(f"%{query}%")
    if category:
        clauses.append("c.name = ?")
        params.append(category)

    no_sync_values = (filters or {}).get("no_price_sync")
    if no_sync_values:
        mapped = [1 if v == "Yes" else 0 for v in no_sync_values if v in ("Yes", "No")]
        if mapped:
            placeholders = ",".join("?" for _ in mapped)
            clauses.append(f"p.no_price_sync IN ({placeholders})")
            params.extend(mapped)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    conn = get_connection()
    try:
        total = conn.execute(
            f"""
            SELECT COUNT(*) AS c
            FROM products p
            JOIN categories c ON c.id = p.category_id
            {where}
            """,
            params,
        ).fetchone()["c"]

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"""
            SELECT p.id, p.name, c.name AS category, p.techbuy_link, p.other_link, p.no_price_sync,
                   EXISTS (SELECT 1 FROM product_variants pv WHERE pv.product_id = p.id) AS is_variant_parent
            FROM products p
            JOIN categories c ON c.id = p.category_id
            {where}
            ORDER BY {sort_col} {direction}
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        ).fetchall()

        return rows, total
    finally:
        conn.close()


def count_no_price_sync():
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) AS c FROM products WHERE no_price_sync = 1").fetchone()["c"]
    finally:
        conn.close()


def set_no_price_sync(product_ids, flag):
    """Flags/unflags the given products as No Price Sync (official distributor pricing —
    no competitor comparison needed). Doesn't touch other_link — kept as-is, just ignored
    everywhere while the flag is set, so re-enabling later loses nothing."""
    if not product_ids:
        return 0
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in product_ids)
        cur = conn.execute(
            f"UPDATE products SET no_price_sync = ? WHERE id IN ({placeholders})",
            [1 if flag else 0] + list(product_ids),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def list_products(query="", sort="name", direction="asc", page=1, page_size=20, filters=None):
    """Single-variant products only — anything with 2+ real Shopify variants lives on the
    separate Variant Products page instead, one row per variant there instead of here."""
    sort_col = SORTABLE_COLUMNS.get(sort, "p.name")
    direction = "DESC" if direction.lower() == "desc" else "ASC"
    offset = (page - 1) * page_size

    conn = get_connection()
    try:
        clauses = [
            "NOT EXISTS (SELECT 1 FROM product_variants pv WHERE pv.product_id = p.id)",
            "p.no_price_sync = 0",
        ]
        params = []
        if query:
            clauses.append("p.name LIKE ?")
            params.append(f"%{query}%")

        filter_clauses, filter_params = _build_filter_clauses(conn, filters)
        clauses.extend(filter_clauses)
        params.extend(filter_params)

        where = "WHERE " + " AND ".join(clauses)

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
                   p.shopify_handle, p.shopify_status, p.shopify_removed, p.variant_issue,
                   fr.techbuy_regular, fr.techbuy_sale, fr.techbuy_stock,
                   fr.other_regular, fr.other_sale, fr.other_stock,
                   fr.need_action, fr.fetched_status, fr.fetched_at
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
    """Deletes the whole product. Variant-parent products have child rows in
    product_variants that FK-reference this product — those must go first, or the
    products delete raises an IntegrityError and nothing (not even fetch_results) commits."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM product_variants WHERE product_id = ?", (product_id,))
        conn.execute("DELETE FROM fetch_results WHERE product_id = ?", (product_id,))
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
    finally:
        conn.close()


def delete_products_without_link_or_no_sync():
    """Deletes every product that has no other-site link and isn't flagged No Price
    Sync — used by the Shopify sync script to clear stale/never-paired products before
    each full re-pull, so only products worth tracking (paired, or intentionally
    unpaired via No Price Sync) survive a sync. Returns the count deleted."""
    conn = get_connection()
    try:
        ids = [
            r["id"] for r in conn.execute(
                "SELECT id FROM products WHERE other_link = '' AND no_price_sync = 0"
            ).fetchall()
        ]
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        conn.execute(f"DELETE FROM product_variants WHERE product_id IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM fetch_results WHERE product_id IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM products WHERE id IN ({placeholders})", ids)
        conn.commit()
        return len(ids)
    finally:
        conn.close()


def get_products_by_ids(ids):
    if not ids:
        return []
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in ids)
        return conn.execute(
            f"SELECT id, category_id, name, techbuy_link, other_link, shopify_handle FROM products WHERE id IN ({placeholders})",
            ids,
        ).fetchall()
    finally:
        conn.close()


def get_row_updates_for(ids):
    """Latest fetch/reviewed state for the given ids, for the Product List's live-update poll."""
    if not ids:
        return []
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in ids)
        return conn.execute(
            f"""
            SELECT p.id, p.reviewed,
                   fr.techbuy_regular, fr.techbuy_sale, fr.techbuy_stock,
                   fr.other_regular, fr.other_sale, fr.other_stock,
                   fr.need_action, fr.fetched_status, fr.fetched_at
            FROM products p
            LEFT JOIN fetch_results fr ON fr.product_id = p.id
            WHERE p.id IN ({placeholders})
            """,
            ids,
        ).fetchall()
    finally:
        conn.close()


def delete_products(ids):
    if not ids:
        return 0
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in ids)
        conn.execute(f"DELETE FROM product_variants WHERE product_id IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM fetch_results WHERE product_id IN ({placeholders})", ids)
        cur = conn.execute(f"DELETE FROM products WHERE id IN ({placeholders})", ids)
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def reset_reviewed_for(ids):
    if not ids:
        return
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in ids)
        conn.execute(f"UPDATE products SET reviewed = 0 WHERE id IN ({placeholders})", ids)
        conn.commit()
    finally:
        conn.close()


def mark_reviewed_bulk(ids):
    """Sets reviewed=1 for the given ids, skipping any that are locked
    (Need Action = No, already auto-reviewed). Returns (updated, skipped_locked)."""
    if not ids:
        return 0, 0
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"SELECT product_id, need_action FROM fetch_results WHERE product_id IN ({placeholders})",
            ids,
        ).fetchall()
        locked_ids = {r["product_id"] for r in rows if r["need_action"] == "No"}
        updatable = [i for i in ids if i not in locked_ids]
        if updatable:
            up_placeholders = ",".join("?" for _ in updatable)
            conn.execute(f"UPDATE products SET reviewed = 1 WHERE id IN ({up_placeholders})", updatable)
            conn.commit()
        return len(updatable), len(ids) - len(updatable)
    finally:
        conn.close()


def get_export_data_for(ids):
    if not ids:
        return []
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in ids)
        return conn.execute(
            f"""
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
            WHERE p.id IN ({placeholders})
            ORDER BY p.name COLLATE NOCASE
            """,
            ids,
        ).fetchall()
    finally:
        conn.close()


def get_all_products():
    """Used by a full ("Start Fetching", no ids given) run — excludes No Price Sync
    products entirely, since there's nothing to compare for them and no reason to spend
    a request scraping a competitor price that will never be used."""
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT id, category_id, name, techbuy_link, other_link, shopify_handle "
            "FROM products WHERE no_price_sync = 0"
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

def update_other_fetch_result(product_id, data):
    """Updates only the Other-site fields (other_*/need_action/updated/fetched_status) for a
    fetch — Tech Buy's own price/stock is never touched here, since it comes exclusively from
    the Shopify catalog sync (get_product_api_call.py), not this fetch."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO fetch_results
                (product_id, other_regular, other_sale, other_stock,
                 need_action, updated, fetched_status, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(product_id) DO UPDATE SET
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
            # (Need Action already accounts for both price and stock status matching)
            conn.execute("UPDATE products SET reviewed = 1 WHERE id = ?", (product_id,))

        conn.commit()
    finally:
        conn.close()


def count_fetch_results():
    """Products with an actual Other-site fetch attempt recorded — not just a row in
    fetch_results, since every synced product has one of those regardless (for its Tech
    Buy data). A variant-parent product counts once here (not once per variant) if ANY of
    its variants has been fetched. This is what drives whether Import/Remove Fetched Data
    make sense to show."""
    conn = get_connection()
    try:
        single = conn.execute(
            f"""
            SELECT COUNT(*) AS c FROM products p
            JOIN fetch_results fr ON fr.product_id = p.id
            WHERE {_SINGLE_PRODUCT_FILTER} AND fr.fetched_status IS NOT NULL
            """
        ).fetchone()["c"]
        variant = conn.execute(
            "SELECT COUNT(DISTINCT product_id) AS c FROM product_variants WHERE fetched_status IS NOT NULL"
        ).fetchone()["c"]
        return single + variant
    finally:
        conn.close()


def clear_fetch_results():
    """Clears only the Other-site comparison data (other_*/need_action/updated/fetched_status)
    — for single products (fetch_results) AND every variant of a variant-parent product
    (product_variants), so this actually clears everything instead of leaving variant
    products' Other-site data (and Reviewed state) behind. Tech Buy's own price/stock is
    never wiped here — it comes from the Shopify catalog sync, not this fetch, so "removing
    previous fetched data" should only affect the Other-site side."""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE fetch_results
            SET other_regular = NULL, other_sale = NULL, other_stock = NULL,
                need_action = NULL, updated = NULL, fetched_status = NULL
            """
        )
        # Found-OT rows (shopify_variant_id IS NULL) only exist because of a fetch —
        # they're not real Tech Buy/Shopify variants, so clearing fetched data removes
        # them entirely rather than leaving an empty husk behind.
        conn.execute("DELETE FROM product_variants WHERE shopify_variant_id IS NULL")
        conn.execute(
            """
            UPDATE product_variants
            SET other_regular = NULL, other_sale = NULL, other_stock = NULL,
                need_action = NULL, updated = NULL, fetched_status = NULL,
                match_status = NULL, match_note = NULL
            """
        )
        conn.execute("UPDATE products SET reviewed = 0")
        conn.execute("UPDATE product_variants SET reviewed = 0")
        conn.commit()
    finally:
        conn.close()


def reset_all_reviewed():
    conn = get_connection()
    try:
        conn.execute("UPDATE products SET reviewed = 0")
        conn.execute("UPDATE product_variants SET reviewed = 0")
        conn.commit()
    finally:
        conn.close()


# ---------- variant-parent fetch / bulk actions ----------

def get_variants_for_product(product_id):
    """Just the fields a re-fetch needs — id (to write results back per row), each
    variant's own Tech Buy price/stock, and variant_path (to match against the other
    site's variant options). Only real Tech Buy variants (shopify_variant_id IS NOT
    NULL) — excludes any Found-OT rows from a previous fetch, since those aren't real
    Tech Buy variants and shouldn't be fed back in as if they were."""
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT id, variant_path, techbuy_regular, techbuy_sale, techbuy_stock "
            "FROM product_variants WHERE product_id = ? AND shopify_variant_id IS NOT NULL ORDER BY sort_order",
            (product_id,),
        ).fetchall()
    finally:
        conn.close()


def update_variant_other_fetch_result(variant_id, data):
    """Per-variant equivalent of update_other_fetch_result — Other-site fields only,
    Tech Buy's own price/stock (synced separately) is never touched here. match_status/
    match_note (from app.scraping.variant_match) record how confidently this variant was
    paired with the other site's data — other_regular/other_sale/other_stock/need_action
    should only ever be set here when match_status is "exact"; anything else means there
    was no safe data to write, just a note explaining why."""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE product_variants
            SET other_regular = ?, other_sale = ?, other_stock = ?,
                need_action = ?, updated = ?, fetched_status = ?,
                match_status = ?, match_note = ?
            WHERE id = ?
            """,
            (
                data.get("other_regular"),
                data.get("other_sale"),
                data.get("other_stock"),
                data.get("need_action"),
                data.get("updated"),
                data.get("fetched_status"),
                data.get("match_status"),
                data.get("match_note"),
                variant_id,
            ),
        )
        if data.get("need_action") == "No":
            conn.execute("UPDATE product_variants SET reviewed = 1 WHERE id = ?", (variant_id,))
        conn.commit()
    finally:
        conn.close()


def sync_found_ot_variants(product_id, found_ot_variants):
    """A "Found-OT" row is a variant that exists on the Other site but not on Tech Buy
    at all — a real product_variants row (so it gets a real, persisted Reviewed checkbox
    like everything else), just with no shopify_variant_id, since it isn't a real Tech
    Buy/Shopify variant. Matched across re-fetches by variant_path instead (its "name" is
    the only stable identity it has), so a manually-set Reviewed survives. Any row that's
    no longer found on the other site gets removed. found_ot_variants is
    app.scraping.variant_match's found_ot_variants list: [{"labels", "regular", "sale",
    "stock"}, ...] — pass an empty list to clear everything for this product."""
    conn = get_connection()
    try:
        existing = {
            r["variant_path"]: r["id"]
            for r in conn.execute(
                "SELECT id, variant_path FROM product_variants WHERE product_id = ? AND shopify_variant_id IS NULL",
                (product_id,),
            ).fetchall()
        }

        seen_paths = set()
        for v in found_ot_variants:
            path = " > ".join(v["labels"])
            seen_paths.add(path)
            if path in existing:
                conn.execute(
                    """
                    UPDATE product_variants
                    SET other_regular = ?, other_sale = ?, other_stock = ?,
                        need_action = 'Yes', fetched_status = 'Fetched', match_status = 'found_ot'
                    WHERE id = ?
                    """,
                    (v["regular"], v["sale"], v["stock"], existing[path]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO product_variants
                        (product_id, shopify_variant_id, variant_path, other_regular, other_sale, other_stock,
                         need_action, fetched_status, match_status, sort_order)
                    VALUES (?, NULL, ?, ?, ?, ?, 'Yes', 'Fetched', 'found_ot', 9999)
                    """,
                    (product_id, path, v["regular"], v["sale"], v["stock"]),
                )

        for path, row_id in existing.items():
            if path not in seen_paths:
                conn.execute("DELETE FROM product_variants WHERE id = ?", (row_id,))

        conn.commit()
    finally:
        conn.close()


def reset_variant_reviewed_for(product_ids):
    """Resets Reviewed on every variant under the given parent product ids — called
    before a re-fetch, since fresh comparison data may change whether a variant still
    needs review."""
    if not product_ids:
        return
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in product_ids)
        conn.execute(
            f"UPDATE product_variants SET reviewed = 0 WHERE product_id IN ({placeholders})",
            product_ids,
        )
        conn.commit()
    finally:
        conn.close()


def mark_variant_reviewed_bulk(product_ids):
    """Sets reviewed=1 for every variant under the given parent product ids, skipping
    any variant that's locked (Need Action = No — already auto-reviewed, just not
    writable). Returns (updated_variant_count, skipped_locked_count). Since a product's
    aggregate Reviewed is true once every one of its variants is reviewed (locked ones
    already count), this always reviews everything it can per selected product."""
    if not product_ids:
        return 0, 0
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in product_ids)
        rows = conn.execute(
            f"SELECT id, need_action FROM product_variants WHERE product_id IN ({placeholders})",
            product_ids,
        ).fetchall()
        locked_ids = {r["id"] for r in rows if r["need_action"] == "No"}
        updatable = [r["id"] for r in rows if r["id"] not in locked_ids]
        if updatable:
            up_placeholders = ",".join("?" for _ in updatable)
            conn.execute(f"UPDATE product_variants SET reviewed = 1 WHERE id IN ({up_placeholders})", updatable)
            conn.commit()
        return len(updatable), len(locked_ids)
    finally:
        conn.close()


# ---------- shopify catalog sync (get_product_api_call.py) ----------

def get_category_id_by_name(name):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM categories WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def get_or_create_category_id(name):
    category_id = get_category_id_by_name(name)
    if category_id is not None:
        return category_id
    add_category(name)
    return get_category_id_by_name(name)


def _upsert_product_shell(shopify_handle, category_id, name, techbuy_link, shopify_status, variant_issue):
    """Shared by both single- and variant-product upserts: matched by handle alone (a
    product's canonical row never needs to split across the two product tables), preserving
    other_link/reviewed. Returns (product_id, created)."""
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM products WHERE shopify_handle = ?", (shopify_handle,)
        ).fetchone()
        if existing:
            product_id = existing["id"]
            conn.execute(
                """
                UPDATE products
                SET name = ?, category_id = ?, techbuy_link = ?, variant_issue = ?,
                    shopify_status = ?, shopify_removed = 0
                WHERE id = ?
                """,
                (name, category_id, techbuy_link, variant_issue, shopify_status, product_id),
            )
            created = False
        else:
            cur = conn.execute(
                """
                INSERT INTO products
                    (category_id, name, techbuy_link, other_link, reviewed,
                     shopify_handle, shopify_status, shopify_removed, variant_issue)
                VALUES (?, ?, ?, '', 0, ?, ?, 0, ?)
                """,
                (category_id, name, techbuy_link, shopify_handle, shopify_status, variant_issue),
            )
            product_id = cur.lastrowid
            created = True
        conn.commit()
        return product_id, created
    finally:
        conn.close()


def upsert_single_product(shopify_handle, category_id, name, techbuy_link,
                           techbuy_regular, techbuy_sale, techbuy_stock, shopify_status, variant_issue=None):
    """For products with 0-1 real Shopify variants — lives on the Product List page."""
    product_id, created = _upsert_product_shell(
        shopify_handle, category_id, name, techbuy_link, shopify_status, variant_issue
    )
    conn = get_connection()
    try:
        # if this handle used to be multi-variant and has since dropped to one real
        # variant, it's no longer a variant-parent — clear any leftover children
        conn.execute("DELETE FROM product_variants WHERE product_id = ?", (product_id,))
        conn.execute(
            """
            INSERT INTO fetch_results (product_id, techbuy_regular, techbuy_sale, techbuy_stock, fetched_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(product_id) DO UPDATE SET
                techbuy_regular=excluded.techbuy_regular,
                techbuy_sale=excluded.techbuy_sale,
                techbuy_stock=excluded.techbuy_stock,
                fetched_at=excluded.fetched_at
            """,
            (product_id, techbuy_regular, techbuy_sale, techbuy_stock),
        )
        conn.commit()
        return product_id, created
    finally:
        conn.close()


def upsert_variant_product(shopify_handle, category_id, name, techbuy_link, shopify_status,
                            variant_issue, variants):
    """For products with 2+ real Shopify variants — lives on the Variant Products page, one
    parent row here plus its full variant breakdown in product_variants. Each variant is
    matched by shopify_variant_id (like the parent product is matched by handle), so its
    Reviewed status and Other-site comparison data survive a re-sync — only the Tech Buy
    name/price/stock get refreshed. A variant no longer present on Shopify is removed; a
    genuinely new one is inserted fresh. Each `variants` entry needs: shopify_variant_id,
    variant_path, regular, sale, stock."""
    product_id, created = _upsert_product_shell(
        shopify_handle, category_id, name, techbuy_link, shopify_status, variant_issue
    )
    conn = get_connection()
    try:
        # shopify_variant_id IS NOT NULL excludes Found-OT rows (a variant that exists on
        # the Other site but not on Tech Buy) — those aren't real Shopify variants and
        # must never be touched by this sync, or they'd get wrongly deleted as "no longer
        # on Shopify" the moment they don't show up in `variants` below (they never will).
        existing = {
            r["shopify_variant_id"]: r["id"] for r in conn.execute(
                "SELECT id, shopify_variant_id FROM product_variants WHERE product_id = ? AND shopify_variant_id IS NOT NULL",
                (product_id,),
            ).fetchall()
        }

        seen_variant_ids = set()
        for i, v in enumerate(variants):
            vid = v["shopify_variant_id"]
            seen_variant_ids.add(vid)
            if vid in existing:
                conn.execute(
                    """
                    UPDATE product_variants
                    SET variant_path = ?, techbuy_regular = ?, techbuy_sale = ?, techbuy_stock = ?, sort_order = ?
                    WHERE id = ?
                    """,
                    (v["variant_path"], v["regular"], v["sale"], v["stock"], i, existing[vid]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO product_variants
                        (product_id, shopify_variant_id, variant_path, techbuy_regular, techbuy_sale, techbuy_stock, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (product_id, vid, v["variant_path"], v["regular"], v["sale"], v["stock"], i),
                )

        # a variant no longer on Shopify at all (not just out of stock — genuinely gone)
        for vid, row_id in existing.items():
            if vid not in seen_variant_ids:
                conn.execute("DELETE FROM product_variants WHERE id = ?", (row_id,))

        # no single top-level price makes sense for a variant-parent row — real prices
        # live in product_variants instead — just keep fetched_at current
        conn.execute(
            """
            INSERT INTO fetch_results (product_id, fetched_at)
            VALUES (?, datetime('now'))
            ON CONFLICT(product_id) DO UPDATE SET fetched_at=excluded.fetched_at
            """,
            (product_id,),
        )
        conn.commit()
        return product_id, created
    finally:
        conn.close()


VARIANT_PRODUCT_SORT_COLUMNS = {
    "name": "p.name COLLATE NOCASE",
    "category": "c.name COLLATE NOCASE, p.name COLLATE NOCASE",
}


VARIANT_FILTERABLE_COLUMNS = {"need_action", "reviewed", "shopify_status", "fetched_status", "other_link"}


def get_variant_filter_options():
    """The Variant Products page only filters on the aggregate columns computed across
    each product's variants (real per-variant values like stock/prices aren't meaningful
    to filter on at the parent-row level), plus the product-level Shopify Status and
    Other Link. Every option offered is checked against what the data actually contains —
    e.g. if no variant-parent product currently has a Fetch Problem, that choice simply
    doesn't appear."""
    conn = get_connection()
    try:
        agg_rows = conn.execute(f"SELECT need_action, reviewed, fetched_status FROM ({_VARIANT_PRODUCT_AGG}) agg").fetchall()

        need_action_values = []
        if any(r["need_action"] == "Yes" for r in agg_rows):
            need_action_values.append("Yes")
        if any(r["need_action"] == "No" for r in agg_rows):
            need_action_values.append("No")
        need_action_null = any(r["need_action"] is None for r in agg_rows)

        reviewed_values = []
        if any(r["reviewed"] == 1 for r in agg_rows):
            reviewed_values.append("Yes")
        if any(r["reviewed"] == 0 for r in agg_rows):
            reviewed_values.append("No")

        fetched_status_values = []
        if any(r["fetched_status"] == "Fetched" for r in agg_rows):
            fetched_status_values.append("Fetched")
        if any(r["fetched_status"] == "Fetch Problem" for r in agg_rows):
            fetched_status_values.append("Fetch Problem")
        fetched_status_null = any(r["fetched_status"] is None for r in agg_rows)

        variant_parent_filter = "WHERE EXISTS (SELECT 1 FROM product_variants pv WHERE pv.product_id = p.id)"

        status_rows = conn.execute(
            f"SELECT DISTINCT p.shopify_removed AS removed, p.shopify_status AS status FROM products p {variant_parent_filter}"
        ).fetchall()
        shopify_status_values = []
        if any(r["removed"] == 1 for r in status_rows):
            shopify_status_values.append("Removed")
        if any(r["removed"] == 0 and r["status"] == "ACTIVE" for r in status_rows):
            shopify_status_values.append("Active")
        if any(r["removed"] == 0 and r["status"] == "DRAFT" for r in status_rows):
            shopify_status_values.append("Draft")

        link_rows = conn.execute(
            f"SELECT DISTINCT (p.other_link != '') AS has_link FROM products p {variant_parent_filter}"
        ).fetchall()
        other_link_values = []
        if any(r["has_link"] == 1 for r in link_rows):
            other_link_values.append("Has Link")
        if any(r["has_link"] == 0 for r in link_rows):
            other_link_values.append("No Link")

        return {
            "need_action": {"values": need_action_values, "has_null": need_action_null},
            "reviewed": {"values": reviewed_values, "has_null": False},
            "shopify_status": {"values": shopify_status_values, "has_null": False},
            "fetched_status": {"values": fetched_status_values, "has_null": fetched_status_null},
            "other_link": {"values": other_link_values, "has_null": False},
        }
    finally:
        conn.close()


def _build_variant_filter_clauses(filters):
    clauses = []
    params = []
    for key, values in (filters or {}).items():
        if not values or key not in VARIANT_FILTERABLE_COLUMNS:
            continue

        if key == "need_action":
            include_null = NULL_FILTER_VALUE in values
            real_values = [v for v in values if v in ("Yes", "No")]
            sub = []
            if real_values:
                placeholders = ",".join("?" for _ in real_values)
                sub.append(f"agg.need_action IN ({placeholders})")
                params.extend(real_values)
            if include_null:
                sub.append("agg.need_action IS NULL")
            if sub:
                clauses.append("(" + " OR ".join(sub) + ")")
        elif key == "reviewed":
            mapped = [1 if v == "Yes" else 0 for v in values if v in ("Yes", "No")]
            if mapped:
                placeholders = ",".join("?" for _ in mapped)
                clauses.append(f"agg.reviewed IN ({placeholders})")
                params.extend(mapped)
        elif key == "shopify_status":
            sub = []
            if "Removed" in values:
                sub.append("p.shopify_removed = 1")
            if "Active" in values:
                sub.append("(p.shopify_removed = 0 AND p.shopify_status = 'ACTIVE')")
            if "Draft" in values:
                sub.append("(p.shopify_removed = 0 AND p.shopify_status = 'DRAFT')")
            if sub:
                clauses.append("(" + " OR ".join(sub) + ")")
        elif key == "fetched_status":
            include_null = NULL_FILTER_VALUE in values
            real_values = [v for v in values if v in ("Fetched", "Fetch Problem")]
            sub = []
            if real_values:
                placeholders = ",".join("?" for _ in real_values)
                sub.append(f"agg.fetched_status IN ({placeholders})")
                params.extend(real_values)
            if include_null:
                sub.append("agg.fetched_status IS NULL")
            if sub:
                clauses.append("(" + " OR ".join(sub) + ")")
        elif key == "other_link":
            sub = []
            if "Has Link" in values:
                sub.append("p.other_link != ''")
            if "No Link" in values:
                sub.append("p.other_link = ''")
            if sub:
                clauses.append("(" + " OR ".join(sub) + ")")
    return clauses, params


MATCH_TABS = ["exact_match", "variant_not_found", "missing_from_techbuy"]
MATCH_TAB_LABELS = {
    "exact_match": "Exact Match",
    "variant_not_found": "Variant Not Found",
    "missing_from_techbuy": "Missing from Tech Buy",
}

# Product-level tab, evaluated as a strict waterfall (checked in order, first match wins
# — a product only ever lands in exactly one of these, see app.scraping.variant_match):
#   1. Every variant is 'found' or 'found_tb' -> exact_match. Checked first, and if true
#      the product never lands anywhere else.
#   2. (only reachable if not #1) any variant is 'not_found' -> variant_not_found.
#   3. (only reachable if not #1/#2) any variant is 'found_ot' -> missing_from_techbuy.
#   Anything else (nothing fetched yet, or a genuinely unhandled mix) -> NULL.
_MATCH_STATUS_CASE = """
    CASE WHEN clean_count = variant_count AND variant_count > 0 THEN 'exact_match'
         WHEN not_found_count > 0 THEN 'variant_not_found'
         WHEN found_ot_count > 0 THEN 'missing_from_techbuy'
         ELSE NULL END
"""


def list_variant_parent_products(page=1, page_size=20, query="", category="", sort="name", direction="asc", filters=None, match_tab=None):
    """One row per variant-parent product (2+ real Shopify variants). Need Action,
    Reviewed, and Match Status are all aggregated across that product's product_variants
    children (computed once in the `agg` CTE so both the WHERE filter and the displayed
    value use the exact same logic): Need Action is "Yes" if any variant needs action,
    "No" only if every variant is "No", otherwise blank (still missing other-site data);
    Reviewed is true only once every variant is individually reviewed (this includes any
    Found-OT rows, which are real product_variants rows too); Match Status is the
    product's tab per the waterfall in _MATCH_STATUS_CASE. Per-variant detail is fetched
    separately via get_variants_for_products, keyed by product id, for the nested
    sub-table."""
    sort_col = VARIANT_PRODUCT_SORT_COLUMNS.get(sort, VARIANT_PRODUCT_SORT_COLUMNS["name"])
    direction = "DESC" if direction.lower() == "desc" else "ASC"

    clauses = ["p.no_price_sync = 0"]
    params = []
    if query:
        clauses.append("p.name LIKE ?")
        params.append(f"%{query}%")
    if category:
        clauses.append("c.name = ?")
        params.append(category)
    if match_tab in MATCH_TABS:
        clauses.append("agg.match_status = ?")
        params.append(match_tab)

    filter_clauses, filter_params = _build_variant_filter_clauses(filters)
    clauses.extend(filter_clauses)
    params.extend(filter_params)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    cte = """
        WITH agg AS (
            SELECT product_id,
                   COUNT(*) AS variant_count,
                   SUM(CASE WHEN need_action = 'Yes' THEN 1 ELSE 0 END) AS need_yes,
                   SUM(CASE WHEN need_action = 'No' THEN 1 ELSE 0 END) AS need_no,
                   SUM(CASE WHEN reviewed = 1 THEN 1 ELSE 0 END) AS reviewed_yes,
                   SUM(CASE WHEN fetched_status = 'Fetch Problem' THEN 1 ELSE 0 END) AS fetch_problem,
                   SUM(CASE WHEN fetched_status = 'Fetched' THEN 1 ELSE 0 END) AS fetched_yes,
                   SUM(CASE WHEN match_status IN ('found', 'found_tb') THEN 1 ELSE 0 END) AS clean_count,
                   SUM(CASE WHEN match_status = 'not_found' THEN 1 ELSE 0 END) AS not_found_count,
                   SUM(CASE WHEN match_status = 'found_ot' THEN 1 ELSE 0 END) AS found_ot_count
            FROM product_variants
            GROUP BY product_id
        )
    """
    agg_select = f"""
        SELECT product_id, variant_count,
               CASE WHEN need_yes > 0 THEN 'Yes'
                    WHEN need_no = variant_count THEN 'No'
                    ELSE NULL END AS need_action,
               CASE WHEN reviewed_yes = variant_count THEN 1 ELSE 0 END AS reviewed,
               CASE WHEN fetch_problem > 0 THEN 'Fetch Problem'
                    WHEN fetched_yes = variant_count THEN 'Fetched'
                    ELSE NULL END AS fetched_status,
               {_MATCH_STATUS_CASE} AS match_status
        FROM agg
    """

    conn = get_connection()
    try:
        total = conn.execute(
            f"""
            {cte}
            SELECT COUNT(*) AS c
            FROM products p
            JOIN categories c ON c.id = p.category_id
            JOIN ({agg_select}) agg ON agg.product_id = p.id
            {where}
            """,
            params,
        ).fetchone()["c"]

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"""
            {cte}
            SELECT p.id, p.name, c.name AS category, p.techbuy_link, p.other_link,
                   p.shopify_status, p.shopify_removed, p.variant_issue,
                   agg.variant_count, agg.need_action, agg.reviewed, agg.fetched_status,
                   agg.match_status
            FROM products p
            JOIN categories c ON c.id = p.category_id
            JOIN ({agg_select}) agg ON agg.product_id = p.id
            {where}
            ORDER BY {sort_col} {direction}
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        ).fetchall()

        results = []
        for r in rows:
            row = dict(r)
            row["reviewed"] = bool(row["reviewed"])
            results.append(row)
        return results, total
    finally:
        conn.close()


def count_all_variant_parent_products():
    """True grand total across every variant-parent product, regardless of Match Status
    tab — the 3 tabs aren't guaranteed to sum to this (e.g. nothing's been fetched yet
    for some products), so the "All" tab needs its own count."""
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT COUNT(*) AS c FROM products p "
            "WHERE p.no_price_sync = 0 AND EXISTS (SELECT 1 FROM product_variants pv WHERE pv.product_id = p.id)"
        ).fetchone()["c"]
    finally:
        conn.close()


def count_variant_match_tabs():
    """Product counts per Match Status tab, for the tab bar on the Variant Products
    page — always agrees with list_variant_parent_products's match_tab filter since
    both use the exact same aggregation CTE/CASE."""
    conn = get_connection()
    try:
        rows = conn.execute(
            f"""
            WITH agg AS (
                SELECT pv.product_id,
                       COUNT(*) AS variant_count,
                       SUM(CASE WHEN pv.match_status IN ('found', 'found_tb') THEN 1 ELSE 0 END) AS clean_count,
                       SUM(CASE WHEN pv.match_status = 'not_found' THEN 1 ELSE 0 END) AS not_found_count,
                       SUM(CASE WHEN pv.match_status = 'found_ot' THEN 1 ELSE 0 END) AS found_ot_count
                FROM product_variants pv
                JOIN products p ON p.id = pv.product_id
                WHERE p.no_price_sync = 0
                GROUP BY pv.product_id
            )
            SELECT {_MATCH_STATUS_CASE} AS match_status, COUNT(*) AS c
            FROM agg
            GROUP BY match_status
            """
        ).fetchall()
        counts = {r["match_status"]: r["c"] for r in rows}
        return {tab: counts.get(tab, 0) for tab in MATCH_TABS}
    finally:
        conn.close()


def get_variants_for_products(product_ids):
    """Per-variant detail rows for the given parent product ids, grouped by product_id,
    for the nested sub-table on the Variant Products page."""
    if not product_ids:
        return {}
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in product_ids)
        rows = conn.execute(
            f"""
            SELECT id, product_id, variant_path,
                   techbuy_regular, techbuy_sale, techbuy_stock,
                   other_regular, other_sale, other_stock,
                   need_action, fetched_status, reviewed,
                   match_status, match_note
            FROM product_variants
            WHERE product_id IN ({placeholders})
            ORDER BY product_id, sort_order
            """,
            product_ids,
        ).fetchall()
        grouped = {}
        for r in rows:
            grouped.setdefault(r["product_id"], []).append(r)
        return grouped
    finally:
        conn.close()


def is_variant_reviewed_locked(variant_id):
    """Mirrors is_reviewed_locked, but per variant row instead of per product."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT need_action FROM product_variants WHERE id = ?", (variant_id,)
        ).fetchone()
        return row is not None and row["need_action"] == "No"
    finally:
        conn.close()


def toggle_variant_reviewed(variant_id, reviewed):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE product_variants SET reviewed = ? WHERE id = ?",
            (1 if reviewed else 0, variant_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_fetch_result(product_id):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM fetch_results WHERE product_id = ?", (product_id,)
        ).fetchone()
    finally:
        conn.close()


def mark_shopify_removed(current_handles):
    """Flags products previously synced from Shopify (shopify_handle set) whose handle
    isn't in the latest pull anymore, and un-flags any that reappeared. Returns count flagged."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, shopify_handle FROM products WHERE shopify_handle IS NOT NULL"
        ).fetchall()
        flagged = 0
        for row in rows:
            removed = 1 if row["shopify_handle"] not in current_handles else 0
            if removed:
                flagged += 1
            conn.execute("UPDATE products SET shopify_removed = ? WHERE id = ?", (removed, row["id"]))
        conn.commit()
        return flagged
    finally:
        conn.close()


# ---------- sync tracking page ----------

TRACKING_SORT_COLUMNS = {
    "name": "p.name COLLATE NOCASE",
    "category": "c.name COLLATE NOCASE",
    "techbuy_stock": "fr.techbuy_stock COLLATE NOCASE",
}

TRACKING_FILTERABLE_COLUMNS = {"techbuy_stock"}


def get_sync_tracking_filter_options():
    """The only column across all three Sync Tracking tabs whose values are a small,
    meaningful categorical set — Category already has its own top dropdown, and each
    tab's last column (Other Link/Shopify Status/Variant Issue) is either constant for
    that tab or free text, neither of which is worth a checkbox filter."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT fr.techbuy_stock AS v FROM products p LEFT JOIN fetch_results fr ON fr.product_id = p.id"
        ).fetchall()
        values = [r["v"] for r in rows if r["v"] is not None]
        has_null = any(r["v"] is None for r in rows)
        return {"techbuy_stock": {"values": values, "has_null": has_null}}
    finally:
        conn.close()


def _build_tracking_filter_clauses(filters):
    clauses = []
    params = []
    for key, values in (filters or {}).items():
        if not values or key not in TRACKING_FILTERABLE_COLUMNS:
            continue
        include_null = NULL_FILTER_VALUE in values
        real_values = [v for v in values if v != NULL_FILTER_VALUE]
        sub = []
        if real_values:
            placeholders = ",".join("?" for _ in real_values)
            sub.append(f"fr.techbuy_stock IN ({placeholders})")
            params.extend(real_values)
        if include_null:
            sub.append("fr.techbuy_stock IS NULL")
        if sub:
            clauses.append("(" + " OR ".join(sub) + ")")
    return clauses, params


def _paginated_tracking_query(where_clause, page, page_size, query="", category="", sort="name", direction="asc", filters=None):
    sort_col = TRACKING_SORT_COLUMNS.get(sort, TRACKING_SORT_COLUMNS["name"])
    direction = "DESC" if direction.lower() == "desc" else "ASC"

    clauses = [where_clause]
    params = []
    if query:
        clauses.append("p.name LIKE ?")
        params.append(f"%{query}%")
    if category:
        clauses.append("c.name = ?")
        params.append(category)

    filter_clauses, filter_params = _build_tracking_filter_clauses(filters)
    clauses.extend(filter_clauses)
    params.extend(filter_params)

    where = " AND ".join(clauses)

    conn = get_connection()
    try:
        offset = (page - 1) * page_size
        total = conn.execute(
            f"""
            SELECT COUNT(*) AS c
            FROM products p
            JOIN categories c ON c.id = p.category_id
            LEFT JOIN fetch_results fr ON fr.product_id = p.id
            WHERE {where}
            """,
            params,
        ).fetchone()["c"]

        rows = conn.execute(
            f"""
            SELECT p.id, p.name, c.name AS category, p.techbuy_link, p.other_link,
                   p.shopify_handle, p.shopify_removed, p.variant_issue,
                   fr.techbuy_regular, fr.techbuy_sale, fr.techbuy_stock
            FROM products p
            JOIN categories c ON c.id = p.category_id
            LEFT JOIN fetch_results fr ON fr.product_id = p.id
            WHERE {where}
            ORDER BY {sort_col} {direction}
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        ).fetchall()
        return rows, total
    finally:
        conn.close()


def count_missing_other_link():
    """Excludes No Price Sync products — a blank other_link there is intentional (we set
    our own price for those), not a follow-up item worth surfacing."""
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT COUNT(*) c FROM products WHERE other_link = '' AND no_price_sync = 0"
        ).fetchone()["c"]
    finally:
        conn.close()


def get_products_missing_other_link(page=1, page_size=50, query="", category="", sort="name", direction="asc", filters=None):
    return _paginated_tracking_query(
        "p.other_link = '' AND p.no_price_sync = 0", page, page_size, query, category, sort, direction, filters
    )


def count_removed_from_shopify():
    """Only products actively being tracked against an Other-site link matter here —
    ones with no other_link were never being compared to anything, so their removal
    from Shopify isn't a follow-up item worth surfacing."""
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT COUNT(*) c FROM products WHERE shopify_removed = 1 AND other_link != ''"
        ).fetchone()["c"]
    finally:
        conn.close()


def get_products_removed_from_shopify(page=1, page_size=50, query="", category="", sort="name", direction="asc", filters=None):
    # Once removed, the Shopify sync no longer touches this product's row at all — its
    # techbuy_link/fetch_results data is simply whatever was last synced before removal,
    # preserved as-is (never cleared), so this tab naturally shows the "previous" data.
    return _paginated_tracking_query(
        "p.shopify_removed = 1 AND p.other_link != ''", page, page_size, query, category, sort, direction, filters
    )


def count_variant_issues():
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) c FROM products WHERE variant_issue IS NOT NULL").fetchone()["c"]
    finally:
        conn.close()


def get_products_with_variant_issues(page=1, page_size=50, query="", category="", sort="name", direction="asc", filters=None):
    return _paginated_tracking_query(
        "p.variant_issue IS NOT NULL", page, page_size, query, category, sort, direction, filters
    )


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
