"""
Authentication API Routes
Centralized authentication endpoints for both user app and admin panel
"""

from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
from collections import defaultdict
import threading
import jwt
import os
import sys
import logging

logger = logging.getLogger(__name__)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, User

auth_api = Blueprint("auth_api", __name__, url_prefix="/api/auth")

# JWT Configuration
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret-change-in-production")

# --- Rate limiting for login ---
_login_attempts = defaultdict(list)
_login_lock = threading.Lock()
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 300  # 5 minutes


def _is_rate_limited(ip):
    """Check if IP has exceeded login attempt limit"""
    now = datetime.utcnow()
    with _login_lock:
        _login_attempts[ip] = [
            t for t in _login_attempts[ip]
            if (now - t).total_seconds() < _WINDOW_SECONDS
        ]
        return len(_login_attempts[ip]) >= _MAX_ATTEMPTS


def _record_login_attempt(ip):
    with _login_lock:
        _login_attempts[ip].append(datetime.utcnow())


@auth_api.route("/login", methods=["POST"])
def login():
    """User login endpoint"""
    try:
        # Rate limiting
        client_ip = request.environ.get("HTTP_X_FORWARDED_FOR", request.remote_addr)
        if _is_rate_limited(client_ip):
            logger.warning(f"Rate limited login from {client_ip}")
            return jsonify({"success": False, "message": "Too many login attempts. Try again later."}), 429

        data = request.get_json()
        username = data.get("username")  # This will actually be an email
        password = data.get("password")
        remember_me = data.get("remember_me", False)

        if not username or not password:
            return (
                jsonify({"success": False, "message": "Email and password required"}),
                400,
            )

        # Find user by email (since email is used as username)
        user = User.query.filter_by(email=username).first()

        logger.debug(f"Login attempt for email: {username}")

        if not user or not check_password_hash(user.password_hash, password):
            _record_login_attempt(client_ip)
            return jsonify({"success": False, "message": "Invalid credentials"}), 401

        # Check if user is active
        if not user.active:
            _record_login_attempt(client_ip)
            return jsonify({"success": False, "message": "Account is not active"}), 401

        # Generate JWT token
        expiry = datetime.utcnow() + (
            timedelta(days=30) if remember_me else timedelta(hours=24)
        )
        payload = {
            "user_id": user.id,
            "username": user.email,  # Use email as username
            "exp": expiry,
        }

        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")

        # Update last login
        user.last_visit = datetime.utcnow()
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "token": token,
                "user": {
                    "id": user.id,
                    "username": user.email,
                    "display_name": user.fullname,
                    "email": user.email,
                    "roles": user.get_permissions(),
                    "is_approver": user.is_approver,
                    "approver_summary": user.get_approver_summary(),
                },
            }
        )

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@auth_api.route("/verify", methods=["GET"])
def verify_token():
    """Verify authentication token"""
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"authenticated": False, "message": "No token provided"}), 401

    if token.startswith("Bearer "):
        token = token[7:]

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
        user = User.query.get(payload["user_id"])

        if not user:
            return jsonify({"authenticated": False, "message": "User not found"}), 401

        if not user.active:
            return (
                jsonify({"authenticated": False, "message": "Account not active"}),
                401,
            )

        return jsonify(
            {
                "authenticated": True,
                "user": {
                    "id": user.id,
                    "username": user.email,
                    "display_name": user.fullname,
                    "email": user.email,
                    "roles": user.get_permissions(),
                    "is_approver": user.is_approver,
                    "approver_summary": user.get_approver_summary(),
                },
            }
        )

    except jwt.ExpiredSignatureError:
        return jsonify({"authenticated": False, "message": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"authenticated": False, "message": "Invalid token"}), 401
    except Exception as e:
        return jsonify({"authenticated": False, "message": str(e)}), 401


@auth_api.route("/logout", methods=["POST"])
def logout():
    """User logout (client-side token removal)"""
    return jsonify({"success": True, "message": "Logged out successfully"})


@auth_api.route("/change-password", methods=["POST"])
def change_password():
    """Change user password"""
    from utils import require_auth
    from werkzeug.security import generate_password_hash, check_password_hash

    # Apply auth decorator manually since we're inside the function
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"success": False, "message": "No token provided"}), 401

    if token.startswith("Bearer "):
        token = token[7:]

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
        user = User.query.get(payload["user_id"])

        if not user or not user.active:
            return jsonify({"success": False, "message": "Invalid user"}), 401

        data = request.get_json()
        current_password = data.get("current_password")
        new_password = data.get("new_password")

        if not current_password or not new_password:
            return (
                jsonify(
                    {"success": False, "message": "Current and new password required"}
                ),
                400,
            )

        # Verify current password
        if not check_password_hash(user.password_hash, current_password):
            return (
                jsonify({"success": False, "message": "Current password is incorrect"}),
                400,
            )

        # Validate new password
        if len(new_password) < 8:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "New password must be at least 8 characters",
                    }
                ),
                400,
            )

        # Update password and mark as no longer first-time login
        user.password_hash = generate_password_hash(new_password)
        user.last_visit = (
            datetime.utcnow()
        )  # Update last_visit to mark as no longer first-time
        user.updated_at = datetime.utcnow()
        user.updated_by = user.email

        db.session.commit()

        return jsonify({"success": True, "message": "Password changed successfully"})

    except jwt.ExpiredSignatureError:
        return jsonify({"success": False, "message": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"success": False, "message": "Invalid token"}), 401
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@auth_api.route("/register", methods=["POST"])
def register():
    """User registration (pending approval)"""
    try:
        data = request.get_json()
        username = data.get("username")
        email = data.get("email")
        display_name = data.get("display_name")
        password = data.get("password")

        if not all([username, email, password]):
            return (
                jsonify({"success": False, "message": "Missing required fields"}),
                400,
            )

        # Check if user exists
        if User.query.filter_by(username=username).first():
            return (
                jsonify({"success": False, "message": "Username already exists"}),
                400,
            )

        if User.query.filter_by(email=email).first():
            return (
                jsonify({"success": False, "message": "Email already registered"}),
                400,
            )

        # Create user (pending approval)
        from werkzeug.security import generate_password_hash

        user = User(
            username=username,
            email=email,
            display_name=display_name,
            password_hash=generate_password_hash(password),
            is_active=False,  # Pending approval
            roles=["User"],
            created_at=datetime.utcnow(),
        )

        db.session.add(user)
        db.session.commit()

        return jsonify(
            {"success": True, "message": "Registration successful. Awaiting approval."}
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@auth_api.route("/saml-match", methods=["POST"])
def saml_match():
    """Match a SAML-authenticated user to a local RFPO user and issue JWT.

    Called by the User App after validating a SAML assertion. This endpoint:
    1. Finds the local user by email (case-insensitive)
    2. Verifies the user is active
    3. Stores the Entra NameID for stable matching
    4. Updates permissions from Entra App Roles if present (D7: baseline + override)
    5. Issues a standard RFPO JWT

    D3: If no matching user exists, returns 403 — no JIT provisioning.
    """
    try:
        data = request.get_json()
        email = data.get("email", "").strip().lower()
        entra_roles = data.get("entra_roles", [])
        name_id = data.get("name_id", "")

        if not email:
            return (
                jsonify({"success": False, "message": "Email is required"}),
                400,
            )

        # Find user by email (case-insensitive)
        from sqlalchemy import func

        user = User.query.filter(func.lower(User.email) == email).first()

        if not user:
            return (
                jsonify({
                    "success": False,
                    "message": "Your account has not been set up in RFPO. Contact your USCAR administrator.",
                }),
                403,
            )

        if not user.active:
            return (
                jsonify({
                    "success": False,
                    "message": "Your RFPO account is not active. Contact your USCAR administrator.",
                }),
                403,
            )

        # Store Entra NameID on first SSO login (stable identity link)
        first_sso = not user.entra_oid
        if name_id and first_sso:
            user.entra_oid = name_id

        # D7: Only apply Entra roles on FIRST SSO login (baseline setup).
        # After that, admin-set permissions take precedence.
        if entra_roles and first_sso:
            current_perms = set(user.get_permissions())
            for role in entra_roles:
                role_upper = role.upper().strip()
                if role_upper == "RFPO_ADMIN" and "RFPO_ADMIN" not in current_perms:
                    current_perms.add("RFPO_ADMIN")
                    current_perms.add("RFPO_USER")
                elif role_upper == "RFPO_USER" and "RFPO_USER" not in current_perms:
                    current_perms.add("RFPO_USER")
            user.set_permissions(list(current_perms))

        # Update last visit
        user.last_visit = datetime.utcnow()
        db.session.commit()

        # Issue standard RFPO JWT (D8: same format as password-based login)
        expiry = datetime.utcnow() + timedelta(hours=24)
        payload = {
            "user_id": user.id,
            "username": user.email,
            "auth_method": "sso",
            "exp": expiry,
        }

        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")

        return jsonify({
            "success": True,
            "token": token,
            "user": {
                "id": user.id,
                "username": user.email,
                "display_name": user.fullname,
                "email": user.email,
                "roles": user.get_permissions(),
                "is_approver": user.is_approver,
                "approver_summary": user.get_approver_summary(),
            },
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
