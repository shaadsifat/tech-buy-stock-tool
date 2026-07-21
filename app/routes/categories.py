from flask import Blueprint, render_template, request, redirect, url_for, flash

from app import models
from app.config import PAGE_SIZE_CHOICES, DEFAULT_PAGE_SIZE

categories_bp = Blueprint("categories", __name__)


@categories_bp.route("/categories", methods=["GET"])
def categories_view():
    page = max(1, request.args.get("page", 1, type=int))
    page_size = request.args.get("size", DEFAULT_PAGE_SIZE, type=int)
    if page_size not in PAGE_SIZE_CHOICES:
        page_size = DEFAULT_PAGE_SIZE
    sort = request.args.get("sort", "name")
    direction = request.args.get("dir", "asc")
    query = request.args.get("q", "").strip()

    categories, total = models.list_categories_with_counts(page, page_size, sort, direction, query)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    other_dir = "desc" if direction == "asc" else "asc"

    return render_template(
        "categories.html",
        categories=categories,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        page_size_choices=PAGE_SIZE_CHOICES,
        sort=sort,
        direction=direction,
        other_dir=other_dir,
        query=query,
    )


@categories_bp.route("/categories", methods=["POST"])
def add_category():
    name = request.form.get("name", "")
    ok, error = models.add_category(name)
    if ok:
        flash(f'Category "{name.strip()}" added.', "success")
    else:
        flash(error, "error")
    return redirect(url_for("categories.categories_view"))


@categories_bp.route("/categories/<int:category_id>/delete", methods=["POST"])
def delete_category(category_id):
    ok, error = models.delete_category(category_id)
    if ok:
        flash("Category deleted.", "success")
    else:
        flash(error, "error")
    return redirect(url_for("categories.categories_view"))
