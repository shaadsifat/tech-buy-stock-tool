from flask import Blueprint, render_template, request, redirect, url_for, flash

from app import models

categories_bp = Blueprint("categories", __name__)


@categories_bp.route("/categories", methods=["GET"])
def categories_view():
    categories = models.list_categories_with_counts()
    return render_template("categories.html", categories=categories)


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
