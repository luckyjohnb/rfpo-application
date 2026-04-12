"""Auth blueprint — login/logout, verify, SSO token, password routes.

SAML SSO routes live in ``user_app.blueprints.saml`` (SRP separation).
"""

import os

from flask import (
    Blueprint,
    jsonify,
    request,
    session,
)

from user_app.api_client import get_api_client

auth_bp = Blueprint("auth", __name__)


# ── API proxy routes ────────────────────────────────────────────────


@auth_bp.route("/api/auth/login", methods=["POST"])
def api_login():
    """Login API proxy."""
    client = get_api_client()
    data = request.get_json()
    response = client.post("/auth/login", data)

    if response.get("success") and response.get("token"):
        session.clear()
        session.permanent = True
        session["auth_token"] = response["token"]
        session["user"] = response["user"]
        roles = response.get("user", {}).get("roles", [])
        is_admin = "RFPO_ADMIN" in roles or "GOD" in roles
        is_approver = response.get("user", {}).get("is_approver", False)
        session["nav_context"] = {
            "is_admin": is_admin,
            "is_approver": is_approver,
            "show_rfpo_nav": is_admin or is_approver,
        }
        session["user_info"] = response.get("user", {})

    return jsonify(response)


@auth_bp.route("/api/auth/logout", methods=["POST"])
def api_logout():
    """Logout API proxy."""
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully"})


@auth_bp.route("/api/auth/verify", methods=["GET"])
def api_verify():
    """Verify auth API proxy."""
    if "auth_token" not in session:
        return jsonify({"authenticated": False, "message": "No token"}), 401

    client = get_api_client()
    response = client.get("/auth/verify")
    if response.get("error") == "permissions_changed":
        return jsonify(response), 401
    return jsonify(response)


@auth_bp.route("/api/auth/sso-token", methods=["POST"])
def api_sso_token():
    """Generate SSO token for admin panel cross-auth."""
    client = get_api_client()
    response = client.post("/auth/sso-token")
    return jsonify(response)


@auth_bp.route("/api/auth/change-password", methods=["POST"])
def api_change_password():
    """Change password API proxy."""
    client = get_api_client()
    data = request.get_json()
    response = client.post("/auth/change-password", data)
    return jsonify(response)
