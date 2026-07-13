"""
Bulk product import from an uploaded .xlsx file.

Expected format: row 1 is headers, columns in this exact order:
    Category | Product Name | Tech Buy Link | Other website link

Each data row is validated and inserted independently — a bad row (missing
field, duplicate name/link) is skipped and reported, while every other valid
row in the same file still gets imported. A category that doesn't exist yet
is created automatically (once per distinct new name) rather than rejected.
"""

import openpyxl

from app import models


def _cell_text(value):
    return str(value).strip() if value is not None else ""


def parse_and_import(file_stream):
    """Returns (imported_count, failed_rows, new_categories)."""
    wb = openpyxl.load_workbook(file_stream, data_only=True)
    ws = wb.active

    categories_by_name = {c["name"].strip().lower(): c["id"] for c in models.list_categories()}
    new_categories = []

    imported = 0
    failed_rows = []

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

        if not category or not name or not techbuy_link or not other_link:
            reason = "Missing required field(s)."
        else:
            category_id = categories_by_name.get(category.lower())
            if category_id is None:
                ok, cat_error = models.add_category(category)
                if ok:
                    fresh = models.list_categories()
                    categories_by_name = {c["name"].strip().lower(): c["id"] for c in fresh}
                    category_id = categories_by_name.get(category.lower())
                    new_categories.append(category)
                else:
                    reason = cat_error

            if reason is None:
                ok, error = models.add_product(category_id, name, techbuy_link, other_link)
                if not ok:
                    reason = error

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
            imported += 1

    return imported, failed_rows, new_categories
