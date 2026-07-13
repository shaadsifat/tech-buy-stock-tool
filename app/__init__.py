import os

from flask import Flask

from app.db import init_db


def create_app():
    app = Flask(__name__)
    app.secret_key = os.urandom(24)

    init_db()

    from app.routes.main import main_bp
    from app.routes.products import products_bp
    from app.routes.categories import categories_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(categories_bp)

    return app
