"""Core pages — landing, login, dashboard, profile, approvals."""

from flask import redirect, render_template, request, session, url_for

from user_app.api_client import get_api_client
from user_app.blueprints.pages import pages_bp
from user_app.decorators import require_admin, require_auth


@pages_bp.route("/")
def landing():
    """Landing page."""
    return render_template("app/landing.html")


@pages_bp.route("/login")
def login_page():
    """Login page."""
    from auth_saml import is_saml_enabled

    return render_template("app/login.html", saml_enabled=is_saml_enabled())


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

    # First-login detection
    user_profile = client.get("/users/profile")
    if user_profile.get("success"):
        user_data = user_profile["user"]
        last_visit = user_data.get("last_visit")
        created_at = user_data.get("created_at")
        if not last_visit or (last_visit and created_at and last_visit == created_at):
            return redirect(url_for("pages.first_login_password_reset"))

    rfpos_response = client.get("/rfpos")
    recent_rfpos = (
        rfpos_response.get("rfpos", []) if rfpos_response.get("success") else []
    )

    teams_response = client.get("/teams")
    user_teams = (
        teams_response.get("teams", []) if teams_response.get("success") else []
    )

    permissions_response = client.get("/users/permissions-summary")
    user_permissions = (
        permissions_response.get("permissions_summary", {})
        if permissions_response.get("success")
        else {}
    )

    approver_response = client.get("/users/approver-status")
    approver_info = approver_response if approver_response.get("success") else {}

    user_data = user_info.get("user", {})
    is_rfpo_user = "RFPO_USER" in user_data.get("roles", [])
    is_rfpo_admin = "RFPO_ADMIN" in user_data.get("roles", []) or "GOD" in user_data.get("roles", [])
    is_approver = approver_info.get("is_approver", False)

    if is_rfpo_admin:
        dashboard_type = "admin"
    elif is_rfpo_user and is_approver:
        dashboard_type = "approver"
    elif is_rfpo_user:
        dashboard_type = "profile_only"
    else:
        dashboard_type = "no_access"

    return render_template(
        "app/dashboard.html",
        user=user_info.get("user"),
        recent_rfpos=recent_rfpos,
        teams=user_teams,
        user_permissions=user_permissions,
        dashboard_type=dashboard_type,
        is_approver=is_approver,
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
