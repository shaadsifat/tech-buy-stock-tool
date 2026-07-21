"""
Bulk Other-site link upload from an uploaded .xlsx file.

Expected format: row 1 is headers, columns in this exact order:
    Category | Product Name | Tech Buy Link | Other website link

Products themselves only ever get created by the Shopify catalog sync
(get_product_api_call.py) now — this bulk upload can no longer add brand-new products,
only attach/update the Other-site link on a product that already exists. Matching is by
Shopify Handle, not Product Name (not guaranteed unique/stable) — the handle is pulled
straight out of the Tech Buy Link column (a Tech Buy Link always looks like
".../products/<handle>"), case-insensitively, so Category/Product Name are only ever
used for display in the failure report, never for matching.

Each row is validated and applied independently:
  - Missing Category/Product Name/Tech Buy Link/Other website link -> skipped, reported
    as missing.
  - Tech Buy Link doesn't look like a real product link (no handle to extract) -> skipped,
    reported as not matched.
  - The extracted handle isn't found in the database -> skipped, reported as a new
    product (bulk upload can't create it — it has to come from the Shopify sync first).
  - The same handle appears more than once in the file -> skipped, reported as duplicate.
"""

from urllib.parse import urlparse

import openpyxl

from app import models


def _cell_text(value):
    return str(value).strip() if value is not None else ""


def _extract_handle(techbuy_link):
    """A Tech Buy Link is https://<domain>/products/<handle> — pull the handle back out.
    Returns None if the link doesn't look like a real product link at all."""
    path = urlparse(techbuy_link).path.strip("/")
    if not path:
        return None
    segments = path.split("/")
    if "products" in segments:
        idx = segments.index("products")
        if idx + 1 < len(segments) and segments[idx + 1]:
            return segments[idx + 1]
        return None
    return segments[-1] or None


def parse_and_import(file_stream):
    """Returns (updated_count, failed_rows)."""
    wb = openpyxl.load_workbook(file_stream, data_only=True)
    ws = wb.active

    updated = 0
    failed_rows = []
    seen_handles = set()

    row_num = 1
    for raw_row in ws.iter_rows(min_row=2, values_only=True):
        row_num += 1
        values = (list(raw_row) + [None, None, None, None])[:4]
        category_raw, name_raw, techbuy_raw, other_raw = values

        category = _cell_text(category_raw)
        name = _cell_text(name_raw)
        techbuy_link = _cell_text(techbuy_raw)
        other_link = _cell_text(other_raw)

        if not any([category, name, techbuy_link, other_link]):
            continue  # fully blank row — ignore silently

        reason = None
        handle = None

        if not category or not name or not techbuy_link or not other_link:
            reason = "Missing required field(s)."
        else:
            handle = _extract_handle(techbuy_link)
            if not handle:
                reason = "Link not matched — couldn't read a product handle from this Tech Buy Link."
            else:
                handle_key = handle.lower()
                if handle_key in seen_handles:
                    reason = "Duplicate — this handle already appeared earlier in this file."
                else:
                    product = models.get_product_by_handle(handle)
                    if product is None:
                        reason = "New product — handle not found in the database. Products can only be added via the Shopify sync, not bulk upload."

        if reason:
            failed_rows.append({
                "row": row_num,
                "category": category,
                "name": name,
                "techbuy_link": techbuy_link,
                "other_link": other_link,
                "reason": reason,
            })
        else:
            seen_handles.add(handle.lower())
            models.set_other_link(product["id"], other_link)
            updated += 1

    return updated, failed_rows
