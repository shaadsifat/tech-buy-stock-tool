import json

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify

from app import models
from app.config import PAGE_SIZE_CHOICES, DEFAULT_PAGE_SIZE

products_bp = Blueprint("products", __name__)


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
