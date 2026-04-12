"""SAML SSO blueprint — login, ACS, SLS, metadata routes.

Separated from the core auth blueprint (SRP) and uses the injected
auth provider (DIP) instead of importing ``auth_saml`` directly.
"""

import os

from flask import (
    Blueprint,
    current_app,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from user_app.api_client import get_api_client
from user_app.auth_provider import get_auth_provider

saml_bp = Blueprint("saml", __name__)


@saml_bp.route("/auth/login-microsoft")
def saml_login():
    """Initiate SAML SSO flow."""
    provider = get_auth_provider()
    if not provider.is_enabled():
        return redirect(url_for("pages.login_page"))

    auth = provider.init_auth(request)
    return_to = request.args.get("next", url_for("pages.dashboard"))
    sso_url = auth.login(return_to=return_to)
    return redirect(sso_url)


@saml_bp.route("/saml/acs", methods=["GET", "POST"])
def saml_acs():
    """Assertion Consumer Service — receives SAML Response from IdP."""
    provider = get_auth_provider()

    if request.method == "GET":
        return redirect(url_for("pages.login_page"))

    if not provider.is_enabled():
        return "SAML SSO is not enabled", 403

    auth = provider.init_auth(request)
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

    user_attrs = provider.extract_user_attributes(auth)
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
        and relay_state != url_for("saml.saml_login")
        and not relay_state.startswith("http")
    ):
        return redirect(relay_state)
    return redirect(url_for("pages.dashboard"))


@saml_bp.route("/saml/sls", methods=["GET", "POST"])
def saml_sls():
    """Single Logout Service — handles IdP-initiated logout."""
    provider = get_auth_provider()
    if not provider.is_enabled():
        return redirect(url_for("pages.login_page"))

    auth = provider.init_auth(request)

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


@saml_bp.route("/saml/metadata")
def saml_metadata():
    """Serve SP metadata XML."""
    provider = get_auth_provider()
    if not provider.is_enabled():
        return "SAML SSO is not enabled", 404

    auth = provider.init_auth(request)
    settings = auth.get_settings()
    metadata = settings.get_sp_metadata()
    errors = settings.validate_metadata(metadata)

    if errors:
        return f"Metadata validation errors: {', '.join(errors)}", 500

    resp = make_response(metadata, 200)
    resp.headers["Content-Type"] = "text/xml"
    return resp
