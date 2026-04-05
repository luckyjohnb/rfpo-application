"""
SAML 2.0 Authentication Module
Handles SP-initiated SAML authentication with USCAR's Entra ID (IdP).

Flow:
1. User clicks "Sign in with Microsoft" → /auth/login-microsoft
2. App generates AuthnRequest → redirect to IdP SSO URL
3. User authenticates at their home IdP (Ford/GM/Stellantis) via Entra B2B
4. IdP POSTs SAML Response to /saml/acs
5. App validates assertion, matches user by email, issues RFPO JWT
"""

import os
import logging
from urllib.parse import urlparse

from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.utils import OneLogin_Saml2_Utils

logger = logging.getLogger(__name__)


def is_saml_enabled():
    """Check if SAML SSO is configured and enabled."""
    enabled = os.environ.get("SAML_ENABLED", "false").lower() == "true"
    has_idp = bool(os.environ.get("SAML_IDP_ENTITY_ID"))
    return enabled and has_idp


def _get_saml_settings():
    """Build python3-saml settings dict from environment variables."""
    sp_entity_id = os.environ.get("SAML_SP_ENTITY_ID", "")
    sp_acs_url = os.environ.get("SAML_SP_ACS_URL", "")
    sp_sls_url = os.environ.get("SAML_SP_SLS_URL", "")

    idp_entity_id = os.environ.get("SAML_IDP_ENTITY_ID", "")
    idp_sso_url = os.environ.get("SAML_IDP_SSO_URL", "")
    idp_sls_url = os.environ.get("SAML_IDP_SLS_URL", "")
    idp_x509_cert = os.environ.get("SAML_IDP_X509_CERT", "")

    return {
        "strict": True,
        "debug": os.environ.get("FLASK_ENV") == "development",
        "sp": {
            "entityId": sp_entity_id,
            "assertionConsumerService": {
                "url": sp_acs_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "singleLogoutService": {
                "url": sp_sls_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        },
        "idp": {
            "entityId": idp_entity_id,
            "singleSignOnService": {
                "url": idp_sso_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "singleLogoutService": {
                "url": idp_sls_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": idp_x509_cert,
        },
        "security": {
            "nameIdEncrypted": False,
            "authnRequestsSigned": False,
            "logoutRequestSigned": False,
            "logoutResponseSigned": False,
            "signMetadata": False,
            "wantMessagesSigned": False,
            "wantAssertionsSigned": True,
            "wantNameIdEncrypted": False,
            "wantAssertionsEncrypted": False,
            "allowSingleLabelDomains": False,
            "signatureAlgorithm": "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
            "digestAlgorithm": "http://www.w3.org/2001/04/xmlenc#sha256",
        },
    }


def prepare_flask_request(request):
    """Convert Flask request into the format python3-saml expects.

    Handles reverse proxy / load balancer scenarios where the app
    sees HTTP internally but the external URL is HTTPS.
    """
    url_data = urlparse(request.url)

    # Behind Azure Container Apps, the app may see HTTP but external is HTTPS.
    # Use X-Forwarded headers if present, otherwise fall back to request values.
    scheme = request.headers.get("X-Forwarded-Proto", url_data.scheme)
    host = request.headers.get("X-Forwarded-Host", request.host)
    port = request.headers.get("X-Forwarded-Port", "")

    # Determine server port based on scheme
    if not port:
        if scheme == "https":
            port = "443"
        else:
            port = "80"

    return {
        "https": "on" if scheme == "https" else "off",
        "http_host": host,
        "server_port": port,
        "script_name": request.path,
        "get_data": request.args.copy(),
        "post_data": request.form.copy(),
    }


def init_saml_auth(request):
    """Initialize a OneLogin_Saml2_Auth instance from a Flask request."""
    req = prepare_flask_request(request)
    auth = OneLogin_Saml2_Auth(req, _get_saml_settings())
    return auth


# --- Claim extraction helpers ---

# Standard SAML 2.0 claim URIs
CLAIM_EMAIL = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"
CLAIM_GIVEN_NAME = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname"
CLAIM_SURNAME = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname"
CLAIM_NAME = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name"

# Custom role claim — matches the URL configured in Entra ID Enterprise Application
CLAIM_ROLE_CUSTOM = None  # Will be set dynamically from SAML_SP_ENTITY_ID


def _get_role_claim_url():
    """Build the custom role claim URL from the SP entity ID."""
    sp_entity_id = os.environ.get("SAML_SP_ENTITY_ID", "")
    if sp_entity_id:
        return f"{sp_entity_id}/saml/attributes/role"
    return None


def extract_user_attributes(auth):
    """Extract user identity attributes from a validated SAML assertion.

    Returns a dict with normalized keys:
        - email: user's email address (from NameID or emailaddress claim)
        - first_name: given name
        - last_name: surname
        - display_name: full display name
        - roles: list of Entra App Role values (e.g., ['RFPO_USER', 'RFPO_ADMIN'])
        - name_id: the NameID value from the assertion
        - session_index: SAML session index (for SLS)
    """
    attributes = auth.get_attributes()
    name_id = auth.get_nameid()
    session_index = auth.get_session_index()

    # Email: prefer NameID (configured as UPN), fall back to emailaddress claim
    email = name_id
    if CLAIM_EMAIL in attributes:
        email = attributes[CLAIM_EMAIL][0]

    # Names
    first_name = attributes.get(CLAIM_GIVEN_NAME, [""])[0]
    last_name = attributes.get(CLAIM_SURNAME, [""])[0]
    display_name = attributes.get(CLAIM_NAME, [""])[0]

    # Roles from custom claim
    roles = []
    role_claim_url = _get_role_claim_url()
    if role_claim_url and role_claim_url in attributes:
        roles = attributes[role_claim_url]

    # Also check standard role claim URI
    standard_role_uri = "http://schemas.microsoft.com/ws/2008/06/identity/claims/role"
    if not roles and standard_role_uri in attributes:
        roles = attributes[standard_role_uri]

    return {
        "email": email.strip().lower() if email else None,
        "first_name": first_name,
        "last_name": last_name,
        "display_name": display_name or f"{first_name} {last_name}".strip(),
        "roles": roles,
        "name_id": name_id,
        "session_index": session_index,
    }


# --- Permission mapping ---

# Maps Entra App Role values to RFPO permission strings
ROLE_TO_PERMISSION = {
    "RFPO_ADMIN": ["RFPO_ADMIN", "RFPO_USER"],  # Admin inherits User
    "RFPO_USER": ["RFPO_USER"],
}


def map_roles_to_permissions(entra_roles):
    """Map Entra App Role values to RFPO permission set.

    D7 resolution: Entra roles serve as baseline. Admin can override/elevate
    within RFPO (e.g., add GOD, VROOM_ADMIN). This function returns the
    baseline permissions from Entra roles only.
    """
    permissions = set()
    for role in entra_roles:
        role_upper = role.upper().strip()
        if role_upper in ROLE_TO_PERMISSION:
            permissions.update(ROLE_TO_PERMISSION[role_upper])
    return list(permissions)


def get_sp_metadata():
    """Generate SP metadata XML for IT to import into Entra ID."""
    settings = _get_saml_settings()
    metadata = OneLogin_Saml2_Utils.add_x509_key_descriptors(
        OneLogin_Saml2_Auth.get_settings(settings).get_sp_metadata(), None
    )
    return metadata
