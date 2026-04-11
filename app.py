"""
RFPO User-Facing Application
Port: 5000
API Consumer Only - All data operations go through API layer

Thin factory — all routes live in user_app/blueprints/.
"""

import os
from datetime import datetime, timedelta

from flask import Flask, jsonify, render_template
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from error_handlers import register_error_handlers
from logging_config import setup_logging
from user_app.api_client import init_api_client
from user_app.context_processors import init_context_processors


def create_user_app():
    """Create user-facing Flask application."""
    app = Flask(__name__)

    # ProxyFix for correct IP/proto behind Azure Load Balancer
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # ── Configuration ───────────────────────────────────────────────
    _is_production = "postgresql" in os.environ.get("DATABASE_URL", "")
    app.config["SECRET_KEY"] = os.environ.get(
        "USER_APP_SECRET_KEY", "user-app-secret-change-in-production"
    )
    if app.config["SECRET_KEY"] == "user-app-secret-change-in-production":
        if _is_production:
            raise RuntimeError(
                "USER_APP_SECRET_KEY must be set in production "
                "(DATABASE_URL contains postgresql)"
            )
        import warnings
        warnings.warn(
            "USER_APP_SECRET_KEY not set! Using insecure default.",
            stacklevel=1,
        )
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = (
        os.environ.get("SESSION_COOKIE_SECURE", "True").lower() == "true"
    )
    app.config["MAX_CONTENT_LENGTH"] = int(
        os.environ.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024)
    )
    app.config["WTF_CSRF_TIME_LIMIT"] = None

    # ── CSRF protection ─────────────────────────────────────────────
    csrf = CSRFProtect(app)

    # ── Logging ─────────────────────────────────────────────────────
    logger = setup_logging("user_app", log_to_file=True)
    app.logger = logger

    # ── Error handlers ──────────────────────────────────────────────
    register_error_handlers(app, "user_app")

    # ── CORS ────────────────────────────────────────────────────────
    _cors_default = "https://rfpo.uscar.org"
    _allowed_origins = os.environ.get("CORS_ORIGINS", _cors_default).split(",")
    CORS(
        app,
        origins=_allowed_origins,
        allow_headers=["Content-Type", "Authorization"],
    )

    # ── API client (DIP) ────────────────────────────────────────────
    init_api_client(app)

    # ── Security headers ────────────────────────────────────────────
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'"
            " https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'"
            " https://cdn.jsdelivr.net"
            " https://cdnjs.cloudflare.com; "
            "font-src 'self'"
            " https://cdnjs.cloudflare.com; "
            "img-src 'self' data:; "
            "connect-src 'self' "
            + os.environ.get(
                "API_BASE_URL", "http://127.0.0.1:5002/api"
            ).rsplit("/api", 1)[0]
        )
        return response

    # ── Theme toggle cookie ─────────────────────────────────────────
    RFPO_THEME_DEFAULT = os.environ.get("RFPO_THEME", "1") == "1"

    @app.after_request
    def _set_theme_cookie(response):
        from flask import request as req

        theme_param = req.args.get("theme")
        if theme_param == "rfpo":
            response.set_cookie(
                "rfpo_theme", "1", max_age=60 * 60 * 24 * 365, samesite="Lax"
            )
        elif theme_param == "default":
            response.delete_cookie("rfpo_theme")
        return response

    # ── Jinja2 filters ──────────────────────────────────────────────
    @app.template_filter("currency")
    def format_currency(value):
        if value is None:
            return "$0.00"
        try:
            float_value = float(value)
            return f"${float_value:,.2f}"
        except (ValueError, TypeError):
            return "$0.00"

    # ── Context processors (nav, theme) ─────────────────────────────
    init_context_processors(app)

    # ── Register blueprints ─────────────────────────────────────────
    from user_app.blueprints.auth import auth_bp
    from user_app.blueprints.file_proxy import file_proxy_bp
    from user_app.blueprints.lookup_proxy import lookup_proxy_bp
    from user_app.blueprints.notification_proxy import notification_proxy_bp
    from user_app.blueprints.pages import pages_bp
    from user_app.blueprints.rfpo_proxy import rfpo_proxy_bp
    from user_app.blueprints.team_proxy import team_proxy_bp
    from user_app.blueprints.ticket_proxy import ticket_proxy_bp
    from user_app.blueprints.user_proxy import user_proxy_bp

    # CSRF exemptions for SAML callbacks and login (no session/token yet)
    csrf.exempt(auth_bp)

    app.register_blueprint(auth_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(rfpo_proxy_bp)
    app.register_blueprint(file_proxy_bp)
    app.register_blueprint(user_proxy_bp)
    app.register_blueprint(team_proxy_bp)
    app.register_blueprint(lookup_proxy_bp)
    app.register_blueprint(notification_proxy_bp)
    app.register_blueprint(ticket_proxy_bp)

    # ── Health check ────────────────────────────────────────────────
    @app.route("/health")
    def health_check():
        resp = jsonify(
            {
                "status": "healthy",
                "service": "RFPO User App",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "2.0.0",
            }
        )
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp

    # ── Error pages ─────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(error):
        return (
            render_template(
                "app/error.html",
                error_code=404,
                error_message="Page not found",
            ),
            404,
        )

    @app.errorhandler(500)
    def internal_error(error):
        return (
            render_template(
                "app/error.html",
                error_code=500,
                error_message="Internal server error",
            ),
            500,
        )

    return app


# Create app instance
app = create_user_app()

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 RFPO USER APPLICATION STARTING")
    print("=" * 60)
    print("🌐 Server: http://127.0.0.1:5000")
    print("🔍 Health: http://127.0.0.1:5000/health")
    print("📋 Dashboard: http://127.0.0.1:5000/dashboard")
    print("🔐 Login: http://127.0.0.1:5000/login")
    print("=" * 60)

    app.run(
        debug=os.environ.get("FLASK_ENV") == "development",
        host="0.0.0.0",
        port=5000,
    )
