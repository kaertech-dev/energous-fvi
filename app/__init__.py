import pymysql
from flask import Flask, jsonify, request
from app.config import Config
from app.routes_scan import scan_bp
from app.routes_admin import admin_bp

def create_app():
    Config.validate()
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(Config)

    app.register_blueprint(scan_bp)
    app.register_blueprint(admin_bp)

    @app.errorhandler(pymysql.err.OperationalError)
    def handle_database_unavailable(_error):
        app.logger.error("Database operation failed", exc_info=_error)
        message = "The database is temporarily unavailable. Please try again shortly."
        if request.path.startswith(("/api/", "/admin/api/")):
            return jsonify({"ok": False, "message": message}), 503
        return message, 503

    return app
