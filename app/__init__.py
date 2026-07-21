import os

from flask import Flask

from app.db import init_db


def pagination_window(current, total, around=3):
    """Page numbers to render for a pagination bar: always the first and last page,
    plus a window of pages around the current one, with None marking a gap where an
    "..." ellipsis belongs. Keeps the bar short even when there are hundreds of pages."""
    if total <= 1:
        return [1] if total == 1 else []

    pages = {1, total}
    for p in range(current - around, current + around + 1):
        if 1 <= p <= total:
            pages.add(p)

    result = []
    prev = None
    for p in sorted(pages):
        if prev is not None and p - prev > 1:
            result.append(None)
        result.append(p)
        prev = p
    return result


def create_app():
    app = Flask(__name__)
    app.secret_key = os.urandom(24)
    app.jinja_env.globals["pagination_window"] = pagination_window

    init_db()

    from app.routes.main import main_bp
    from app.routes.products import products_bp
    from app.routes.categories import categories_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(categories_bp)

    return app
