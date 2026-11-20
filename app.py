"""Smart Canteen - Flask application factory."""
import logging
import os
import re
import sys

from flask import Flask, Response, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config  # noqa: E402
from database import close_db, connect, init_schema  # noqa: E402


def create_app(overrides=None):
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    conn = connect(app.config["DATABASE"])
    init_schema(conn)           # creates tables if they do not exist yet
    conn.close()
    app.teardown_appcontext(close_db)

    from routes import admin, auth, menu, orders
    for module in (auth, menu, orders, admin):
        app.register_blueprint(module.bp)

    origin_re = re.compile(app.config["CORS_ORIGIN_REGEX"])

    def origin_allowed(origin):
        return bool(origin_re.match(origin)) or origin in app.config["CORS_ORIGINS"]

    @app.before_request
    def block_foreign_origins():
        """CSRF defence in depth: reject state-changing API calls from unknown origins."""
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.path.startswith("/api/"):
            origin = request.headers.get("Origin")
            if origin and origin != request.host_url.rstrip("/") and not origin_allowed(origin):
                return jsonify({"error": "Request origin not allowed."}), 403

    @app.after_request
    def add_headers(resp):
        origin = request.headers.get("Origin")
        if origin and origin_allowed(origin) and request.path.startswith(("/api/", "/uploads/")):
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Credentials"] = "true"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            resp.headers.add("Vary", "Origin")
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        elif not request.path.startswith("/uploads/"):
            resp.headers["Content-Security-Policy"] = (
                "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
                "script-src 'self'; connect-src 'self' http://localhost:* http://127.0.0.1:*; "
                "base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
        return resp

    @app.get("/uploads/<path:filename>")
    def uploaded_file(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    frontend = app.config["FRONTEND_DIR"]
    if app.config["SERVE_FRONTEND"] and os.path.isdir(frontend):
        @app.get("/")
        def home():
            return send_from_directory(frontend, "index.html")

        @app.get("/js/config.js")
        def runtime_config():
            # When Flask serves the pages, the API is always on the same origin,
            # whatever PORT is configured.
            return Response("window.CANTEEN_API_BASE = '';\n", mimetype="application/javascript",
                            headers={"Cache-Control": "no-store"})

        @app.get("/admin")
        @app.get("/admin/")
        def admin_home():
            return send_from_directory(os.path.join(frontend, "admin"), "dashboard.html")

        @app.get("/<path:filename>")
        def frontend_files(filename):
            if filename.startswith("api/"):
                return jsonify({"error": "Endpoint not found."}), 404
            return send_from_directory(frontend, filename)

    @app.errorhandler(HTTPException)
    def http_error(exc):
        if request.path.startswith("/api/"):
            messages = {404: "Endpoint not found.", 405: "Method not allowed.",
                        413: "Upload too large (max 4 MB).", 415: "Unsupported content type."}
            return jsonify({"error": messages.get(exc.code, exc.description)}), exc.code
        return exc

    @app.errorhandler(Exception)
    def unexpected(exc):
        app.logger.exception("Unhandled error: %s", exc)
        return jsonify({"error": "Something went wrong on the server. Please try again."}), 500

    if not app.debug:
        app.logger.setLevel(logging.INFO)
    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host=application.config["HOST"], port=application.config["PORT"])
