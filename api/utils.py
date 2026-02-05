"""
API Utilities
Shared decorators and helper functions for API routes
"""

from functools import wraps
from flask import request, jsonify
import jwt
import os
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import User

# JWT Configuration
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret-change-in-production")


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
    """Decorator to require admin or team admin privileges"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(request, "current_user") or not request.current_user:
            return (
                jsonify({"success": False, "message": "Authentication required"}),
                401,
            )

        user_permissions = request.current_user.get_permissions() or []
        if not any(perm in user_permissions for perm in ["GOD", "RFPO_ADMIN"]):
            return (
                jsonify(
                    {"success": False, "message": "Admin or RFPO Admin access required"}
                ),
                403,
            )

        return f(*args, **kwargs)

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


def validate_required_fields(data, required_fields):
    """Validate required fields in request data"""
    missing_fields = []
    for field in required_fields:
        if not data.get(field):
            missing_fields.append(field)

    if missing_fields:
        return f"Missing required fields: {', '.join(missing_fields)}"

    return None
