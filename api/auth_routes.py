"""
Authentication API Routes
Centralized authentication endpoints for both user app and admin panel
"""

from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
import jwt
import os
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, User

auth_api = Blueprint("auth_api", __name__, url_prefix="/api/auth")

# JWT Configuration
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret-change-in-production")


@auth_api.route("/login", methods=["POST"])
def login():
    """User login endpoint"""
    try:
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

        # Debug logging
        print(f"DEBUG: Login attempt for email: {username}")
        print(f"DEBUG: Total users in database: {User.query.count()}")
        all_users = User.query.all()
        print(f"DEBUG: All user emails: {[u.email for u in all_users]}")
        print(f"DEBUG: User found: {user is not None}")
        if user:
            print(f"DEBUG: User active: {user.active}")
            password_valid = check_password_hash(user.password_hash, password)
            print(f"DEBUG: Password valid: {password_valid}")

        if not user or not check_password_hash(user.password_hash, password):
            return jsonify({"success": False, "message": "Invalid credentials"}), 401

        # Check if user is active
        if not user.active:
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
