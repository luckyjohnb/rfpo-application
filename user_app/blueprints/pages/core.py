"""Core pages — landing, login, dashboard, profile, approvals."""

from flask import redirect, render_template, request, session, url_for

from user_app.api_client import get_api_client
from user_app.auth_provider import get_auth_provider
from user_app.blueprints.pages import pages_bp
from user_app.dashboard_service import (
    check_first_login,
    classify_dashboard_type,
    fetch_dashboard_data,
)
from user_app.decorators import require_admin, require_auth


@pages_bp.route("/")
def landing():
    """Landing page."""
    return render_template("app/landing.html")


@pages_bp.route("/login")
def login_page():
    """Login page."""
    provider = get_auth_provider()
    return render_template("app/login.html", saml_enabled=provider.is_enabled())


@pages_bp.route("/dashboard")
@require_auth
def dashboard():
    """Main dashboard."""
    client = get_api_client()

    user_info = client.get("/auth/verify")
    if user_info.get("error") == "permissions_changed":
        return redirect(url_for("pages.login_page", reason="permissions_changed"))
    if not user_info.get("authenticated"):
        session.pop("auth_token", None)
        return redirect(url_for("pages.login_page"))

    if check_first_login(client):
        return redirect(url_for("pages.first_login_password_reset"))

    data = fetch_dashboard_data(client)
    roles = user_info.get("user", {}).get("roles", [])
    dashboard_type = classify_dashboard_type(roles, data["is_approver"])

    return render_template(
        "app/dashboard.html",
        user=user_info.get("user"),
        recent_rfpos=data["recent_rfpos"],
        teams=data["teams"],
        user_permissions=data["user_permissions"],
        dashboard_type=dashboard_type,
        is_approver=data["is_approver"],
    )


@pages_bp.route("/profile")
@require_auth
def profile():
    """User profile page."""
    return render_template("app/profile.html")


@pages_bp.route("/approvals")
@require_auth
def approvals():
    """Approval queue page for approvers."""
    is_admin = False
    user_info = session.get("user_info", {})
    roles = user_info.get("permissions", [])
    if roles:
        is_admin = "RFPO_ADMIN" in roles or "GOD" in roles
    return render_template("app/approvals.html", is_admin=is_admin)


@pages_bp.route("/first-login-password-reset")
@require_auth
def first_login_password_reset():
    """First login password reset page."""
    return render_template("app/first_login_password_reset.html")
