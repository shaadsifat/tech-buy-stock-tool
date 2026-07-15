import json

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file

from app import models
from app import import_products
from app.config import PAGE_SIZE_CHOICES, DEFAULT_PAGE_SIZE
from app.export import products_export
from app.export.excel_export import build_workbook, build_filename
from app.scraping import registry
from app.scraping import runner

products_bp = Blueprint("products", __name__)


def _parse_ids(values):
    ids = []
    for v in values:
        try:
            ids.append(int(v))
        except (TypeError, ValueError):
            continue
    return ids


def _enrich_with_site_name(products):
    enriched = []
    for p in products:
        row = dict(p)
        row["other_site"] = registry.get_site_display_name(registry.domain_of(row["other_link"]))
        enriched.append(row)
    return enriched


def _parse_filters(raw):
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    filters = {}
    for key, values in parsed.items():
        if key in models.ALL_FILTER_KEYS and isinstance(values, list) and values:
            filters[key] = [str(v) for v in values]
    return filters


@products_bp.route("/products/new", methods=["GET"])
def new_product():
    categories = models.list_categories()
    return render_template("input_product.html", categories=categories)


@products_bp.route("/products/new", methods=["POST"])
def create_product():
    category_id = request.form.get("category_id")
    name = request.form.get("name", "")
    techbuy_link = request.form.get("techbuy_link", "")
    other_link = request.form.get("other_link", "")

    ok, error = models.add_product(category_id, name, techbuy_link, other_link)
    if ok:
        flash(f'Product "{name.strip()}" added.', "success")
        return redirect(url_for("products.new_product"))
    else:
        flash(error, "error")
        return redirect(url_for("products.new_product"))


@products_bp.route("/products/bulk-upload", methods=["POST"])
def bulk_upload():
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Please choose an Excel file to upload.", "error")
        return redirect(url_for("products.new_product"))

    if not file.filename.lower().endswith(".xlsx"):
        flash("Please upload a .xlsx Excel file.", "error")
        return redirect(url_for("products.new_product"))

    try:
        imported, failed_rows, new_categories = import_products.parse_and_import(file.stream)
    except Exception:
        flash("Could not read that file — make sure it's a valid .xlsx Excel file.", "error")
        return redirect(url_for("products.new_product"))

    categories = models.list_categories()
    return render_template(
        "input_product.html",
        categories=categories,
        bulk_result={"imported": imported, "failed_rows": failed_rows, "new_categories": new_categories},
    )


@products_bp.route("/products/export-template", methods=["GET"])
def export_products_template():
    buffer = products_export.build_workbook()
    return send_file(
        buffer,
        as_attachment=True,
        download_name=products_export.build_filename(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@products_bp.route("/products", methods=["GET"])
def list_products_view():
    query = request.args.get("q", "").strip()
    sort = request.args.get("sort", "name")
    direction = request.args.get("dir", "asc")
    page = max(1, request.args.get("page", 1, type=int))
    page_size = request.args.get("size", DEFAULT_PAGE_SIZE, type=int)
    if page_size not in PAGE_SIZE_CHOICES:
        page_size = DEFAULT_PAGE_SIZE

    filters_raw = request.args.get("filters", "")
    filters = _parse_filters(filters_raw)
    filters_json = json.dumps(filters) if filters else ""

    products, total = models.list_products(
        query=query, sort=sort, direction=direction, page=page, page_size=page_size, filters=filters
    )
    products = _enrich_with_site_name(products)

    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)

    other_dir = "desc" if direction == "asc" else "asc"

    return render_template(
        "product_list.html",
        products=products,
        query=query,
        sort=sort,
        direction=direction,
        other_dir=other_dir,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        page_size_choices=PAGE_SIZE_CHOICES,
        filters=filters,
        filters_json=filters_json,
        filter_options=models.get_filter_options(),
        categories=models.list_categories(),
    )


@products_bp.route("/products/<int:product_id>/reviewed", methods=["POST"])
def toggle_reviewed(product_id):
    if models.is_reviewed_locked(product_id):
        return jsonify({"ok": True, "reviewed": True, "locked": True})

    data = request.get_json(silent=True) or {}
    reviewed = bool(data.get("reviewed"))
    models.set_reviewed(product_id, reviewed)
    return jsonify({"ok": True, "reviewed": reviewed})


@products_bp.route("/products/<int:product_id>/edit", methods=["GET"])
def edit_product(product_id):
    product = models.get_product(product_id)
    if product is None:
        flash("Product not found.", "error")
        return redirect(url_for("products.list_products_view"))
    categories = models.list_categories()
    return render_template("edit_product.html", product=product, categories=categories)


@products_bp.route("/products/<int:product_id>/edit", methods=["POST"])
def update_product(product_id):
    category_id = request.form.get("category_id")
    name = request.form.get("name", "")
    techbuy_link = request.form.get("techbuy_link", "")
    other_link = request.form.get("other_link", "")

    ok, error = models.update_product(product_id, category_id, name, techbuy_link, other_link)
    if ok:
        flash(f'Product "{name.strip()}" updated.', "success")
        return redirect(url_for("products.list_products_view"))
    else:
        flash(error, "error")
        return redirect(url_for("products.edit_product", product_id=product_id))


@products_bp.route("/products/<int:product_id>/delete", methods=["POST"])
def delete_product(product_id):
    models.delete_product(product_id)
    flash("Product deleted.", "success")
    return redirect(request.referrer or url_for("products.list_products_view"))


@products_bp.route("/products/other-sites", methods=["GET"])
def other_sites_view():
    counts = models.get_other_site_counts()
    sites = [
        {"domain": domain, "name": registry.get_site_display_name(domain), "count": count}
        for domain, count in counts.items()
    ]
    sites.sort(key=lambda s: s["name"].lower())
    return render_template("other_sites.html", sites=sites, total=sum(counts.values()))


@products_bp.route("/products/bulk-delete", methods=["POST"])
def bulk_delete():
    data = request.get_json(silent=True) or {}
    ids = _parse_ids(data.get("ids", []))
    deleted = models.delete_products(ids)
    return jsonify({"ok": True, "deleted": deleted})


@products_bp.route("/products/bulk-refetch", methods=["POST"])
def bulk_refetch():
    data = request.get_json(silent=True) or {}
    ids = _parse_ids(data.get("ids", []))
    if not ids:
        return jsonify({"ok": False, "error": "No products selected."}), 400
    started = runner.start_fetch(product_ids=ids)
    if not started:
        return jsonify({"ok": False, "error": "A fetch is already running."}), 409
    return jsonify({"ok": True})


@products_bp.route("/products/bulk-mark-reviewed", methods=["POST"])
def bulk_mark_reviewed():
    data = request.get_json(silent=True) or {}
    ids = _parse_ids(data.get("ids", []))
    updated, skipped = models.mark_reviewed_bulk(ids)
    return jsonify({"ok": True, "updated": updated, "skipped_locked": skipped})


@products_bp.route("/products/bulk-export", methods=["POST"])
def bulk_export():
    ids = _parse_ids(request.form.getlist("ids"))
    buffer = build_workbook(product_ids=ids) if ids else build_workbook()
    return send_file(
        buffer,
        as_attachment=True,
        download_name=build_filename(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
