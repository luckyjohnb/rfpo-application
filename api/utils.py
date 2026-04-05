"""
API Utilities
Shared decorators and helper functions for API routes
"""

from functools import wraps
from flask import request, jsonify
import jwt
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import User, Team

# JWT Configuration - fail-hard if secret is missing or insecure
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "")
if not JWT_SECRET_KEY or JWT_SECRET_KEY == "dev-jwt-secret-change-in-production":
    import warnings
    if os.environ.get("FLASK_ENV") == "production":
        raise RuntimeError("JWT_SECRET_KEY must be set to a secure value in production")
    else:
        JWT_SECRET_KEY = "dev-jwt-secret-LOCAL-ONLY-NOT-FOR-PRODUCTION"
        warnings.warn("JWT_SECRET_KEY not set - using insecure default for local development only", stacklevel=1)


def require_auth(f):
    """Decorator to require authentication"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"success": False, "message": "No token provided"}), 401

        try:
            # Remove 'Bearer ' prefix if present
            if token.startswith("Bearer "):
                token = token[7:]

            # Verify token
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
            user = User.query.get(payload["user_id"])

            if not user:
                return jsonify({"success": False, "message": "User not found"}), 401

            if not user.active:
                return jsonify({"success": False, "message": "Account not active"}), 401

            request.current_user = user

        except jwt.ExpiredSignatureError:
            return jsonify({"success": False, "message": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"success": False, "message": "Invalid token"}), 401
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 401

        return f(*args, **kwargs)

    return decorated_function


def require_admin(f):
    """Decorator to require admin privileges"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(request, "current_user") or not request.current_user:
            return (
                jsonify({"success": False, "message": "Authentication required"}),
                401,
            )

        if "GOD" not in (request.current_user.get_permissions() or []):
            return jsonify({"success": False, "message": "Admin access required"}), 403

        return f(*args, **kwargs)

    return decorated_function


def require_admin_or_team_admin(f):
    """Decorator to require admin or team admin privileges.
    Checks system-level GOD/RFPO_ADMIN permissions first,
    then falls back to checking if user is a team-level admin."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(request, "current_user") or not request.current_user:
            return (
                jsonify({"success": False, "message": "Authentication required"}),
                401,
            )

        user = request.current_user
        user_permissions = user.get_permissions() or []

        # System-level admin check
        if any(perm in user_permissions for perm in ["GOD", "RFPO_ADMIN"]):
            return f(*args, **kwargs)

        # Team-level admin check: user's record_id in any team's rfpo_admin_user_ids
        teams = Team.query.all()
        for team in teams:
            admin_users = team.get_rfpo_admin_users()
            if user.record_id in admin_users:
                return f(*args, **kwargs)

        return (
            jsonify(
                {"success": False, "message": "Admin or Team Admin access required"}
            ),
            403,
        )

    return decorated_function


def is_system_admin(user):
    """Check if user is system administrator"""
    return "GOD" in (user.get_permissions() or [])


def is_team_admin(user):
    """Check if user is RFPO admin or system admin"""
    user_permissions = user.get_permissions() or []
    return "RFPO_ADMIN" in user_permissions or "GOD" in user_permissions


def is_limited_admin(user):
    """Check if user has any admin privileges"""
    user_permissions = user.get_permissions() or []
    return any(perm in user_permissions for perm in ["RFPO_USER", "RFPO_ADMIN", "GOD"])


def format_response(success=True, data=None, message=None, status_code=200):
    """Format standardized API response"""
    response = {"success": success}

    if data is not None:
        response.update(data)

    if message:
        response["message"] = message

    return jsonify(response), status_code


def error_response(e, status_code=500):
    """Return sanitized error response — log details server-side, generic message to client."""
    import logging
    logging.getLogger(__name__).error("Request error: %s", str(e), exc_info=True)
    return jsonify({"success": False, "message": "An internal error occurred"}), status_code


def validate_required_fields(data, required_fields):
    """Validate required fields in request data"""
    missing_fields = []
    for field in required_fields:
        if not data.get(field):
            missing_fields.append(field)

    if missing_fields:
        return f"Missing required fields: {', '.join(missing_fields)}"

    return None
