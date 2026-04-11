"""Reusable route decorators for the User App.

Eliminates repeated auth / permission checks across route handlers.
"""

from functools import wraps

from flask import jsonify, redirect, session, url_for

from user_app.api_client import get_api_client


def require_auth(f):
    """Redirect unauthenticated visitors to the login page.

    For use on page-rendering routes (returns a redirect, not JSON).
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        if "auth_token" not in session:
            return redirect(url_for("pages.login_page"))
        return f(*args, **kwargs)

    return decorated


def require_auth_json(f):
    """Return a 401 JSON response for unauthenticated API proxy calls."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if "auth_token" not in session:
            return (
                jsonify({"authenticated": False, "message": "No token"}),
                401,
            )
        return f(*args, **kwargs)

    return decorated


def require_admin(f):
    """Page-level guard: requires RFPO_ADMIN or GOD role.

    Redirects to dashboard if authenticated but not admin,
    or to login if the token is missing / permissions changed.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        if "auth_token" not in session:
            return redirect(url_for("pages.login_page"))

        client = get_api_client()
        user_info = client.get("/auth/verify")

        if user_info.get("error") == "permissions_changed":
            return redirect(
                url_for("pages.login_page", reason="permissions_changed")
            )
        if not user_info.get("authenticated"):
            session.pop("auth_token", None)
            return redirect(url_for("pages.login_page"))

        roles = user_info.get("user", {}).get("roles", [])
        if "RFPO_ADMIN" not in roles and "GOD" not in roles:
            return redirect(url_for("pages.dashboard"))

        return f(*args, **kwargs)

    return decorated
