"""Auth blueprint — login/logout, verify, SSO/SAML, password routes."""

import os

from flask import (
    Blueprint,
    current_app,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
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


# ── SAML SSO ────────────────────────────────────────────────────────


@auth_bp.route("/auth/login-microsoft")
def saml_login():
    """Initiate SAML SSO flow."""
    from auth_saml import init_saml_auth, is_saml_enabled

    if not is_saml_enabled():
        return redirect(url_for("pages.login_page"))

    auth = init_saml_auth(request)
    return_to = request.args.get("next", url_for("pages.dashboard"))
    sso_url = auth.login(return_to=return_to)
    return redirect(sso_url)


@auth_bp.route("/saml/acs", methods=["GET", "POST"])
def saml_acs():
    """Assertion Consumer Service — receives SAML Response from IdP."""
    from auth_saml import (
        extract_user_attributes,
        init_saml_auth,
        is_saml_enabled,
    )

    if request.method == "GET":
        return redirect(url_for("pages.login_page"))

    if not is_saml_enabled():
        return "SAML SSO is not enabled", 403

    auth = init_saml_auth(request)
    auth.process_response()
    errors = auth.get_errors()

    if errors:
        error_reason = auth.get_last_error_reason()
        current_app.logger.error(
            "SAML ACS validation failed: %s — %s", errors, error_reason
        )
        return (
            render_template(
                "app/error.html",
                error_code=401,
                error_message=(
                    "SSO authentication failed. "
                    "Please contact your administrator."
                ),
            ),
            401,
        )

    if not auth.is_authenticated():
        return (
            render_template(
                "app/error.html",
                error_code=401,
                error_message="Authentication was not completed.",
            ),
            401,
        )

    user_attrs = extract_user_attributes(auth)
    email = user_attrs.get("email")

    if not email:
        current_app.logger.error("SAML assertion missing email/NameID")
        return (
            render_template(
                "app/error.html",
                error_code=400,
                error_message="SSO response did not include an email address.",
            ),
            400,
        )

    INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")
    internal_headers = (
        {"X-Internal-API-Key": INTERNAL_API_KEY} if INTERNAL_API_KEY else {}
    )

    client = get_api_client()
    match_response = client.post(
        "/auth/saml-match",
        {
            "email": email,
            "entra_roles": user_attrs.get("roles", []),
            "first_name": user_attrs.get("first_name", ""),
            "last_name": user_attrs.get("last_name", ""),
            "name_id": user_attrs.get("name_id", ""),
        },
        extra_headers=internal_headers,
    )

    if not match_response.get("success"):
        message = match_response.get(
            "message",
            "Your account has not been set up in RFPO. "
            "Contact your USCAR administrator.",
        )
        current_app.logger.warning("SAML login blocked for %s: %s", email, message)
        return (
            render_template(
                "app/error.html",
                error_code=403,
                error_message=message,
            ),
            403,
        )

    session["auth_token"] = match_response["token"]
    session["user"] = match_response["user"]
    session["auth_method"] = "sso"
    session["saml_session_index"] = user_attrs.get("session_index")

    relay_state = request.form.get("RelayState", "")
    if (
        relay_state
        and relay_state != url_for("auth.saml_login")
        and not relay_state.startswith("http")
    ):
        return redirect(relay_state)
    return redirect(url_for("pages.dashboard"))


@auth_bp.route("/saml/sls", methods=["GET", "POST"])
def saml_sls():
    """Single Logout Service — handles IdP-initiated logout."""
    from auth_saml import init_saml_auth, is_saml_enabled

    if not is_saml_enabled():
        return redirect(url_for("pages.login_page"))

    auth = init_saml_auth(request)

    def delete_session():
        session.pop("auth_token", None)
        session.pop("user", None)
        session.pop("auth_method", None)
        session.pop("saml_session_index", None)

    url = auth.process_slo(delete_session_cb=delete_session)
    errors = auth.get_errors()

    if errors:
        current_app.logger.error("SAML SLS error: %s", errors)

    if url:
        return redirect(url)
    return redirect(url_for("pages.login_page"))


@auth_bp.route("/saml/metadata")
def saml_metadata():
    """Serve SP metadata XML."""
    from auth_saml import init_saml_auth, is_saml_enabled

    if not is_saml_enabled():
        return "SAML SSO is not enabled", 404

    auth = init_saml_auth(request)
    settings = auth.get_settings()
    metadata = settings.get_sp_metadata()
    errors = settings.validate_metadata(metadata)

    if errors:
        return f"Metadata validation errors: {', '.join(errors)}", 500

    resp = make_response(metadata, 200)
    resp.headers["Content-Type"] = "text/xml"
    return resp
