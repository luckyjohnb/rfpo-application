"""
RFPO User-Facing Application
Port: 5000
API Consumer Only - All data operations go through API layer
"""

import os
from datetime import datetime, timedelta
from urllib.parse import urlencode

import jwt as pyjwt
import requests
from flask import Flask, jsonify, redirect, render_template, request, session, url_for, make_response
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

# Import error handling
from error_handlers import register_error_handlers
from logging_config import setup_logging


def create_user_app():
    """Create user-facing Flask application"""
    app = Flask(__name__)

    # Apply ProxyFix for correct IP/proto detection behind Azure Load Balancer
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # Configuration
    _is_production = "postgresql" in os.environ.get("DATABASE_URL", "")
    app.config["SECRET_KEY"] = os.environ.get(
        "USER_APP_SECRET_KEY", "user-app-secret-change-in-production"
    )
    if app.config["SECRET_KEY"] == "user-app-secret-change-in-production":
        if _is_production:
            raise RuntimeError("USER_APP_SECRET_KEY must be set in production (DATABASE_URL contains postgresql)")
        import warnings
        warnings.warn("USER_APP_SECRET_KEY not set! Using insecure default.", stacklevel=1)
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "True").lower() == "true"
    app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))

    # Setup logging
    logger = setup_logging("user_app", log_to_file=True)
    app.logger = logger

    # Register error handlers
    register_error_handlers(app, "user_app")

    # Enable CORS - restrict to known origins in production
    _cors_default = "https://rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io"
    _allowed_origins = os.environ.get("CORS_ORIGINS", _cors_default).split(",")
    CORS(app, origins=_allowed_origins, allow_headers=["Content-Type", "Authorization"])

    # Security headers
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "font-src 'self' https://cdnjs.cloudflare.com; "
            "img-src 'self' data:; "
            "connect-src 'self' " + os.environ.get("API_BASE_URL", "http://127.0.0.1:5003/api").rsplit("/api", 1)[0]
        )
        return response

    # Custom Jinja2 filter for currency formatting
    @app.template_filter("currency")
    def format_currency(value):
        """Format a number as currency with commas and 2 decimal places"""
        if value is None:
            return "$0.00"
        try:
            float_value = float(value)
            return f"${float_value:,.2f}"
        except (ValueError, TypeError):
            return "$0.00"

    # API Configuration
    API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:5003/api")
    ADMIN_API_URL = os.environ.get("ADMIN_API_URL", "http://127.0.0.1:5111/api")
    INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")

    # Context processor — inject nav context into every template
    @app.context_processor
    def inject_nav_context():
        """Provide role-based navigation context to all templates (cached in session)."""
        nav = {"is_admin": False, "is_approver": False, "show_rfpo_nav": False}
        if "auth_token" not in session:
            return {"nav": nav}

        # Use cached nav from session if available
        if "nav_context" in session:
            return {"nav": session["nav_context"]}

        try:
            resp = make_api_request("/auth/verify")
            if resp.get("authenticated"):
                roles = resp.get("user", {}).get("roles", [])
                is_admin = "RFPO_ADMIN" in roles or "GOD" in roles
                is_approver = resp.get("user", {}).get("is_approver", False)
                nav["is_admin"] = is_admin
                nav["is_approver"] = is_approver
                nav["show_rfpo_nav"] = is_admin or is_approver
                session["nav_context"] = nav
        except Exception:
            pass
        return {"nav": nav}

    def _require_session_token(f):
        """Decorator to reject proxy requests without a session auth_token."""
        from functools import wraps
        @wraps(f)
        def decorated(*args, **kwargs):
            if "auth_token" not in session:
                return jsonify({"authenticated": False, "message": "No token"}), 401
            return f(*args, **kwargs)
        return decorated

    # Helper function to make API calls
    def make_api_request(endpoint, method="GET", data=None, use_admin_api=False, extra_headers=None):
        """Make API request with authentication"""
        base_url = ADMIN_API_URL if use_admin_api else API_BASE_URL
        url = f"{base_url}{endpoint}"

        headers = {"Content-Type": "application/json"}
        if extra_headers:
            headers.update(extra_headers)

        # Add auth token if available
        if "auth_token" in session:
            headers["Authorization"] = f"Bearer {session['auth_token']}"

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=10)
            elif method == "POST":
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == "PUT":
                response = requests.put(url, json=data, headers=headers, timeout=10)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, timeout=10)
            else:
                return {"success": False, "message": "Unsupported method"}

            if not response.content:
                return {"success": True}
            try:
                return response.json()
            except ValueError:
                return {"success": False, "message": f"API returned non-JSON response (HTTP {response.status_code})"}

        except requests.exceptions.RequestException as e:
            app.logger.error(f"API request failed for {endpoint}: {e}")
            return {"success": False, "message": "API service unavailable"}

    # Routes
    @app.route("/")
    def landing():
        """Landing page"""
        return render_template("app/landing.html")

    @app.route("/login")
    def login_page():
        """Login page"""
        from auth_saml import is_saml_enabled

        return render_template("app/login.html", saml_enabled=is_saml_enabled())

    @app.route("/dashboard")
    def dashboard():
        """Main dashboard"""
        if "auth_token" not in session:
            return redirect(url_for("login_page"))

        # Get user info
        user_info = make_api_request("/auth/verify")
        if not user_info.get("authenticated"):
            session.pop("auth_token", None)
            return redirect(url_for("login_page"))

        # Check if this is first login (user needs to change password)
        user_profile = make_api_request("/users/profile")
        if user_profile.get("success"):
            user_data = user_profile["user"]

            # More robust first-time login detection
            last_visit = user_data.get("last_visit")
            created_at = user_data.get("created_at")

            # First login if:
            # 1. No last_visit recorded, OR
            # 2. last_visit is exactly the same as created_at (never updated after creation)
            if not last_visit or (
                last_visit and created_at and last_visit == created_at
            ):
                # First time login - redirect to password reset page
                return redirect(url_for("first_login_password_reset"))

        # Get recent RFPOs
        rfpos_response = make_api_request("/rfpos")
        recent_rfpos = (
            rfpos_response.get("rfpos", []) if rfpos_response.get("success") else []
        )

        # Get user's teams
        teams_response = make_api_request("/teams")
        user_teams = (
            teams_response.get("teams", []) if teams_response.get("success") else []
        )

        # Get user permissions summary to determine access levels
        permissions_response = make_api_request("/users/permissions-summary")
        user_permissions = (
            permissions_response.get("permissions_summary", {})
            if permissions_response.get("success")
            else {}
        )

        # Get approver status
        approver_response = make_api_request("/users/approver-status")
        approver_info = approver_response if approver_response.get("success") else {}

        # Determine user access level
        user_data = user_info.get("user", {})
        is_rfpo_user = "RFPO_USER" in user_data.get("roles", [])
        is_rfpo_admin = "RFPO_ADMIN" in user_data.get(
            "roles", []
        ) or "GOD" in user_data.get("roles", [])
        is_approver = approver_info.get("is_approver", False)

        # Determine dashboard type
        if is_rfpo_admin:
            dashboard_type = "admin"
        elif is_rfpo_user and is_approver:
            dashboard_type = "approver"
        elif is_rfpo_user:
            dashboard_type = "profile_only"
        else:
            dashboard_type = "no_access"

        # The dashboard will load user-specific data via JavaScript based on user type
        # This keeps the server-side logic simple and leverages existing API endpoints

        return render_template(
            "app/dashboard.html",
            user=user_info.get("user"),
            recent_rfpos=recent_rfpos,
            teams=user_teams,
            user_permissions=user_permissions,
            dashboard_type=dashboard_type,
            is_approver=is_approver,
        )

    @app.route("/rfpos")
    def rfpos_list():
        """RFPOs list page"""
        if "auth_token" not in session:
            return redirect(url_for("login_page"))

        return render_template("app/rfpos.html")

    @app.route("/rfpos/create")
    def rfpo_create():
        """Create RFPO - Stage 1: Select Consortium & Project"""
        if "auth_token" not in session:
            return redirect(url_for("login_page"))

        # Only admins can create RFPOs
        user_info = make_api_request("/auth/verify")
        if user_info.get("authenticated"):
            roles = user_info.get("user", {}).get("roles", [])
            if "RFPO_ADMIN" not in roles and "GOD" not in roles:
                return redirect(url_for("dashboard"))

        # Get consortiums for dropdown
        consortiums_response = make_api_request("/consortiums")
        consortiums = (
            consortiums_response.get("consortiums", [])
            if consortiums_response.get("success") else []
        )

        return render_template(
            "app/rfpo_create_stage1.html",
            consortiums=consortiums,
        )

    @app.route("/rfpos/create/details")
    def rfpo_create_details():
        """Create RFPO - Stage 2: RFPO Details"""
        if "auth_token" not in session:
            return redirect(url_for("login_page"))

        # Only admins can create RFPOs
        user_info = make_api_request("/auth/verify")
        if user_info.get("authenticated"):
            roles = user_info.get("user", {}).get("roles", [])
            if "RFPO_ADMIN" not in roles and "GOD" not in roles:
                return redirect(url_for("dashboard"))

        # Validate required query params from stage 1
        consortium_id = request.args.get("consortium_id")
        project_id = request.args.get("project_id")
        if not consortium_id or not project_id:
            return redirect(url_for("rfpo_create"))

        # Fetch consortium and project details
        consortiums_resp = make_api_request("/consortiums")
        consortium = None
        if consortiums_resp.get("success"):
            for c in consortiums_resp.get("consortiums", []):
                if c.get("consort_id") == consortium_id:
                    consortium = c
                    break

        projects_resp = make_api_request(
            f"/projects/{consortium_id}"
        )
        project = None
        projects = (
            projects_resp.get("projects", [])
            if projects_resp.get("success")
            else projects_resp if isinstance(projects_resp, list)
            else []
        )
        for p in projects:
            if str(p.get("id")) == str(project_id):
                project = p
                break

        if not consortium or not project:
            return redirect(url_for("rfpo_create"))

        # Wrap dicts as SimpleNamespace for template dot access
        from types import SimpleNamespace
        consortium_obj = SimpleNamespace(**consortium)
        project_obj = SimpleNamespace(**project)

        # Get teams and vendors for dropdowns
        teams_response = make_api_request("/teams")
        teams = (
            teams_response.get("teams", [])
            if teams_response.get("success") else []
        )

        vendors_response = make_api_request("/vendors")
        vendors = (
            vendors_response.get("vendors", [])
            if vendors_response.get("success") else []
        )

        # Determine default team from project
        default_team = None
        team_record_id = project.get("team_record_id")
        if team_record_id:
            for t in teams:
                if t.get("record_id") == team_record_id:
                    default_team = t
                    break

        return render_template(
            "app/rfpo_create_stage2.html",
            consortium=consortium_obj,
            project=project_obj,
            teams=teams,
            vendors=vendors,
            default_team=default_team,
        )

    @app.route("/rfpos/<int:rfpo_id>")
    def rfpo_detail(rfpo_id):
        """RFPO detail page"""
        if "auth_token" not in session:
            return redirect(url_for("login_page"))

        # Get user info for role-based UI
        user_info = make_api_request("/auth/verify")
        is_admin = False
        if user_info.get("authenticated"):
            roles = user_info.get("user", {}).get("roles", [])
            is_admin = "RFPO_ADMIN" in roles or "GOD" in roles

        return render_template("app/rfpo_detail.html", rfpo_id=rfpo_id, is_admin=is_admin)

    @app.route("/teams")
    def teams_list():
        """Teams list page"""
        if "auth_token" not in session:
            return redirect(url_for("login_page"))

        return render_template("app/teams.html")

    @app.route("/teams/<int:team_id>")
    def team_detail(team_id):
        """Team detail page"""
        if "auth_token" not in session:
            return redirect(url_for("login_page"))

        return render_template("app/team_detail.html", team_id=team_id)

    @app.route("/profile")
    def profile():
        """User profile page"""
        if "auth_token" not in session:
            return redirect(url_for("login_page"))

        return render_template("app/profile.html")

    @app.route("/approvals")
    def approvals():
        """Approval queue page for approvers"""
        if "auth_token" not in session:
            return redirect(url_for("login_page"))

        is_admin = False
        user_info = session.get("user_info", {})
        roles = user_info.get("permissions", [])
        if roles:
            is_admin = "RFPO_ADMIN" in roles or "GOD" in roles

        return render_template("app/approvals.html", is_admin=is_admin)

    @app.route("/first-login-password-reset")
    def first_login_password_reset():
        """First login password reset page - forces password change"""
        if "auth_token" not in session:
            return redirect(url_for("login_page"))

        return render_template("app/first_login_password_reset.html")

    # API Proxy Routes (for frontend AJAX calls)
    @app.route("/api/auth/login", methods=["POST"])
    def api_login():
        """Login API proxy"""
        data = request.get_json()
        response = make_api_request("/auth/login", "POST", data)

        if response.get("success") and response.get("token"):
            # Rotate session to prevent fixation
            session.clear()
            session.permanent = True
            session["auth_token"] = response["token"]
            session["user"] = response["user"]
            # Cache nav context from login response
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

    @app.route("/api/auth/logout", methods=["POST"])
    def api_logout():
        """Logout API proxy"""
        session.clear()
        return jsonify({"success": True, "message": "Logged out successfully"})

    @app.route("/api/auth/verify", methods=["GET"])
    def api_verify():
        """Verify auth API proxy"""
        if "auth_token" not in session:
            return jsonify({"authenticated": False, "message": "No token"}), 401

        response = make_api_request("/auth/verify")
        return jsonify(response)

    @app.route("/api/rfpos", methods=["GET", "POST"])
    def api_rfpos():
        """RFPOs API proxy"""
        if request.method == "GET":
            # Forward query parameters
            params = urlencode(request.args.to_dict(flat=False), doseq=True)
            endpoint = f"/rfpos?{params}" if params else "/rfpos"
            response = make_api_request(endpoint)
        else:
            data = request.get_json()
            response = make_api_request("/rfpos", "POST", data)

        return jsonify(response)

    @app.route("/api/rfpos/<int:rfpo_id>", methods=["GET", "PUT", "DELETE"])
    def api_rfpo_detail(rfpo_id):
        """RFPO detail API proxy"""
        if request.method == "GET":
            response = make_api_request(f"/rfpos/{rfpo_id}")
        elif request.method == "PUT":
            data = request.get_json()
            response = make_api_request(f"/rfpos/{rfpo_id}", "PUT", data)
        else:  # DELETE
            response = make_api_request(f"/rfpos/{rfpo_id}", "DELETE")

        return jsonify(response)

    @app.route("/api/teams", methods=["GET"])
    def api_teams():
        """Teams API proxy"""
        params = urlencode(request.args.to_dict(flat=False), doseq=True)
        endpoint = f"/teams?{params}" if params else "/teams"
        response = make_api_request(endpoint)
        return jsonify(response)

    @app.route("/api/teams/<int:team_id>", methods=["GET"])
    def api_team_detail(team_id):
        """Team detail API proxy"""
        response = make_api_request(f"/teams/{team_id}")
        return jsonify(response)

    @app.route("/api/consortiums", methods=["GET"])
    @_require_session_token
    def api_consortiums():
        """Consortiums API proxy"""
        response = make_api_request("/consortiums")
        return jsonify(response)

    @app.route("/api/projects/<consortium_id>", methods=["GET"])
    @_require_session_token
    def api_projects_for_consortium(consortium_id):
        """Projects for consortium API proxy"""
        response = make_api_request(
            f"/projects/{consortium_id}"
        )
        return jsonify(response)

    @app.route("/api/vendors", methods=["GET"])
    @_require_session_token
    def api_vendors():
        """Vendors API proxy"""
        response = make_api_request("/vendors")
        return jsonify(response)

    @app.route("/api/vendor-sites/<int:vendor_id>", methods=["GET"])
    @_require_session_token
    def api_vendor_sites(vendor_id):
        """Vendor sites API proxy"""
        response = make_api_request(
            f"/vendor-sites/{vendor_id}"
        )
        return jsonify(response)

    @app.route("/api/users/profile", methods=["GET"])
    def api_user_profile():
        """User profile API proxy"""
        response = make_api_request("/users/profile")
        return jsonify(response)

    @app.route("/api/users/profile", methods=["PUT"])
    def api_update_profile():
        """Update user profile API proxy"""
        data = request.get_json()
        response = make_api_request("/users/profile", "PUT", data)
        return jsonify(response)

    @app.route("/api/auth/change-password", methods=["POST"])
    def api_change_password():
        """Change password API proxy"""
        data = request.get_json()
        response = make_api_request("/auth/change-password", "POST", data)
        return jsonify(response)

    @app.route("/api/users/permissions-summary", methods=["GET"])
    def api_user_permissions_summary():
        """User permissions summary API proxy"""
        response = make_api_request("/users/permissions-summary")
        return jsonify(response)

    @app.route("/api/users/approver-status", methods=["GET"])
    def api_user_approver_status():
        """User approver status API proxy"""
        response = make_api_request("/users/approver-status")
        return jsonify(response)

    @app.route("/api/users/approver-rfpos", methods=["GET"])
    def api_user_approver_rfpos():
        """User approver RFPOs API proxy"""
        response = make_api_request("/users/approver-rfpos")
        return jsonify(response)

    @app.route("/api/users/approval-action/<action_id>", methods=["POST"])
    def api_take_approval_action(action_id):
        """Take approval action API proxy"""
        data = request.get_json()
        response = make_api_request(f"/users/approval-action/{action_id}", "POST", data)
        return jsonify(response)

    @app.route("/api/users/bulk-approval", methods=["POST"])
    def api_bulk_approval():
        """Bulk approval action API proxy"""
        data = request.get_json()
        response = make_api_request("/users/bulk-approval", "POST", data)
        return jsonify(response)

    @app.route("/api/rfpos/<int:rfpo_id>/submit-for-approval", methods=["POST"])
    def api_submit_for_approval(rfpo_id):
        """Submit RFPO for approval API proxy"""
        response = make_api_request(f"/rfpos/{rfpo_id}/submit-for-approval", "POST")
        return jsonify(response)

    @app.route("/api/rfpos/<int:rfpo_id>/withdraw-approval", methods=["POST"])
    def api_withdraw_approval(rfpo_id):
        """Withdraw RFPO from approval process API proxy"""
        data = request.get_json() if request.is_json else {}
        response = make_api_request(f"/rfpos/{rfpo_id}/withdraw-approval", "POST", data)
        return jsonify(response)

    @app.route("/api/users/reassign-approval/<action_id>", methods=["POST"])
    def api_reassign_approval(action_id):
        """Reassign approval action to a different user API proxy"""
        data = request.get_json()
        response = make_api_request(f"/users/reassign-approval/{action_id}", "POST", data)
        return jsonify(response)

    @app.route("/api/users/list", methods=["GET"])
    def api_list_users():
        """List active users API proxy (admin only)"""
        response = make_api_request("/users")
        return jsonify(response)

    @app.route("/api/rfpos/<int:rfpo_id>/line-items", methods=["GET", "POST"])
    def api_rfpo_line_items(rfpo_id):
        """RFPO line items API proxy"""
        if request.method == "POST":
            data = request.get_json()
            response = make_api_request(f"/rfpos/{rfpo_id}/line-items", "POST", data)
        else:
            response = make_api_request(f"/rfpos/{rfpo_id}/line-items")
        return jsonify(response)

    @app.route("/api/rfpos/<int:rfpo_id>/line-items/<int:line_item_id>", methods=["PUT", "DELETE"])
    def api_rfpo_line_item_detail(rfpo_id, line_item_id):
        """RFPO line item detail API proxy"""
        if request.method == "PUT":
            data = request.get_json()
            response = make_api_request(f"/rfpos/{rfpo_id}/line-items/{line_item_id}", "PUT", data)
        else:  # DELETE
            response = make_api_request(f"/rfpos/{rfpo_id}/line-items/{line_item_id}", "DELETE")
        return jsonify(response)

    @app.route("/api/rfpos/<int:rfpo_id>/files/upload", methods=["POST"])
    def api_rfpo_upload_file(rfpo_id):
        """RFPO file upload proxy - forwards multipart form data to API"""
        if "auth_token" not in session:
            return jsonify({"success": False, "message": "Not authenticated"}), 401

        url = f"{API_BASE_URL}/rfpos/{rfpo_id}/files/upload"
        headers = {"Authorization": f"Bearer {session['auth_token']}"}

        try:
            # Forward the multipart form data as-is
            files = {}
            if "file" in request.files:
                f = request.files["file"]
                files["file"] = (f.filename, f.stream, f.content_type)

            form_data = {
                "document_type": request.form.get("document_type", ""),
                "description": request.form.get("description", ""),
            }

            resp = requests.post(url, headers=headers, files=files, data=form_data, timeout=30)
            return jsonify(resp.json()), resp.status_code
        except requests.exceptions.RequestException as e:
            return jsonify({"success": False, "message": f"API Error: {str(e)}"}), 500

    @app.route("/api/rfpos/<int:rfpo_id>/files/<file_id>/view", methods=["GET"])
    def api_rfpo_view_file(rfpo_id, file_id):
        """RFPO file view proxy - streams file content from API"""
        if "auth_token" not in session:
            return redirect(url_for("login_page"))

        url = f"{API_BASE_URL}/rfpos/{rfpo_id}/files/{file_id}/view"
        headers = {"Authorization": f"Bearer {session['auth_token']}"}

        try:
            resp = requests.get(url, headers=headers, stream=True, timeout=30)
            if resp.status_code != 200:
                return jsonify({"success": False, "message": "File not found"}), resp.status_code

            from flask import Response
            return Response(
                resp.iter_content(chunk_size=8192),
                content_type=resp.headers.get("Content-Type", "application/octet-stream"),
                headers={
                    "Content-Disposition": resp.headers.get("Content-Disposition", ""),
                },
            )
        except requests.exceptions.RequestException as e:
            return jsonify({"success": False, "message": f"API Error: {str(e)}"}), 500

    @app.route("/api/rfpos/<int:rfpo_id>/files/<file_id>", methods=["DELETE"])
    def api_rfpo_delete_file(rfpo_id, file_id):
        """RFPO file delete proxy"""
        response = make_api_request(f"/rfpos/{rfpo_id}/files/{file_id}", "DELETE")
        return jsonify(response)

    @app.route("/api/rfpos/doc-types", methods=["GET"])
    @_require_session_token
    def api_doc_types():
        """Document types API proxy"""
        response = make_api_request("/rfpos/doc-types")
        return jsonify(response)

    @app.route("/api/rfpos/<int:rfpo_id>/rendered-view", methods=["GET"])
    def api_rfpo_rendered_view(rfpo_id):
        """RFPO rendered view API proxy"""
        response = make_api_request(f"/rfpos/{rfpo_id}/rendered-view")
        return jsonify(response)

    @app.route("/rfpos/<int:rfpo_id>/preview")
    def rfpo_preview(rfpo_id):
        """Render RFPO preview HTML (same as admin panel)"""
        if "auth_token" not in session:
            return redirect(url_for("login_page"))

        # Get RFPO data from API
        rfpo_response = make_api_request(f"/rfpos/{rfpo_id}")
        if not rfpo_response.get("success"):
            return (
                f"Error loading RFPO: {rfpo_response.get('message', 'Unknown error')}",
                404,
            )

        rfpo = rfpo_response["rfpo"]

        # Get related data from API
        project = None
        consortium = None
        vendor = None
        vendor_site = None
        requestor = None

        # Get project info
        if rfpo.get("project_id"):
            projects_response = make_api_request("/projects")
            if projects_response.get("success"):
                for p in projects_response.get("projects", []):
                    if p.get("project_id") == rfpo["project_id"]:
                        project = p
                        break

        # Get consortium info
        if rfpo.get("consortium_id"):
            consortiums_response = make_api_request("/consortiums")
            if consortiums_response.get("success"):
                for c in consortiums_response.get("consortiums", []):
                    if c.get("consort_id") == rfpo["consortium_id"]:
                        consortium = c
                        break

        # Get vendor info
        if rfpo.get("vendor_id"):
            vendors_response = make_api_request("/vendors")
            if vendors_response.get("success"):
                for v in vendors_response.get("vendors", []):
                    if v.get("id") == rfpo["vendor_id"]:
                        vendor = v
                        break

        # Get vendor site info
        if rfpo.get("vendor_site_id") and vendor:
            vendor_sites_response = make_api_request(f'/vendor-sites/{vendor["id"]}')
            if vendor_sites_response:
                for site in vendor_sites_response:
                    if site.get("id") == rfpo["vendor_site_id"]:
                        vendor_site = site
                        break

        # Create simple namespace objects to match template expectations
        from datetime import datetime
        from types import SimpleNamespace

        # Convert date strings to datetime objects for template compatibility
        if rfpo.get("created_at"):
            try:
                if isinstance(rfpo["created_at"], str):
                    rfpo["created_at"] = datetime.fromisoformat(
                        rfpo["created_at"].replace("Z", "+00:00")
                    )
            except (ValueError, TypeError):
                rfpo["created_at"] = None

        if rfpo.get("delivery_date"):
            try:
                if isinstance(rfpo["delivery_date"], str):
                    rfpo["delivery_date"] = datetime.fromisoformat(
                        rfpo["delivery_date"].replace("Z", "+00:00")
                    ).date()
            except (ValueError, TypeError):
                rfpo["delivery_date"] = None

        rfpo_obj = SimpleNamespace(**rfpo)
        project_obj = SimpleNamespace(**project) if project else None
        consortium_obj = SimpleNamespace(**consortium) if consortium else None
        vendor_obj = SimpleNamespace(**vendor) if vendor else None
        vendor_site_obj = SimpleNamespace(**vendor_site) if vendor_site else None

        # Add line_items as a list of SimpleNamespace objects
        if hasattr(rfpo_obj, "line_items") and rfpo_obj.line_items:
            rfpo_obj.line_items = [
                SimpleNamespace(**item) for item in rfpo_obj.line_items
            ]
        else:
            rfpo_obj.line_items = []

        # Add helper methods to rfpo_obj
        def get_calculated_cost_share_amount():
            if hasattr(rfpo_obj, "cost_share_amount") and hasattr(rfpo_obj, "subtotal"):
                if rfpo_obj.cost_share_type == "percent":
                    return (
                        float(rfpo_obj.subtotal or 0)
                        * float(rfpo_obj.cost_share_amount or 0)
                    ) / 100
                else:
                    return float(rfpo_obj.cost_share_amount or 0)
            return 0.0

        def get_calculated_total_amount():
            subtotal = float(rfpo_obj.subtotal or 0)
            cost_share = get_calculated_cost_share_amount()
            return subtotal - cost_share

        rfpo_obj.get_calculated_cost_share_amount = get_calculated_cost_share_amount
        rfpo_obj.get_calculated_total_amount = get_calculated_total_amount

        # Add helper method to requestor
        if requestor:
            requestor_obj = SimpleNamespace(**requestor)
            requestor_obj.get_display_name = lambda: requestor.get(
                "fullname", requestor.get("display_name", "Unknown")
            )
        else:
            requestor_obj = None

        return render_template(
            "app/rfpo_preview.html",
            rfpo=rfpo_obj,
            project=project_obj,
            consortium=consortium_obj,
            vendor=vendor_obj,
            vendor_site=vendor_site_obj,
            requestor=requestor_obj,
        )

    # ─── SAML SSO Routes ─────────────────────────────────────────────────

    @app.route("/auth/login-microsoft")
    def saml_login():
        """Initiate SAML SSO flow — redirects to Microsoft/Entra ID login."""
        from auth_saml import is_saml_enabled, init_saml_auth

        if not is_saml_enabled():
            return redirect(url_for("login_page"))

        auth = init_saml_auth(request)
        # RelayState carries the intended destination after login
        return_to = request.args.get("next", url_for("dashboard"))
        sso_url = auth.login(return_to=return_to)
        return redirect(sso_url)

    @app.route("/saml/acs", methods=["GET", "POST"])
    def saml_acs():
        """Assertion Consumer Service — receives and validates SAML Response from IdP."""
        from auth_saml import is_saml_enabled, init_saml_auth, extract_user_attributes, map_roles_to_permissions

        if request.method == "GET":
            return redirect(url_for("login_page"))

        if not is_saml_enabled():
            return "SAML SSO is not enabled", 403

        auth = init_saml_auth(request)
        auth.process_response()
        errors = auth.get_errors()

        if errors:
            error_reason = auth.get_last_error_reason()
            logger.error(f"SAML ACS validation failed: {errors} — {error_reason}")
            return render_template(
                "app/error.html",
                error_code=401,
                error_message="SSO authentication failed. Please contact your administrator.",
            ), 401

        if not auth.is_authenticated():
            return render_template(
                "app/error.html",
                error_code=401,
                error_message="Authentication was not completed.",
            ), 401

        # Extract user attributes from the SAML assertion
        user_attrs = extract_user_attributes(auth)
        email = user_attrs.get("email")

        if not email:
            logger.error("SAML assertion missing email/NameID")
            return render_template(
                "app/error.html",
                error_code=400,
                error_message="SSO response did not include an email address.",
            ), 400

        # Match to local RFPO user by email (D3: block if not pre-provisioned)
        internal_headers = {"X-Internal-API-Key": INTERNAL_API_KEY} if INTERNAL_API_KEY else {}
        match_response = make_api_request("/auth/saml-match", "POST", {
            "email": email,
            "entra_roles": user_attrs.get("roles", []),
            "first_name": user_attrs.get("first_name", ""),
            "last_name": user_attrs.get("last_name", ""),
            "name_id": user_attrs.get("name_id", ""),
        }, extra_headers=internal_headers)

        if not match_response.get("success"):
            message = match_response.get("message", "Your account has not been set up in RFPO. Contact your USCAR administrator.")
            logger.warning(f"SAML login blocked for {email}: {message}")
            return render_template(
                "app/error.html",
                error_code=403,
                error_message=message,
            ), 403

        # Store JWT in session (same as password-based login)
        session["auth_token"] = match_response["token"]
        session["user"] = match_response["user"]
        session["auth_method"] = "sso"
        session["saml_session_index"] = user_attrs.get("session_index")

        # Redirect to intended destination or dashboard
        relay_state = request.form.get("RelayState", "")
        if relay_state and relay_state != url_for("saml_login") and not relay_state.startswith("http"):
            return redirect(relay_state)
        return redirect(url_for("dashboard"))

    @app.route("/saml/sls", methods=["GET", "POST"])
    def saml_sls():
        """Single Logout Service — handles logout initiated by IdP."""
        from auth_saml import is_saml_enabled, init_saml_auth

        if not is_saml_enabled():
            return redirect(url_for("login_page"))

        auth = init_saml_auth(request)

        def delete_session():
            session.pop("auth_token", None)
            session.pop("user", None)
            session.pop("auth_method", None)
            session.pop("saml_session_index", None)

        url = auth.process_slo(delete_session_cb=delete_session)
        errors = auth.get_errors()

        if errors:
            logger.error(f"SAML SLS error: {errors}")

        if url:
            return redirect(url)
        return redirect(url_for("login_page"))

    @app.route("/saml/metadata")
    def saml_metadata():
        """Serve SP metadata XML — useful for IT when configuring the Enterprise Application."""
        from auth_saml import is_saml_enabled, init_saml_auth

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

    # Health check
    @app.route("/health")
    def health_check():
        """Health check endpoint"""
        resp = jsonify(
            {
                "status": "healthy",
                "service": "RFPO User App",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0",
            }
        )
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return (
            render_template(
                "app/error.html", error_code=404, error_message="Page not found"
            ),
            404,
        )

    @app.errorhandler(500)
    def internal_error(error):
        return (
            render_template(
                "app/error.html", error_code=500, error_message="Internal server error"
            ),
            500,
        )

    return app


# Create app instance
app = create_user_app()

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 RFPO USER APPLICATION STARTING")
    print("=" * 60)
    print(f"🌐 Server: http://127.0.0.1:5000")
    print(f"🔍 Health Check: http://127.0.0.1:5000/health")
    print(f"📋 Dashboard: http://127.0.0.1:5000/dashboard")
    print(f"🔐 Login: http://127.0.0.1:5000/login")
    print("=" * 60)

    app.run(debug=os.environ.get("FLASK_ENV") == "development", host="0.0.0.0", port=5000)
