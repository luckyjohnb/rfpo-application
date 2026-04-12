"""Auth provider abstraction — Dependency Inversion for SSO providers.

Route handlers depend on this interface, not on concrete modules like
``auth_saml``.  The concrete provider is wired once in ``app.py`` via
``init_auth_provider()``.
"""

from flask import current_app


class AuthProvider:
    """Base interface that SSO provider implementations must satisfy."""

    def is_enabled(self) -> bool:
        """Return True if this SSO provider is configured and available."""
        return False

    def init_auth(self, flask_request):
        """Return a provider-specific auth object from a Flask request."""
        raise NotImplementedError

    def extract_user_attributes(self, auth) -> dict:
        """Extract normalised user attributes from a validated assertion."""
        raise NotImplementedError


class SAMLAuthProvider(AuthProvider):
    """Concrete provider backed by ``auth_saml`` (python3-saml / Entra ID)."""

    def is_enabled(self) -> bool:
        from auth_saml import is_saml_enabled
        return is_saml_enabled()

    def init_auth(self, flask_request):
        from auth_saml import init_saml_auth
        return init_saml_auth(flask_request)

    def extract_user_attributes(self, auth) -> dict:
        from auth_saml import extract_user_attributes
        return extract_user_attributes(auth)


class NullAuthProvider(AuthProvider):
    """No-op provider used when SSO is not configured."""
    pass


# ── Flask integration ───────────────────────────────────────────────


def init_auth_provider(app):
    """Detect SSO configuration and store the appropriate provider."""
    import os

    if os.environ.get("SAML_ENABLED", "false").lower() == "true":
        provider = SAMLAuthProvider()
    else:
        provider = NullAuthProvider()
    app.extensions["auth_provider"] = provider
    return provider


def get_auth_provider() -> AuthProvider:
    """Retrieve the auth provider from the current Flask app."""
    return current_app.extensions.get("auth_provider", NullAuthProvider())
