"""Context processors — inject theme and nav data into every template."""

import os
from time import time as _time

from flask import request, session

from user_app.api_client import get_api_client


def init_context_processors(app):
    """Register context processors on *app*."""

    ADMIN_PANEL_URL = os.environ.get(
        "ADMIN_PANEL_URL", "http://127.0.0.1:5111"
    )
    RFPO_THEME_DEFAULT = os.environ.get("RFPO_THEME", "1") == "1"

    @app.context_processor
    def inject_nav_context():
        # Determine active theme
        theme_param = request.args.get("theme")
        if theme_param in ("rfpo", "default"):
            use_rfpo_theme = theme_param == "rfpo"
        elif request.cookies.get("rfpo_theme") == "1":
            use_rfpo_theme = True
        else:
            use_rfpo_theme = RFPO_THEME_DEFAULT

        base = {
            "admin_panel_url": ADMIN_PANEL_URL,
            "rfpo_theme": use_rfpo_theme,
        }
        nav = {"is_admin": False, "is_approver": False, "show_rfpo_nav": False}

        if "auth_token" not in session:
            return {**base, "nav": nav}

        # Re-verify roles every 60 s to pick up permission changes
        cached = session.get("nav_context")
        cached_at = session.get("nav_context_ts", 0)
        if cached and (_time() - cached_at) < 60:
            return {**base, "nav": cached}

        try:
            client = get_api_client()
            resp = client.get("/auth/verify")
            if resp.get("error") == "permissions_changed":
                session.pop("nav_context", None)
                session.pop("nav_context_ts", None)
                return {**base, "nav": nav}
            if resp.get("authenticated"):
                roles = resp.get("user", {}).get("roles", [])
                is_admin = "RFPO_ADMIN" in roles or "GOD" in roles
                is_approver = resp.get("user", {}).get("is_approver", False)
                nav["is_admin"] = is_admin
                nav["is_approver"] = is_approver
                nav["show_rfpo_nav"] = is_admin or is_approver
                session["nav_context"] = nav
                session["nav_context_ts"] = _time()
        except Exception:
            pass

        return {**base, "nav": nav}
