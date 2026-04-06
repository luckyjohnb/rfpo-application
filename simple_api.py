#!/usr/bin/env python3
"""
Simple RFPO API Server
Just Flask + Database connection - nothing fancy
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
import jwt
import logging
from datetime import datetime, timedelta
import os
import time
import threading
from collections import defaultdict

# Import our models
from models import (
    db,
    User,
    Team,
    UserTeam,
    RFPO,
    RFPOLineItem,
    Consortium,
    Project,
    Vendor,
    VendorSite,
    UploadedFile,
    List,
)

# Import approval and audit models at top level
from models import (
    RFPOApprovalWorkflow,
    RFPOApprovalStage,
    RFPOApprovalStep,
    RFPOApprovalInstance,
    RFPOApprovalAction,
    AuditLog,
)

# Import admin routes
import sys

sys.path.append("api")
try:
    from admin_routes import admin_api

    ADMIN_ROUTES_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Admin routes not available: {e}")
    ADMIN_ROUTES_AVAILABLE = False

# User routes are handled directly in this file
USER_ROUTES_AVAILABLE = False

# Create Flask app with template folder
app = Flask(__name__, template_folder="templates")

# Apply ProxyFix for correct IP/proto detection behind Azure Load Balancer
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configuration
_is_production = "postgresql" in os.environ.get("DATABASE_URL", "")
app.config["SECRET_KEY"] = os.environ.get("API_SECRET_KEY", "simple-api-secret")
if app.config["SECRET_KEY"] == "simple-api-secret":
    if _is_production:
        raise RuntimeError("API_SECRET_KEY must be set in production (DATABASE_URL contains postgresql)")
    import warnings
    warnings.warn("API_SECRET_KEY not set! Using insecure default.", stacklevel=1)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", f'sqlite:///{os.path.abspath("instance/rfpo_admin.db")}'
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_size": 20,
    "pool_recycle": 3600,
    "pool_pre_ping": True,
}

# Initialize database
db.init_app(app)


@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()


# Setup structured logging and error handlers
try:
    from logging_config import setup_logging
    from error_handlers import register_error_handlers
    logger = setup_logging("simple_api", log_to_file=True)
    app.logger = logger
    register_error_handlers(app, "simple_api")
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    app.logger.warning("logging_config/error_handlers not available, using basic logging")

# Enable CORS - restrict to known origins in production
_cors_default = (
    "https://rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io,"
    "https://rfpo-admin.livelyforest-d06a98a0.eastus.azurecontainerapps.io"
)
_allowed_origins = os.environ.get("CORS_ORIGINS", _cors_default).split(",")
CORS(app, origins=_allowed_origins, allow_headers=["Content-Type", "Authorization"])

# Security headers
@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def _error_response(e, status_code=500):
    """Return sanitized error response — log details server-side, generic message to client."""
    app.logger.error("Request error: %s", str(e), exc_info=True)
    return jsonify({"success": False, "message": "An internal error occurred"}), status_code

# Register admin routes if available
if ADMIN_ROUTES_AVAILABLE:
    app.register_blueprint(admin_api)
    app.logger.info("Admin API routes registered")

# User routes are handled directly in this file (not as blueprint)

# JWT Secret - MUST be set via environment variable in production
JWT_SECRET = os.environ.get("JWT_SECRET_KEY", "simple-jwt-secret")
if JWT_SECRET == "simple-jwt-secret":
    if _is_production:
        raise RuntimeError("JWT_SECRET_KEY must be set in production (DATABASE_URL contains postgresql)")
    import warnings
    warnings.warn("JWT_SECRET_KEY not set! Using insecure default. Set JWT_SECRET_KEY env var.", stacklevel=1)

# Internal API key for service-to-service calls (SAML match, etc.)
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")
if not INTERNAL_API_KEY and _is_production:
    import warnings
    warnings.warn("INTERNAL_API_KEY not set. SAML match endpoint will reject requests.", stacklevel=1)

# --- Rate limiting for login (DB-backed via AuditLog) ---
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 300  # 5 minutes

# In-memory fallback only used if DB query fails
_login_attempts_fallback = defaultdict(list)
_login_lock = threading.Lock()


def _is_rate_limited(ip_address: str) -> bool:
    """Check if IP has exceeded login attempt limit using AuditLog (persistent across restarts)."""
    try:
        cutoff = datetime.utcnow() - timedelta(seconds=_LOGIN_WINDOW_SECONDS)
        count = AuditLog.query.filter(
            AuditLog.action == "failed_login",
            AuditLog.ip_address == ip_address,
            AuditLog.timestamp >= cutoff,
        ).count()
        return count >= _LOGIN_MAX_ATTEMPTS
    except Exception:
        # Fallback to in-memory if DB unavailable
        now = time.time()
        with _login_lock:
            _login_attempts_fallback[ip_address] = [
                ts for ts in _login_attempts_fallback[ip_address]
                if now - ts < _LOGIN_WINDOW_SECONDS
            ]
            return len(_login_attempts_fallback[ip_address]) >= _LOGIN_MAX_ATTEMPTS


def _record_login_attempt(ip_address: str) -> None:
    """Record a failed login attempt to AuditLog for persistent rate limiting."""
    try:
        entry = AuditLog(
            action="failed_login",
            entity_type="auth",
            ip_address=ip_address,
            user_agent=request.headers.get("User-Agent", "")[:512],
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
        # Fallback to in-memory
        with _login_lock:
            _login_attempts_fallback[ip_address].append(time.time())


# Simple authentication decorator
def require_auth(f):
    def wrapper(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token or not token.startswith("Bearer "):
            return jsonify({"error": "No token provided"}), 401

        try:
            token = token[7:]  # Remove 'Bearer '
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            user = User.query.get(payload["user_id"])
            if not user or not user.active:
                return jsonify({"error": "Invalid user"}), 401
            request.current_user = user
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, Exception) as e:
            app.logger.warning(f"Token validation failed: {type(e).__name__}")
            return jsonify({"error": "Invalid token"}), 401

        return f(*args, **kwargs)

    wrapper.__name__ = f.__name__
    return wrapper


def require_admin(f):
    def wrapper(*args, **kwargs):
        if not hasattr(request, "current_user") or not request.current_user:
            return jsonify({"error": "Authentication required"}), 401

        user_permissions = request.current_user.get_permissions() or []
        if "GOD" not in user_permissions:
            return jsonify({"error": "Admin access required"}), 403

        return f(*args, **kwargs)

    wrapper.__name__ = f.__name__
    return wrapper


# Routes
@app.route("/api/health")
def health():
    resp = jsonify({"status": "healthy", "service": "Simple RFPO API"})
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


@app.route("/api/auth/login", methods=["POST"])
def login():
    # Rate limiting
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if _is_rate_limited(client_ip):
        return jsonify({"success": False, "message": "Too many login attempts. Try again later."}), 429

    data = request.get_json()
    email = data.get("username")  # Frontend sends as 'username' but it's email
    password = data.get("password")

    if not email or not password:
        return (
            jsonify({"success": False, "message": "Email and password required"}),
            400,
        )

    # Find user
    user = User.query.filter_by(email=email).first()

    if not user or not user.active:
        _record_login_attempt(client_ip)
        return jsonify({"success": False, "message": "Invalid credentials"}), 401

    # Check password
    if not check_password_hash(user.password_hash, password):
        _record_login_attempt(client_ip)
        return jsonify({"success": False, "message": "Invalid credentials"}), 401

    app.logger.info(f"Login successful: {email}")

    # Create token
    token = jwt.encode(
        {"user_id": user.id, "exp": datetime.utcnow() + timedelta(hours=24)},
        JWT_SECRET,
        algorithm="HS256",
    )

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


@app.route("/api/auth/verify")
@require_auth
def verify():
    user = request.current_user
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


@app.route("/api/teams")
@require_auth
def list_teams():
    user = request.current_user
    teams = Team.query.filter_by(active=True).order_by(Team.name).all()

    # Get user's team memberships in one query
    member_team_ids = set(
        ut.team_id for ut in UserTeam.query.filter_by(user_id=user.id).all()
    )

    # Build consortium lookup
    consortiums = {c.consort_id: c.name for c in Consortium.query.all()}

    # Batch-load member counts and rfpo counts to avoid N+1
    team_ids = [t.id for t in teams]
    member_counts = dict(
        db.session.query(UserTeam.team_id, db.func.count(UserTeam.id))
        .filter(UserTeam.team_id.in_(team_ids))
        .group_by(UserTeam.team_id)
        .all()
    ) if team_ids else {}
    rfpo_counts = dict(
        db.session.query(RFPO.team_id, db.func.count(RFPO.id))
        .filter(RFPO.team_id.in_(team_ids))
        .group_by(RFPO.team_id)
        .all()
    ) if team_ids else {}

    result = []
    for t in teams:
        result.append({
            "id": t.id,
            "name": t.name,
            "abbrev": t.abbrev,
            "description": t.description,
            "consortium_name": consortiums.get(t.consortium_consort_id, "Unknown"),
            "is_member": t.id in member_team_ids,
            "member_count": member_counts.get(t.id, 0),
            "rfpo_count": rfpo_counts.get(t.id, 0),
        })

    return jsonify({"success": True, "teams": result})


@app.route("/api/teams/<int:team_id>")
@require_auth
def get_team_detail(team_id):
    """Get full team details including members and RFPOs"""
    user = request.current_user
    team = Team.query.get(team_id)
    if not team:
        return jsonify({"success": False, "message": "Team not found"}), 404

    # Consortium info
    consortium = Consortium.query.filter_by(consort_id=team.consortium_consort_id).first()

    # Members via UserTeam
    members = []
    for ut in team.team_users:
        if ut.user and ut.user.active:
            members.append({
                "id": ut.user.id,
                "fullname": ut.user.fullname,
                "email": ut.user.email,
                "company": ut.user.company,
                "role": ut.role or "member",
            })

    # Team RFPOs (non-deleted, most recent first)
    rfpos = []
    for r in sorted(
        [r for r in team.rfpos if not r.is_deleted],
        key=lambda x: x.created_at or datetime.min,
        reverse=True,
    ):
        rfpos.append({
            "id": r.id,
            "rfpo_id": r.rfpo_id,
            "title": r.title,
            "status": r.status,
            "total_amount": float(r.total_amount) if r.total_amount else 0,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "created_by": r.created_by,
        })

    # Check membership
    is_member = any(ut.user_id == user.id for ut in team.team_users)

    return jsonify({
        "success": True,
        "team": {
            "id": team.id,
            "name": team.name,
            "abbrev": team.abbrev,
            "description": team.description,
            "active": team.active,
            "created_at": team.created_at.isoformat() if team.created_at else None,
            "consortium": {
                "name": consortium.name if consortium else "Unknown",
                "abbrev": consortium.abbrev if consortium else "",
            } if consortium else None,
            "is_member": is_member,
            "members": members,
            "rfpos": rfpos,
        },
    })


@app.route("/api/auth/change-password", methods=["POST"])
@require_auth
def change_password():
    """Change user password"""
    try:
        data = request.get_json()
        current_password = data.get("current_password")
        new_password = data.get("new_password")

        if not current_password or not new_password:
            return (
                jsonify(
                    {"success": False, "message": "Current and new passwords required"}
                ),
                400,
            )

        user = request.current_user

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

        import re
        if not re.search(r'[A-Z]', new_password):
            return jsonify({"success": False, "message": "Password must contain at least one uppercase letter"}), 400
        if not re.search(r'[a-z]', new_password):
            return jsonify({"success": False, "message": "Password must contain at least one lowercase letter"}), 400
        if not re.search(r'[0-9]', new_password):
            return jsonify({"success": False, "message": "Password must contain at least one number"}), 400
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_password):
            return jsonify({"success": False, "message": "Password must contain at least one special character"}), 400

        # Update password
        from werkzeug.security import generate_password_hash

        user.password_hash = generate_password_hash(new_password)
        user.updated_at = datetime.utcnow()

        # Mark as no longer first-time user by updating last_visit
        user.last_visit = datetime.utcnow()

        db.session.commit()

        # Send password change notification email
        try:
            # Get user's IP address for security notification
            user_ip = request.environ.get(
                "HTTP_X_FORWARDED_FOR", request.environ.get("REMOTE_ADDR", "Unknown")
            )

            # Try to send email notification
            try:
                from email_service import send_password_changed_email

                email_sent = send_password_changed_email(
                    user.email, user.fullname, user_ip
                )
                if email_sent:
                    app.logger.info(f"Password change notification sent to {user.email}")
                else:
                    app.logger.warning(f"Password change notification failed for {user.email}")
            except ImportError:
                app.logger.warning("Email service not available - password change notification not sent")
            except Exception as email_error:
                app.logger.warning(f"Email notification error: {email_error}")
        except Exception as e:
            app.logger.warning(f"Error sending password change notification: {e}")

        return jsonify({"success": True, "message": "Password changed successfully"})

    except Exception as e:
        db.session.rollback()
        return _error_response(e)


@app.route("/api/auth/saml-match", methods=["POST"])
def saml_match():
    """Match a SAML-authenticated user to a local RFPO user and issue JWT."""
    # Validate internal service-to-service API key
    provided_key = request.headers.get("X-Internal-API-Key", "")
    if INTERNAL_API_KEY:
        if not provided_key or provided_key != INTERNAL_API_KEY:
            return jsonify({"success": False, "message": "Unauthorized"}), 403
    elif _is_production:
        # No INTERNAL_API_KEY configured in production — reject all calls
        return jsonify({"success": False, "message": "Endpoint not configured"}), 503

    try:
        data = request.get_json()
        email = data.get("email", "").strip().lower()
        entra_roles = data.get("entra_roles", [])
        name_id = data.get("name_id", "")

        if not email:
            return jsonify({"success": False, "message": "Email is required"}), 400

        from sqlalchemy import func

        user = User.query.filter(func.lower(User.email) == email).first()

        if not user:
            return jsonify({
                "success": False,
                "message": "Your account has not been set up in RFPO. Contact your USCAR administrator.",
            }), 403

        if not user.active:
            return jsonify({
                "success": False,
                "message": "Your RFPO account is not active. Contact your USCAR administrator.",
            }), 403

        # Store Entra NameID on first SSO login
        first_sso = not user.entra_oid
        if name_id and first_sso:
            user.entra_oid = name_id

        # Only apply Entra roles on FIRST SSO login (baseline setup).
        # After that, admin-set permissions take precedence (D7 resolution).
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

        user.last_visit = datetime.utcnow()
        db.session.commit()

        # Issue JWT
        token = jwt.encode(
            {"user_id": user.id, "exp": datetime.utcnow() + timedelta(hours=24)},
            JWT_SECRET,
            algorithm="HS256",
        )

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
            },
        })
    except Exception as e:
        db.session.rollback()
        app.logger.exception(f"SAML match error: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500


@app.route("/api/users/approver-rfpos", methods=["GET"])
@require_auth
def get_approver_rfpos():
    """Get RFPOs with pending approval actions for the current user"""
    try:

        user = request.current_user

        # Find all pending actions assigned to this user (primary approver)
        pending_actions = RFPOApprovalAction.query.filter_by(
            approver_id=user.record_id,
            status="pending",
        ).all()

        # Also find actions where user is backup approver (from instance snapshots)
        all_active_instances = RFPOApprovalInstance.query.filter(
            RFPOApprovalInstance.overall_status.in_(["waiting", "draft"]),
        ).all()

        backup_action_ids = set()
        for inst in all_active_instances:
            try:
                data = inst.get_instance_data()
                for phase in data.get("phases", []):
                    stage = phase.get("stage", {})
                    for step in stage.get("steps", []):
                        if step.get("backup_approver_id") == user.record_id:
                            for act in inst.actions:
                                if (act.status == "pending"
                                        and act.stage_order == stage.get("stage_order")
                                        and act.step_order == step.get("step_order")):
                                    backup_action_ids.add(act.id)
            except Exception:
                continue

        # Merge primary + backup actions
        if backup_action_ids:
            extra_actions = RFPOApprovalAction.query.filter(
                RFPOApprovalAction.id.in_(backup_action_ids),
            ).all()
            all_actions = list(pending_actions) + [
                a for a in extra_actions if a.id not in {pa.id for pa in pending_actions}
            ]
        else:
            all_actions = list(pending_actions)

        # Build response grouped by RFPO
        rfpo_map = {}
        for action in all_actions:
            instance = RFPOApprovalInstance.query.get(action.instance_id)
            if not instance or not instance.rfpo:
                continue
            rfpo = instance.rfpo
            if rfpo.id not in rfpo_map:
                rfpo_map[rfpo.id] = {
                    "rfpo": rfpo.to_dict(),
                    "instance": instance.to_dict(),
                    "pending_actions": [],
                }
            rfpo_map[rfpo.id]["pending_actions"].append(action.to_dict())

        rfpos_list = list(rfpo_map.values())

        # Also fetch completed actions for this user
        completed_actions = RFPOApprovalAction.query.filter(
            RFPOApprovalAction.approver_id == user.record_id,
            RFPOApprovalAction.status.in_(["approved", "conditional"]),
        ).all()
        refused_actions = RFPOApprovalAction.query.filter_by(
            approver_id=user.record_id,
            status="refused",
        ).all()

        # Summary counts
        total_pending = len(all_actions)
        total_rfpos = len(rfpos_list)

        return jsonify({
            "success": True,
            "rfpos": rfpos_list,
            "summary": {
                "total": total_rfpos,
                "pending": total_pending,
                "completed": len(completed_actions),
                "refused": len(refused_actions),
            },
        })

    except Exception as e:
        app.logger.exception(f"Approver RFPOs error for user {request.current_user.record_id}: {e}")
        return _error_response(e)


@app.route("/api/users/approval-action/<action_id>", methods=["POST"])
@require_auth
def take_approval_action(action_id):
    """Take an approval action (approve/reject)"""
    try:

        user = request.current_user
        data = request.get_json()

        # Find the action
        action = RFPOApprovalAction.query.filter_by(action_id=action_id).first()
        if not action:
            return (
                jsonify({"success": False, "message": "Approval action not found"}),
                404,
            )

        # Check if user is authorized to take this action
        if action.approver_id != user.record_id and not user.is_super_admin():
            return (
                jsonify(
                    {"success": False, "message": "Not authorized to take this action"}
                ),
                403,
            )

        # Check if action is still pending
        if action.status != "pending":
            return (
                jsonify(
                    {"success": False, "message": "Action has already been completed"}
                ),
                400,
            )

        # Validate status
        status = data.get("status")
        if status not in ["approved", "conditional", "refused"]:
            return (
                jsonify(
                    {"success": False, "message": "Status must be approved, conditional, or refused"}
                ),
                400,
            )

        comments = data.get("comments", "")
        conditions = data.get("conditions", "")

        # Complete the action
        action.complete_action(status, comments, conditions if status == "conditional" else None, user.record_id)

        # Update instance status
        instance = action.instance
        if status == "refused":
            instance.overall_status = "refused"
            instance.completed_at = datetime.utcnow()

            # Update RFPO status
            if instance.rfpo:
                instance.rfpo.status = "Refused"
                instance.rfpo.updated_by = user.get_display_name()
        elif status == "conditional":
            # Conditional approval: advance workflow but note conditions
            instance.advance_to_next_step()
            if instance.overall_status == "approved" and instance.rfpo:
                instance.rfpo.status = "Approved"
                instance.rfpo.updated_by = user.get_display_name()
        else:
            # For approvals, advance workflow and check for completion
            instance.advance_to_next_step()

            # If workflow is now complete and approved, update RFPO status
            if instance.overall_status == "approved" and instance.rfpo:
                instance.rfpo.status = "Approved"
                instance.rfpo.updated_by = user.get_display_name()

        instance.updated_at = datetime.utcnow()

        # Audit trail
        audit = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action=status,
            entity_type="rfpo_approval",
            entity_id=str(instance.rfpo_id),
            ip_address=request.remote_addr,
        )
        audit.set_details({
            "action_id": action.action_id,
            "step_name": action.step_name,
            "stage_name": action.stage_name,
            "comments": comments,
            "conditions": conditions if status == "conditional" else None,
            "instance_status": instance.overall_status,
        })
        db.session.add(audit)

        db.session.commit()

        # Send email notifications (non-blocking)
        try:
            from email_service import send_approval_notification
            # Notify requestor if workflow completed
            if instance.overall_status in ("approved", "refused") and instance.rfpo:
                requestor = User.query.filter_by(
                    record_id=instance.rfpo.created_by_id
                ).first() if hasattr(instance.rfpo, 'created_by_id') else None
                if requestor and requestor.email:
                    send_approval_notification(
                        requestor.email, requestor.get_display_name(),
                        instance.rfpo.rfpo_id, f"RFPO {instance.overall_status.title()}"
                    )
        except Exception as email_err:
            app.logger.warning(f"Email notification failed: {email_err}")

        return jsonify(
            {
                "success": True,
                "message": f"Action {status} successfully",
                "action": {
                    "action_id": action.action_id,
                    "status": action.status,
                    "completed_at": (
                        action.completed_at.isoformat() if action.completed_at else None
                    ),
                },
                "instance_status": instance.overall_status,
                "rfpo_status": instance.rfpo.status if instance.rfpo else None,
            }
        )

    except Exception as e:
        db.session.rollback()
        return _error_response(e)


@app.route("/api/users/bulk-approval", methods=["POST"])
@require_auth
def bulk_approval_action():
    """Approve or refuse multiple approval actions at once"""
    try:

        user = request.current_user
        data = request.get_json()

        action_ids = data.get("action_ids", [])
        status = data.get("status")
        comments = data.get("comments", "")

        if not action_ids:
            return jsonify({"success": False, "message": "No actions specified"}), 400
        if status not in ["approved", "refused"]:
            return jsonify({"success": False, "message": "Status must be approved or refused"}), 400

        results = {"succeeded": 0, "failed": 0, "errors": []}

        for action_id in action_ids:
            try:
                action = RFPOApprovalAction.query.filter_by(action_id=action_id).first()
                if not action:
                    results["failed"] += 1
                    results["errors"].append(f"{action_id}: not found")
                    continue
                if action.approver_id != user.record_id and not user.is_super_admin():
                    results["failed"] += 1
                    results["errors"].append(f"{action_id}: not authorized")
                    continue
                if action.status != "pending":
                    results["failed"] += 1
                    results["errors"].append(f"{action_id}: already completed")
                    continue

                action.complete_action(status, comments, None, user.record_id)

                instance = action.instance
                if status == "refused":
                    instance.overall_status = "refused"
                    instance.completed_at = datetime.utcnow()
                    if instance.rfpo:
                        instance.rfpo.status = "Refused"
                        instance.rfpo.updated_by = user.get_display_name()
                else:
                    instance.advance_to_next_step()
                    if instance.overall_status == "approved" and instance.rfpo:
                        instance.rfpo.status = "Approved"
                        instance.rfpo.updated_by = user.get_display_name()

                instance.updated_at = datetime.utcnow()
                results["succeeded"] += 1

            except Exception as action_err:
                results["failed"] += 1
                results["errors"].append(f"{action_id}: {str(action_err)}")

        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"{results['succeeded']} action(s) {status} successfully" +
                       (f", {results['failed']} failed" if results["failed"] else ""),
            "results": results,
        })

    except Exception as e:
        db.session.rollback()
        return _error_response(e)


@app.route("/api/rfpos/<int:rfpo_id>/submit-for-approval", methods=["POST"])
@require_auth
def submit_for_approval(rfpo_id):
    """Submit an RFPO for approval - admin only. Creates workflow instance and first actions."""
    try:
        import uuid as uuid_mod

        user = request.current_user

        # Admin-only check
        user_perms = user.get_permissions() or []
        if "RFPO_ADMIN" not in user_perms and "GOD" not in user_perms:
            return jsonify({"success": False, "message": "Admin access required"}), 403

        rfpo = RFPO.query.get_or_404(rfpo_id)

        # Only Draft RFPOs can be submitted
        if rfpo.status not in ("Draft", "Refused"):
            return jsonify({
                "success": False,
                "message": f"Cannot submit RFPO with status '{rfpo.status}'. Must be Draft or Refused."
            }), 400

        # Check if there's already an active approval instance
        existing = RFPOApprovalInstance.query.filter_by(rfpo_id=rfpo.id).first()
        if existing and existing.overall_status not in ("refused",):
            return jsonify({
                "success": False,
                "message": "This RFPO already has an active approval workflow"
            }), 400

        # If re-submitting after refusal, remove old instance
        if existing and existing.overall_status == "refused":
            db.session.delete(existing)
            db.session.flush()

        # Find the appropriate workflow template
        # Priority: team → consortium (matching RFPO's team/consortium)
        workflow = None

        if rfpo.team_id:
            workflow = RFPOApprovalWorkflow.query.filter_by(
                team_id=rfpo.team_id, workflow_type="team", is_active=True, is_template=True
            ).first()

        if not workflow and rfpo.consortium_id:
            workflow = RFPOApprovalWorkflow.query.filter_by(
                consortium_id=rfpo.consortium_id, workflow_type="consortium",
                is_active=True, is_template=True
            ).first()

        if not workflow:
            return jsonify({
                "success": False,
                "message": "No active approval workflow found for this RFPO's team or consortium. "
                           "Please configure a workflow in the admin panel first."
            }), 400

        # Determine which stage applies based on RFPO total amount
        rfpo_total = float(rfpo.total_amount or 0)
        applicable_stage = None
        for stage in sorted(workflow.stages, key=lambda s: s.budget_bracket_amount or 0):
            if rfpo_total <= float(stage.budget_bracket_amount or 0):
                applicable_stage = stage
                break
        # If no bracket matches, use the highest bracket
        if not applicable_stage and workflow.stages:
            applicable_stage = sorted(workflow.stages, key=lambda s: s.budget_bracket_amount or 0)[-1]

        if not applicable_stage or not applicable_stage.steps:
            return jsonify({
                "success": False,
                "message": "No approval stages/steps configured for this workflow"
            }), 400

        # Build instance_data snapshot for ONLY the applicable stage
        # (the stage whose budget bracket covers the RFPO total amount)
        steps_data = []
        for step in sorted(applicable_stage.steps, key=lambda s: s.step_order):
            steps_data.append({
                "step_id": step.step_id,
                "step_name": step.step_name,
                "step_order": step.step_order,
                "approval_type_key": step.approval_type_key,
                "approval_type_name": step.approval_type_name,
                "primary_approver_id": step.primary_approver_id,
                "backup_approver_id": step.backup_approver_id,
                "is_required": step.is_required,
                "timeout_days": step.timeout_days,
            })
        stages_data = [{
            "stage_id": applicable_stage.stage_id,
            "stage_name": applicable_stage.stage_name,
            "stage_order": applicable_stage.stage_order,
            "budget_bracket_key": applicable_stage.budget_bracket_key,
            "budget_bracket_amount": float(applicable_stage.budget_bracket_amount or 0),
            "requires_all_steps": applicable_stage.requires_all_steps,
            "is_parallel": applicable_stage.is_parallel,
            "steps": steps_data,
        }]

        # Create the approval instance
        instance = RFPOApprovalInstance(
            instance_id=uuid_mod.uuid4().hex[:16],
            rfpo_id=rfpo.id,
            template_workflow_id=workflow.id,
            workflow_name=workflow.name,
            workflow_version=workflow.version or "1.0",
            consortium_id=rfpo.consortium_id or workflow.consortium_id or "",
            current_stage_order=1,
            current_step_order=1,
            overall_status="waiting",
            submitted_at=datetime.utcnow(),
            created_by=user.get_display_name(),
        )
        instance.set_instance_data({"stages": stages_data})
        db.session.add(instance)
        db.session.flush()  # Get instance.id

        # Create approval actions for all steps in the applicable stage
        for stage_data in stages_data:
            for step_data in stage_data["steps"]:
                # Get approver name
                approver = User.query.filter_by(
                    record_id=step_data["primary_approver_id"], active=True
                ).first()
                approver_name = approver.get_display_name() if approver else "Unknown"

                # First step of first stage is pending, rest are pending too
                # (they get activated sequentially by advance_to_next_step)
                action = RFPOApprovalAction(
                    action_id=uuid_mod.uuid4().hex[:16],
                    instance_id=instance.id,
                    stage_order=stage_data["stage_order"],
                    step_order=step_data["step_order"],
                    stage_name=stage_data["stage_name"],
                    step_name=step_data["step_name"],
                    approval_type_key=step_data["approval_type_key"],
                    approver_id=step_data["primary_approver_id"],
                    approver_name=approver_name,
                    status="pending",
                    assigned_at=datetime.utcnow(),
                    due_date=datetime.utcnow() + timedelta(days=step_data.get("timeout_days", 5)),
                )
                db.session.add(action)

        # Update RFPO status
        rfpo.status = "Pending Approval"
        rfpo.updated_by = user.get_display_name()
        rfpo.updated_at = datetime.utcnow()

        # Audit trail
        audit = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action="submit_for_approval",
            entity_type="rfpo",
            entity_id=str(rfpo.id),
            ip_address=request.remote_addr,
        )
        audit.set_details({
            "rfpo_id": rfpo.rfpo_id,
            "workflow_name": workflow.name,
            "instance_id": instance.instance_id,
            "total_amount": rfpo_total,
        })
        db.session.add(audit)

        db.session.commit()

        # Send email notifications to first approver(s) (non-blocking)
        try:
            from email_service import send_approval_notification
            first_stage = stages_data[0] if stages_data else None
            if first_stage:
                for step_data in first_stage["steps"]:
                    approver = User.query.filter_by(
                        record_id=step_data["primary_approver_id"], active=True
                    ).first()
                    if approver and approver.email:
                        send_approval_notification(
                            approver.email, approver.get_display_name(),
                            rfpo.rfpo_id, step_data["approval_type_name"]
                        )
        except Exception as email_err:
            app.logger.warning(f"Email notification failed: {email_err}")

        return jsonify({
            "success": True,
            "message": f"RFPO submitted for approval via '{workflow.name}'",
            "instance": instance.to_dict(),
            "rfpo_status": rfpo.status,
        }), 201

    except Exception as e:
        db.session.rollback()
        return _error_response(e)


@app.route("/api/rfpos/<int:rfpo_id>/withdraw-approval", methods=["POST"])
@require_auth
def withdraw_approval(rfpo_id):
    """Withdraw an RFPO from the approval process - admin only"""
    try:

        user = request.current_user
        user_perms = user.get_permissions() or []
        if "RFPO_ADMIN" not in user_perms and "GOD" not in user_perms:
            return jsonify({"success": False, "message": "Admin access required"}), 403

        rfpo = RFPO.query.get_or_404(rfpo_id)

        if rfpo.status not in ("Pending Approval",):
            return jsonify({
                "success": False,
                "message": f"Cannot withdraw RFPO with status '{rfpo.status}'"
            }), 400

        instance = RFPOApprovalInstance.query.filter_by(rfpo_id=rfpo.id).first()
        if not instance:
            return jsonify({
                "success": False, "message": "No approval instance found"
            }), 404

        # Delete the instance (cascades to actions)
        db.session.delete(instance)

        # Reset RFPO status to Draft
        rfpo.status = "Draft"
        rfpo.updated_by = user.get_display_name()
        rfpo.updated_at = datetime.utcnow()

        # Audit trail
        audit = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action="withdraw_approval",
            entity_type="rfpo",
            entity_id=str(rfpo.id),
            ip_address=request.remote_addr,
        )
        audit.set_details({
            "rfpo_id": rfpo.rfpo_id,
            "instance_id": instance.instance_id,
            "reason": request.get_json().get("reason", "") if request.is_json else "",
        })
        db.session.add(audit)

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Approval withdrawn. RFPO returned to Draft status.",
            "rfpo_status": rfpo.status,
        })

    except Exception as e:
        db.session.rollback()
        return _error_response(e)


@app.route("/api/users/reassign-approval/<action_id>", methods=["POST"])
@require_auth
def reassign_approval_action(action_id):
    """Reassign a pending approval action to a different user - GOD/admin only"""
    try:

        user = request.current_user
        user_perms = user.get_permissions() or []
        if "RFPO_ADMIN" not in user_perms and "GOD" not in user_perms:
            return jsonify({"success": False, "message": "Admin access required"}), 403

        data = request.get_json()
        new_approver_id = data.get("new_approver_id")
        reason = data.get("reason", "")

        if not new_approver_id:
            return jsonify({
                "success": False, "message": "new_approver_id is required"
            }), 400

        action = RFPOApprovalAction.query.filter_by(action_id=action_id).first()
        if not action:
            return jsonify({"success": False, "message": "Action not found"}), 404

        if action.status != "pending":
            return jsonify({
                "success": False, "message": "Can only reassign pending actions"
            }), 400

        new_approver = User.query.filter_by(
            record_id=new_approver_id, active=True
        ).first()
        if not new_approver:
            return jsonify({
                "success": False, "message": "New approver not found or inactive"
            }), 404

        old_approver_id = action.approver_id
        old_approver_name = action.approver_name

        # Reassign
        action.approver_id = new_approver.record_id
        action.approver_name = new_approver.get_display_name()
        action.assigned_at = datetime.utcnow()
        action.updated_at = datetime.utcnow()

        # Audit trail
        audit = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action="reassign_approval",
            entity_type="rfpo_approval",
            entity_id=str(action.instance.rfpo_id),
            ip_address=request.remote_addr,
        )
        audit.set_details({
            "action_id": action.action_id,
            "step_name": action.step_name,
            "old_approver_id": old_approver_id,
            "old_approver_name": old_approver_name,
            "new_approver_id": new_approver.record_id,
            "new_approver_name": new_approver.get_display_name(),
            "reason": reason,
        })
        db.session.add(audit)

        db.session.commit()

        # Notify new approver (non-blocking)
        try:
            from email_service import send_approval_notification
            rfpo = action.instance.rfpo
            if new_approver.email and rfpo:
                send_approval_notification(
                    new_approver.email, new_approver.get_display_name(),
                    rfpo.rfpo_id, f"Reassigned: {action.step_name}"
                )
        except Exception as email_err:
            app.logger.warning(f"Email notification failed: {email_err}")

        return jsonify({
            "success": True,
            "message": f"Action reassigned from {old_approver_name} to {new_approver.get_display_name()}",
            "action": {
                "action_id": action.action_id,
                "approver_id": action.approver_id,
                "approver_name": action.approver_name,
            },
        })

    except Exception as e:
        db.session.rollback()
        return _error_response(e)


@app.route("/api/users", methods=["GET"])
@require_auth
def list_users():
    """List active users - admin only (used for reassignment dropdowns)"""
    try:
        user = request.current_user
        user_perms = user.get_permissions() or []
        if "RFPO_ADMIN" not in user_perms and "GOD" not in user_perms:
            return jsonify({"success": False, "message": "Admin access required"}), 403

        users = User.query.filter_by(active=True).all()
        return jsonify({
            "success": True,
            "users": [
                {
                    "record_id": u.record_id,
                    "email": u.email,
                    "display_name": u.get_display_name(),
                    "active": u.active,
                }
                for u in users
            ],
        })
    except Exception as e:
        return _error_response(e)


@app.route("/api/users/profile", methods=["GET"])
@require_auth
def get_user_profile():
    """Get current user's profile"""
    try:
        user = request.current_user
        return jsonify(
            {
                "success": True,
                "user": {
                    "id": user.id,
                    "record_id": user.record_id,
                    "fullname": user.fullname,
                    "email": user.email,
                    "sex": user.sex,
                    "company_code": user.company_code,
                    "company": user.company,
                    "position": user.position,
                    "department": user.department,
                    "building_address": user.building_address,
                    "address1": user.address1,
                    "address2": user.address2,
                    "city": user.city,
                    "state": user.state,
                    "zip_code": user.zip_code,
                    "country": user.country,
                    "phone": user.phone,
                    "phone_ext": user.phone_ext,
                    "mobile": user.mobile,
                    "fax": user.fax,
                    "last_visit": (
                        user.last_visit.isoformat() if user.last_visit else None
                    ),
                    "created_at": (
                        user.created_at.isoformat() if user.created_at else None
                    ),
                    "active": user.active,
                    "permissions": user.get_permissions(),
                    "is_approver": user.is_approver,
                    "approver_summary": user.get_approver_summary(),
                },
            }
        )
    except Exception as e:
        return _error_response(e)


@app.route("/api/users/approver-status", methods=["GET"])
@require_auth
def get_user_approver_status():
    """Get detailed approver status for current user"""
    try:
        user = request.current_user
        approver_info = user.check_approver_status()
        approver_summary = user.get_approver_summary()

        return jsonify(
            {
                "success": True,
                "user_id": user.id,
                "record_id": user.record_id,
                "is_approver": user.is_approver,
                "approver_updated_at": (
                    user.approver_updated_at.isoformat()
                    if user.approver_updated_at
                    else None
                ),
                "approver_info": approver_info,
                "approver_summary": approver_summary,
            }
        )

    except Exception as e:
        return _error_response(e)


@app.route("/api/users/sync-approver-status", methods=["POST"])
@require_auth
def sync_user_approver_status():
    """Sync approver status for current user (force refresh)"""
    try:
        user = request.current_user
        status_changed = user.update_approver_status(updated_by=user.email)

        if status_changed:
            db.session.commit()
            message = f"Approver status updated to: {'Approver' if user.is_approver else 'Not an approver'}"
        else:
            message = "Approver status is already up to date"

        return jsonify(
            {
                "success": True,
                "message": message,
                "status_changed": status_changed,
                "is_approver": user.is_approver,
                "approver_summary": user.get_approver_summary(),
            }
        )

    except Exception as e:
        db.session.rollback()
        return _error_response(e)


@app.route("/api/users/profile", methods=["PUT"])
@require_auth
def update_user_profile():
    """Update current user's profile"""
    try:
        data = request.get_json()
        user = request.current_user

        # Update allowed fields (excluding sensitive fields like permissions)
        updateable_fields = [
            "fullname",
            "sex",
            "company_code",
            "company",
            "position",
            "department",
            "building_address",
            "address1",
            "address2",
            "city",
            "state",
            "zip_code",
            "country",
            "phone",
            "phone_ext",
            "mobile",
            "fax",
        ]

        for field in updateable_fields:
            if field in data:
                setattr(user, field, data[field])

        user.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({"success": True, "message": "Profile updated successfully"})

    except Exception as e:
        db.session.rollback()
        return _error_response(e)


@app.route("/api/users/permissions-summary")
@require_auth
def get_user_permissions_summary():
    """Get comprehensive permissions summary for current user"""
    try:

        user = request.current_user

        # System permissions
        system_permissions = user.get_permissions() or []

        # Team associations
        user_teams = user.get_teams()
        team_data = []
        accessible_consortium_ids = set()

        for team in user_teams:
            team_info = {
                "id": team.id,
                "record_id": team.record_id,
                "name": team.name,
                "abbrev": team.abbrev,
                "consortium_id": team.consortium_consort_id,
                "consortium_name": None,
            }

            # Get consortium info
            if team.consortium_consort_id:
                consortium = Consortium.query.filter_by(
                    consort_id=team.consortium_consort_id
                ).first()
                if consortium:
                    team_info["consortium_name"] = consortium.name
                    accessible_consortium_ids.add(team.consortium_consort_id)

            team_data.append(team_info)

        # Direct consortium access
        direct_consortium_access = []
        all_consortiums = Consortium.query.all()
        for consortium in all_consortiums:
            viewer_users = consortium.get_rfpo_viewer_users()
            admin_users = consortium.get_rfpo_admin_users()

            access_type = None
            if user.record_id in admin_users:
                access_type = "admin"
            elif user.record_id in viewer_users:
                access_type = "viewer"

            if access_type:
                # Count RFPOs in this consortium (both through teams and direct consortium association)
                consortium_teams = Team.query.filter_by(
                    consortium_consort_id=consortium.consort_id
                ).all()
                team_based_rfpos = sum(
                    RFPO.query.filter_by(team_id=team.id).count()
                    for team in consortium_teams
                )

                # Also count RFPOs that directly reference this consortium
                direct_consortium_rfpos = RFPO.query.filter_by(
                    consortium_id=consortium.consort_id
                ).count()

                # Total is the sum (but we need to check for potential overlaps)
                # For now, use direct count if no team-based, otherwise use total
                consortium_rfpo_count = (
                    direct_consortium_rfpos
                    if team_based_rfpos == 0
                    else (team_based_rfpos + direct_consortium_rfpos)
                )

                direct_consortium_access.append(
                    {
                        "consort_id": consortium.consort_id,
                        "name": consortium.name,
                        "abbrev": consortium.abbrev,
                        "access_type": access_type,
                        "rfpo_count": consortium_rfpo_count,
                    }
                )
                accessible_consortium_ids.add(consortium.consort_id)

        # Project access (both direct and via team membership)
        project_access = []
        all_projects = Project.query.all()
        accessible_project_ids = []

        # Get team record IDs for projects accessible via teams
        team_record_ids = [team["record_id"] for team in team_data]

        for project in all_projects:
            access_type = None

            # Check direct project access
            viewer_users = project.get_rfpo_viewer_users()
            if user.record_id in viewer_users:
                access_type = "direct_viewer"

            # Check team-based project access
            elif project.team_record_id in team_record_ids:
                access_type = "via_team"

            if access_type:
                project_rfpo_count = RFPO.query.filter_by(
                    project_id=project.project_id
                ).count()
                project_access.append(
                    {
                        "project_id": project.project_id,
                        "name": project.name,
                        "ref": project.ref,
                        "consortium_ids": project.get_consortium_ids(),
                        "rfpo_count": project_rfpo_count,
                        "access_type": access_type,
                    }
                )
                accessible_project_ids.append(project.project_id)

        # Calculate accessible RFPOs
        accessible_rfpos = []

        # 1. RFPOs from user's teams
        team_ids = [team.id for team in user_teams]
        if team_ids:
            team_rfpos = RFPO.query.filter(RFPO.team_id.in_(team_ids)).all()
            accessible_rfpos.extend(team_rfpos)

        # 2. RFPOs from projects user has access to
        if accessible_project_ids:
            project_rfpos = RFPO.query.filter(
                RFPO.project_id.in_(accessible_project_ids)
            ).all()
            accessible_rfpos.extend(project_rfpos)

        # 3. RFPOs from consortiums user has access to
        accessible_consortium_ids_list = [
            consortium["consort_id"] for consortium in direct_consortium_access
        ]
        if accessible_consortium_ids_list:
            consortium_rfpos = RFPO.query.filter(
                RFPO.consortium_id.in_(accessible_consortium_ids_list)
            ).all()
            accessible_rfpos.extend(consortium_rfpos)

        # Remove duplicates
        accessible_rfpos = list({rfpo.id: rfpo for rfpo in accessible_rfpos}.values())

        rfpo_summary = []
        for rfpo in accessible_rfpos[:10]:  # Limit to first 10 for performance
            rfpo_summary.append(
                {
                    "id": rfpo.id,
                    "rfpo_id": rfpo.rfpo_id,
                    "title": rfpo.title,
                    "status": rfpo.status,
                    "total_amount": float(rfpo.total_amount or 0),
                    "created_at": (
                        rfpo.created_at.isoformat() if rfpo.created_at else None
                    ),
                }
            )

        # Approval workflow access (for users with admin permissions)
        approval_access = []
        if user.is_rfpo_admin() or user.is_super_admin():
            # They can see all approval workflows
            approval_access = ["All approval workflows (Admin access)"]

        return jsonify(
            {
                "success": True,
                "user": {
                    "id": user.id,
                    "record_id": user.record_id,
                    "email": user.email,
                    "display_name": user.get_display_name(),
                },
                "permissions_summary": {
                    "system_permissions": system_permissions,
                    "is_super_admin": user.is_super_admin(),
                    "is_rfpo_admin": user.is_rfpo_admin(),
                    "is_rfpo_user": user.is_rfpo_user(),
                    "team_associations": team_data,
                    "direct_consortium_access": direct_consortium_access,
                    "project_access": project_access,
                    "accessible_rfpos_count": len(accessible_rfpos),
                    "accessible_rfpos_sample": rfpo_summary,
                    "approval_access": approval_access,
                    "summary_counts": {
                        "teams": len(team_data),
                        "consortiums": len(accessible_consortium_ids),
                        "projects": len(project_access),
                        "rfpos": len(accessible_rfpos),
                    },
                },
            }
        )

    except Exception as e:
        return _error_response(e)


@app.route("/api/rfpos")
@require_auth
def list_rfpos():
    """List RFPOs with permission filtering, pagination, and search"""
    try:
        user = request.current_user
        page = max(1, request.args.get("page", 1, type=int))
        per_page = max(1, min(request.args.get("per_page", 50, type=int), 200))
        status_filter = request.args.get("status")
        search_query = request.args.get("search", "").strip()
        team_id_filter = request.args.get("team_id", type=int)
        date_from = request.args.get("date_from")  # YYYY-MM-DD
        date_to = request.args.get("date_to")  # YYYY-MM-DD

        # If user is super admin, they can see all RFPOs
        if user.is_super_admin():
            query = RFPO.query
        else:
            accessible_rfpo_ids = set()

            # 1. Get user's accessible team IDs
            user_teams = user.get_teams()
            team_ids = [team.id for team in user_teams]

            # 2. Get user's accessible project IDs
            all_projects = Project.query.all()
            accessible_project_ids = []
            for project in all_projects:
                viewer_users = project.get_rfpo_viewer_users()
                if user.record_id in viewer_users:
                    accessible_project_ids.append(project.project_id)

            # 3. Get RFPOs where user is an approver
            if user.is_approver:

                user_actions = RFPOApprovalAction.query.filter_by(
                    approver_id=user.record_id
                ).all()
                for action in user_actions:
                    if action.instance and action.instance.rfpo:
                        accessible_rfpo_ids.add(action.instance.rfpo.id)

            # Build query filters
            filters = []
            if team_ids:
                filters.append(RFPO.team_id.in_(team_ids))
            if accessible_project_ids:
                filters.append(RFPO.project_id.in_(accessible_project_ids))
            if accessible_rfpo_ids:
                filters.append(RFPO.id.in_(accessible_rfpo_ids))

            # Apply filters
            if filters:
                if len(filters) > 1:
                    query = RFPO.query.filter(db.or_(*filters))
                else:
                    query = RFPO.query.filter(filters[0])
            else:
                # User has no access to any RFPOs
                return jsonify({"success": True, "rfpos": [], "total": 0, "page": page, "pages": 0})

        # Apply status filter if provided
        if status_filter:
            query = query.filter(RFPO.status == status_filter)

        # Apply text search
        if search_query:
            like_term = f"%{search_query}%"
            query = query.filter(
                db.or_(
                    RFPO.title.ilike(like_term),
                    RFPO.rfpo_id.ilike(like_term),
                    RFPO.description.ilike(like_term),
                )
            )

        # Apply team filter
        if team_id_filter:
            query = query.filter(RFPO.team_id == team_id_filter)

        # Apply date range filters
        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d")
                query = query.filter(RFPO.created_at >= from_date)
            except ValueError:
                pass
        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
                query = query.filter(RFPO.created_at < to_date)
            except ValueError:
                pass

        # Order and paginate
        query = query.order_by(RFPO.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        rfpos = pagination.items

        # Build a lookup of pending approval action_ids for this user
        pending_action_map = {}  # rfpo_id -> action_id
        try:
            user_pending = RFPOApprovalAction.query.filter_by(
                approver_id=user.record_id, status="pending"
            ).all()
            for pa in user_pending:
                inst = RFPOApprovalInstance.query.get(pa.instance_id)
                if inst and inst.rfpo_id:
                    pending_action_map[inst.rfpo_id] = pa.action_id
        except Exception as e:
            app.logger.warning(f"Failed to load pending actions: {e}")

        return jsonify(
            {
                "success": True,
                "rfpos": [
                    {
                        "id": r.id,
                        "rfpo_id": r.rfpo_id,
                        "title": r.title,
                        "status": r.status,
                        "total_amount": float(r.total_amount) if r.total_amount else 0,
                        "vendor": r.vendor.company_name if r.vendor else None,
                        "due_date": r.due_date.isoformat() if r.due_date else None,
                        "created_at": (
                            r.created_at.isoformat() if r.created_at else None
                        ),
                        "pending_action_id": pending_action_map.get(r.id),
                    }
                    for r in rfpos
                ],
                "total": pagination.total,
                "page": pagination.page,
                "pages": pagination.pages,
                "per_page": pagination.per_page,
            }
        )

    except Exception as e:
        return _error_response(e)


@app.route("/api/rfpos", methods=["POST"])
@require_auth
def create_rfpo():
    """Create new RFPO"""
    try:
        # Only RFPO_ADMIN or GOD can create RFPOs
        user_perms = request.current_user.get_permissions() or []
        if 'RFPO_ADMIN' not in user_perms and 'GOD' not in user_perms:
            return jsonify({"success": False, "message": "Admin access required to create RFPOs"}), 403

        data = request.get_json()

        # Validate required fields
        required_fields = ["title", "project_id", "consortium_id", "team_id"]
        for field in required_fields:
            if not data.get(field):
                return (
                    jsonify({"success": False, "message": f"{field} is required"}),
                    400,
                )

        # Generate RFPO ID
        from datetime import datetime

        today = datetime.now()
        date_str = today.strftime("%Y-%m-%d")

        # Get project reference for RFPO ID
        project = Project.query.filter_by(project_id=data["project_id"]).first()
        project_ref = project.ref if project else "PROJ"

        # Count existing RFPOs for this project and date
        existing_count = RFPO.query.filter(
            RFPO.rfpo_id.like(f"RFPO-{project_ref}-%{date_str}%")
        ).count()
        rfpo_id = f"RFPO-{project_ref}-{date_str}-N{existing_count + 1:02d}"

        # Create RFPO
        rfpo = RFPO(
            rfpo_id=rfpo_id,
            title=data["title"],
            description=data.get("description", ""),
            project_id=data["project_id"],
            consortium_id=data["consortium_id"],
            team_id=data["team_id"],
            government_agreement_number=data.get("government_agreement_number"),
            requestor_id=request.current_user.record_id,
            requestor_tel=data.get("requestor_tel"),
            requestor_location=data.get("requestor_location"),
            shipto_name=data.get("shipto_name"),
            shipto_tel=data.get("shipto_tel"),
            shipto_address=data.get("shipto_address"),
            delivery_date=(
                datetime.strptime(data["delivery_date"], "%Y-%m-%d").date()
                if data.get("delivery_date")
                else None
            ),
            delivery_type=data.get("delivery_type"),
            delivery_payment=data.get("delivery_payment"),
            delivery_routing=data.get("delivery_routing"),
            payment_terms=data.get("payment_terms", "Net 30"),
            vendor_id=data.get("vendor_id"),
            vendor_site_id=data.get("vendor_site_id"),
            cost_share_description=data.get("cost_share_description"),
            cost_share_type=data.get("cost_share_type", "total"),
            cost_share_amount=float(data.get("cost_share_amount", 0)),
            status=data.get("status", "Draft"),
            comments=data.get("comments"),
            created_by=request.current_user.get_display_name(),
        )

        # Set default invoice address from consortium
        if data.get("consortium_id"):
            consortium = Consortium.query.filter_by(
                consort_id=data["consortium_id"]
            ).first()
            if consortium and consortium.invoicing_address:
                rfpo.invoice_address = consortium.invoicing_address

        db.session.add(rfpo)
        db.session.commit()

        return jsonify({"success": True, "rfpo": rfpo.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        return _error_response(e)


@app.route("/api/rfpos/<int:rfpo_id>", methods=["GET"])
@require_auth
def get_rfpo(rfpo_id):
    """Get RFPO details"""
    try:

        rfpo = RFPO.query.get_or_404(rfpo_id)

        # Check permissions - user must have access to this RFPO
        user = request.current_user
        if not user.is_super_admin():
            # Check if user has access to this RFPO via team, project, or approval
            has_access = False

            # Check team access
            user_teams = user.get_teams()
            team_ids = [team.id for team in user_teams]
            if rfpo.team_id and rfpo.team_id in team_ids:
                has_access = True

            # Check project access
            if not has_access:
                all_projects = Project.query.all()
                for project in all_projects:
                    if project.project_id == rfpo.project_id:
                        viewer_users = project.get_rfpo_viewer_users()
                        if user.record_id in viewer_users:
                            has_access = True
                            break

            # Check approver access
            if not has_access and user.is_approver:
                user_action = (
                    RFPOApprovalAction.query.filter_by(approver_id=user.record_id)
                    .join(RFPOApprovalInstance)
                    .filter(RFPOApprovalInstance.rfpo_id == rfpo.id)
                    .first()
                )
                if user_action:
                    has_access = True

            if not has_access:
                return jsonify({"success": False, "message": "Access denied"}), 403

        # Get approval information for approvers AND admins
        approval_data = None
        user_action = None
        user_perms = user.get_permissions() or []
        is_admin_user = "RFPO_ADMIN" in user_perms or "GOD" in user_perms

        if user.is_approver or is_admin_user:
            # Find approval instance for this RFPO
            approval_instance = RFPOApprovalInstance.query.filter_by(
                rfpo_id=rfpo.id
            ).first()
            if approval_instance:
                # Get user's specific action for this RFPO
                user_action_obj = RFPOApprovalAction.query.filter_by(
                    instance_id=approval_instance.id, approver_id=user.record_id
                ).first()

                if user_action_obj:
                    user_action = {
                        "action_id": user_action_obj.action_id,
                        "step_name": user_action_obj.step_name,
                        "stage_name": user_action_obj.stage_name,
                        "status": user_action_obj.status,
                        "approval_type": user_action_obj.approval_type_key,
                        "assigned_at": (
                            user_action_obj.assigned_at.isoformat()
                            if user_action_obj.assigned_at
                            else None
                        ),
                        "completed_at": (
                            user_action_obj.completed_at.isoformat()
                            if user_action_obj.completed_at
                            else None
                        ),
                        "comments": user_action_obj.comments,
                        "can_take_action": user_action_obj.status == "pending",
                    }

                # Get all actions for approval chain display
                all_actions = (
                    RFPOApprovalAction.query.filter_by(instance_id=approval_instance.id)
                    .order_by(
                        RFPOApprovalAction.stage_order, RFPOApprovalAction.step_order
                    )
                    .all()
                )

                approval_chain = []
                for action in all_actions:
                    approval_chain.append(
                        {
                            "action_id": action.action_id,
                            "stage_order": action.stage_order,
                            "step_order": action.step_order,
                            "stage_name": action.stage_name,
                            "step_name": action.step_name,
                            "approver_name": action.approver_name,
                            "approver_id": action.approver_id,
                            "status": action.status,
                            "assigned_at": (
                                action.assigned_at.isoformat()
                                if action.assigned_at
                                else None
                            ),
                            "completed_at": (
                                action.completed_at.isoformat()
                                if action.completed_at
                                else None
                            ),
                            "comments": action.comments,
                            "conditions": action.conditions,
                            "is_user_action": action.approver_id == user.record_id,
                        }
                    )

                approval_data = {
                    "instance_id": approval_instance.instance_id,
                    "workflow_name": approval_instance.workflow_name,
                    "overall_status": approval_instance.overall_status,
                    "current_stage_order": approval_instance.current_stage_order,
                    "current_step_order": approval_instance.current_step_order,
                    "submitted_at": (
                        approval_instance.submitted_at.isoformat()
                        if approval_instance.submitted_at
                        else None
                    ),
                    "completed_at": (
                        approval_instance.completed_at.isoformat()
                        if approval_instance.completed_at
                        else None
                    ),
                    "approval_chain": approval_chain,
                }

        # Get RFPO files/attachments
        files_data = []
        if rfpo.files:
            for file in rfpo.files:
                files_data.append(
                    {
                        "file_id": file.file_id,
                        "original_filename": file.original_filename,
                        "file_size": file.file_size,
                        "document_type": file.document_type,
                        "description": file.description,
                        "uploaded_at": (
                            file.uploaded_at.isoformat() if file.uploaded_at else None
                        ),
                        "uploaded_by": file.uploaded_by,
                    }
                )

        # Build RFPO response with line items included
        rfpo_data = rfpo.to_dict()
        rfpo_data["line_items"] = [
            item.to_dict() for item in rfpo.line_items
        ]

        return jsonify(
            {
                "success": True,
                "rfpo": rfpo_data,
                "approval_data": approval_data,
                "user_action": user_action,
                "files": files_data,
            }
        )

    except Exception as e:
        return _error_response(e)


@app.route("/api/rfpos/<int:rfpo_id>", methods=["PUT", "PATCH"])
@require_auth
def update_rfpo(rfpo_id):
    """Update RFPO"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)
        data = request.get_json()

        # Block edits if RFPO is in approval or already approved
        locked_statuses = ("Pending Approval", "Approved", "Completed")
        if rfpo.status in locked_statuses:
            return jsonify({
                "success": False,
                "message": f"Cannot edit RFPO with status '{rfpo.status}'. Withdraw the approval first."
            }), 400

        # Check permissions (same logic as GET)
        user = request.current_user
        if not user.is_super_admin():
            has_access = False
            user_teams = user.get_teams()
            team_ids = [team.id for team in user_teams]
            if rfpo.team_id in team_ids:
                has_access = True

            if not has_access:
                all_projects = Project.query.all()
                for project in all_projects:
                    if project.project_id == rfpo.project_id:
                        viewer_users = project.get_rfpo_viewer_users()
                        if user.record_id in viewer_users:
                            has_access = True
                            break

            if not has_access:
                return jsonify({"success": False, "message": "Access denied"}), 403

        # Update fields
        updatable_fields = [
            "title",
            "description",
            "government_agreement_number",
            "requestor_tel",
            "requestor_location",
            "shipto_name",
            "shipto_tel",
            "shipto_address",
            "delivery_type",
            "delivery_payment",
            "delivery_routing",
            "payment_terms",
            "vendor_id",
            "vendor_site_id",
            "cost_share_description",
            "cost_share_type",
            "cost_share_amount",
            "status",
            "comments",
        ]

        for field in updatable_fields:
            if field in data:
                if field == "delivery_date" and data[field]:
                    rfpo.delivery_date = datetime.strptime(
                        data[field], "%Y-%m-%d"
                    ).date()
                elif field == "cost_share_amount":
                    rfpo.cost_share_amount = float(data[field]) if data[field] else 0.00
                elif field == "vendor_id":
                    rfpo.vendor_id = int(data[field]) if data[field] else None
                elif field == "vendor_site_id":
                    rfpo.vendor_site_id = int(data[field]) if data[field] else None
                else:
                    setattr(rfpo, field, data[field])

        # Handle delivery_date separately
        if "delivery_date" in data and data["delivery_date"]:
            rfpo.delivery_date = datetime.strptime(
                data["delivery_date"], "%Y-%m-%d"
            ).date()

        rfpo.updated_by = user.get_display_name()
        rfpo.update_totals()  # Recalculate totals with cost sharing

        db.session.commit()

        return jsonify({"success": True, "rfpo": rfpo.to_dict()})

    except Exception as e:
        db.session.rollback()
        return _error_response(e)


@app.route("/api/rfpos/<int:rfpo_id>", methods=["DELETE"])
@require_auth
def delete_rfpo(rfpo_id):
    """Delete RFPO"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)

        # Check permissions and approval status
        user = request.current_user
        if not (user.is_super_admin() or user.is_rfpo_admin()):
            return jsonify({"success": False, "message": "Admin access required"}), 403

        # Check if RFPO has approval instances

        approval_instance = RFPOApprovalInstance.query.filter_by(
            rfpo_id=rfpo.id
        ).first()
        if approval_instance:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Cannot delete RFPO: It has an active approval workflow",
                    }
                ),
                400,
            )

        db.session.delete(rfpo)
        db.session.commit()

        return jsonify({"success": True, "message": "RFPO deleted successfully"})

    except Exception as e:
        db.session.rollback()
        return _error_response(e)


# Line Items API
@app.route("/api/rfpos/<int:rfpo_id>/line-items", methods=["POST"])
@require_auth
def add_line_item(rfpo_id):
    """Add line item to RFPO"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)
        data = request.get_json()

        # Block edits if RFPO is in approval or already approved
        locked_statuses = ("Pending Approval", "Approved", "Completed")
        if rfpo.status in locked_statuses:
            return jsonify({
                "success": False,
                "message": f"Cannot modify line items while RFPO status is '{rfpo.status}'"
            }), 400

        # Only RFPO_ADMIN or GOD can add line items
        user = request.current_user
        user_perms = user.get_permissions() or []
        if 'RFPO_ADMIN' not in user_perms and 'GOD' not in user_perms:
            return jsonify({"success": False, "message": "Admin access required"}), 403

        # Get next line number
        max_line = (
            db.session.query(db.func.max(RFPOLineItem.line_number))
            .filter_by(rfpo_id=rfpo.id)
            .scalar()
        )
        next_line_number = (max_line or 0) + 1

        line_item = RFPOLineItem(
            rfpo_id=rfpo.id,
            line_number=next_line_number,
            quantity=int(data.get("quantity", 1)),
            description=data.get("description", ""),
            unit_price=float(data.get("unit_price", 0.00)),
            is_capital_equipment=bool(data.get("is_capital_equipment", False)),
            capital_description=data.get("capital_description"),
            capital_serial_id=data.get("capital_serial_id"),
            capital_location=data.get("capital_location"),
            capital_condition=data.get("capital_condition"),
        )

        # Handle capital equipment date and cost
        if data.get("capital_acquisition_date"):
            line_item.capital_acquisition_date = datetime.strptime(
                data["capital_acquisition_date"], "%Y-%m-%d"
            ).date()

        if data.get("capital_acquisition_cost"):
            line_item.capital_acquisition_cost = float(data["capital_acquisition_cost"])

        line_item.calculate_total()

        db.session.add(line_item)
        db.session.flush()

        # Update RFPO totals
        rfpo.update_totals()

        db.session.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "line_item": line_item.to_dict(),
                    "rfpo": rfpo.to_dict(),
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        return _error_response(e)


@app.route("/api/rfpos/<int:rfpo_id>/line-items/<int:line_item_id>", methods=["DELETE"])
@require_auth
def delete_line_item(rfpo_id, line_item_id):
    """Delete line item from RFPO"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)

        # Block edits if RFPO is in approval or already approved
        locked_statuses = ("Pending Approval", "Approved", "Completed")
        if rfpo.status in locked_statuses:
            return jsonify({
                "success": False,
                "message": f"Cannot modify line items while RFPO status is '{rfpo.status}'"
            }), 400

        line_item = RFPOLineItem.query.get_or_404(line_item_id)

        if line_item.rfpo_id != rfpo.id:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Line item does not belong to this RFPO",
                    }
                ),
                400,
            )

        # Only RFPO_ADMIN or GOD can delete line items
        user = request.current_user
        user_perms = user.get_permissions() or []
        if 'RFPO_ADMIN' not in user_perms and 'GOD' not in user_perms:
            return jsonify({"success": False, "message": "Admin access required"}), 403

        db.session.delete(line_item)

        # Update RFPO totals
        rfpo.update_totals()

        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": "Line item deleted successfully",
                "rfpo": rfpo.to_dict(),
            }
        )

    except Exception as e:
        db.session.rollback()
        return _error_response(e)


@app.route("/api/rfpos/<int:rfpo_id>/line-items", methods=["GET"])
@require_auth
def get_line_items(rfpo_id):
    """Get all line items for an RFPO"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)
        line_items = RFPOLineItem.query.filter_by(rfpo_id=rfpo.id).order_by(
            RFPOLineItem.line_number
        ).all()

        return jsonify(
            {"success": True, "line_items": [item.to_dict() for item in line_items]}
        )

    except Exception as e:
        return _error_response(e)


@app.route("/api/rfpos/<int:rfpo_id>/line-items/<int:line_item_id>", methods=["PUT"])
@require_auth
def update_line_item(rfpo_id, line_item_id):
    """Update a line item"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)

        # Block edits if RFPO is in approval or already approved
        locked_statuses = ("Pending Approval", "Approved", "Completed")
        if rfpo.status in locked_statuses:
            return jsonify({
                "success": False,
                "message": f"Cannot modify line items while RFPO status is '{rfpo.status}'"
            }), 400

        line_item = RFPOLineItem.query.get_or_404(line_item_id)

        if line_item.rfpo_id != rfpo.id:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Line item does not belong to this RFPO",
                    }
                ),
                400,
            )

        # Only RFPO_ADMIN or GOD can update line items
        user = request.current_user
        user_perms = user.get_permissions() or []
        if 'RFPO_ADMIN' not in user_perms and 'GOD' not in user_perms:
            return jsonify({"success": False, "message": "Admin access required"}), 403

        data = request.get_json()

        if "description" in data:
            line_item.description = data["description"]
        if "quantity" in data:
            line_item.quantity = int(data["quantity"])
        if "unit_price" in data:
            line_item.unit_price = float(data["unit_price"])
        if "is_capital_equipment" in data:
            line_item.is_capital_equipment = bool(data["is_capital_equipment"])
        if "capital_description" in data:
            line_item.capital_description = data["capital_description"]
        if "capital_serial_id" in data:
            line_item.capital_serial_id = data["capital_serial_id"]
        if "capital_location" in data:
            line_item.capital_location = data["capital_location"]
        if "capital_condition" in data:
            line_item.capital_condition = data["capital_condition"]
        if "capital_acquisition_date" in data and data["capital_acquisition_date"]:
            line_item.capital_acquisition_date = datetime.strptime(
                data["capital_acquisition_date"], "%Y-%m-%d"
            ).date()
        if "capital_acquisition_cost" in data and data["capital_acquisition_cost"]:
            line_item.capital_acquisition_cost = float(data["capital_acquisition_cost"])

        # Recalculate total
        line_item.calculate_total()
        line_item.updated_at = datetime.utcnow()

        # Update RFPO totals
        rfpo.update_totals()

        db.session.commit()

        return jsonify(
            {
                "success": True,
                "line_item": line_item.to_dict(),
                "rfpo": rfpo.to_dict(),
            }
        )

    except Exception as e:
        db.session.rollback()
        return _error_response(e)


# Supporting API endpoints for admin panel
@app.route("/api/consortiums")
@require_auth
def list_consortiums():
    """List all consortiums"""
    try:
        consortiums = Consortium.query.filter_by(active=True).all()
        return jsonify(
            {
                "success": True,
                "consortiums": [
                    {
                        "id": c.id,
                        "consort_id": c.consort_id,
                        "name": c.name,
                        "abbrev": c.abbrev,
                        "active": c.active,
                    }
                    for c in consortiums
                ],
            }
        )
    except Exception as e:
        return _error_response(e)


@app.route("/api/projects")
@require_auth
def list_projects():
    """List all projects"""
    try:
        projects = Project.query.filter_by(active=True).all()
        return jsonify(
            {
                "success": True,
                "projects": [
                    {
                        "id": p.id,
                        "project_id": p.project_id,
                        "name": p.name,
                        "ref": p.ref,
                        "description": p.description,
                        "consortium_ids": p.get_consortium_ids(),
                        "team_record_id": p.team_record_id,
                        "active": p.active,
                    }
                    for p in projects
                ],
            }
        )
    except Exception as e:
        return _error_response(e)


@app.route("/api/projects/<consortium_id>")
@require_auth
def list_projects_for_consortium(consortium_id):
    """List projects for a specific consortium"""
    try:
        projects = Project.query.filter(
            Project.consortium_ids.like(f"%{consortium_id}%"), Project.active == True
        ).all()

        return jsonify(
            {
                "success": True,
                "projects": [
                    {
                        "id": p.project_id,
                        "ref": p.ref,
                        "name": p.name,
                        "description": p.description,
                        "gov_funded": p.gov_funded,
                        "uni_project": p.uni_project,
                    }
                    for p in projects
                ],
            }
        )
    except Exception as e:
        return _error_response(e)


@app.route("/api/vendors")
@require_auth
def list_vendors():
    """List all vendors"""
    try:
        vendors = Vendor.query.filter_by(active=True).all()
        return jsonify(
            {
                "success": True,
                "vendors": [
                    {
                        "id": v.id,
                        "vendor_id": v.vendor_id,
                        "company_name": v.company_name,
                        "contact_name": v.contact_name,
                        "contact_tel": v.contact_tel,
                        "active": v.active,
                    }
                    for v in vendors
                ],
            }
        )
    except Exception as e:
        return _error_response(e)


@app.route("/api/vendor-sites/<int:vendor_id>")
@require_auth
def list_vendor_sites(vendor_id):
    """List sites for a specific vendor"""
    try:
        vendor = Vendor.query.get_or_404(vendor_id)
        site_data = []

        # Add vendor's primary contact as first option if it has contact info
        if vendor.contact_name:
            site_data.append(
                {
                    "id": f"vendor_{vendor.id}",
                    "contact_name": vendor.contact_name,
                    "contact_dept": vendor.contact_dept,
                    "contact_tel": vendor.contact_tel,
                    "contact_city": vendor.contact_city,
                    "contact_state": vendor.contact_state,
                    "is_primary": True,
                }
            )

        # Add additional vendor sites
        for site in vendor.sites:
            site_data.append(
                {
                    "id": site.id,
                    "contact_name": site.contact_name,
                    "contact_dept": site.contact_dept,
                    "contact_tel": site.contact_tel,
                    "contact_city": site.contact_city,
                    "contact_state": site.contact_state,
                    "is_primary": False,
                }
            )

        return jsonify(site_data)
    except Exception as e:
        return _error_response(e)


@app.route("/api/rfpos/<int:rfpo_id>/rendered-view")
@require_auth
def get_rfpo_rendered_view(rfpo_id):
    """Get RFPO rendered HTML view for approvers (like admin panel)"""
    try:
        from flask import render_template

        rfpo = RFPO.query.get_or_404(rfpo_id)
        user = request.current_user

        # Check permissions (same as get_rfpo)
        if not user.is_super_admin():
            has_access = False

            # Check team access
            user_teams = user.get_teams()
            team_ids = [team.id for team in user_teams]
            if rfpo.team_id and rfpo.team_id in team_ids:
                has_access = True

            # Check project access
            if not has_access:
                all_projects = Project.query.all()
                for project in all_projects:
                    if project.project_id == rfpo.project_id:
                        viewer_users = project.get_rfpo_viewer_users()
                        if user.record_id in viewer_users:
                            has_access = True
                            break

            # Check approver access
            if not has_access and user.is_approver:

                user_action = (
                    RFPOApprovalAction.query.filter_by(approver_id=user.record_id)
                    .join(RFPOApprovalInstance)
                    .filter(RFPOApprovalInstance.rfpo_id == rfpo.id)
                    .first()
                )
                if user_action:
                    has_access = True

            if not has_access:
                return jsonify({"success": False, "message": "Access denied"}), 403

        # Get related data for rendering (same as admin panel)
        project = Project.query.filter_by(project_id=rfpo.project_id).first()
        consortium = Consortium.query.filter_by(consort_id=rfpo.consortium_id).first()
        vendor = Vendor.query.get(rfpo.vendor_id) if rfpo.vendor_id else None
        vendor_site = None

        # Handle vendor_site_id
        if rfpo.vendor_site_id:
            try:
                vendor_site = VendorSite.query.get(int(rfpo.vendor_site_id))
            except (ValueError, TypeError):
                vendor_site = None

        # Get requestor user information
        requestor = (
            User.query.filter_by(record_id=rfpo.requestor_id).first()
            if rfpo.requestor_id
            else None
        )

        # Return the same HTML that admin panel generates
        try:
            html_content = render_template(
                "admin/rfpo_preview.html",
                rfpo=rfpo,
                project=project,
                consortium=consortium,
                vendor=vendor,
                vendor_site=vendor_site,
                requestor=requestor,
            )

            return jsonify({"success": True, "html_content": html_content})
        except Exception as template_error:
            # Fallback if template not available in API container
            return jsonify(
                {
                    "success": True,
                    "rfpo": rfpo.to_dict(),
                    "project": project.to_dict() if project else None,
                    "consortium": consortium.to_dict() if consortium else None,
                    "vendor": vendor.to_dict() if vendor else None,
                    "vendor_site": vendor_site.to_dict() if vendor_site else None,
                    "requestor": requestor.to_dict() if requestor else None,
                }
            )

    except Exception as e:
        return _error_response(e)


# ─── FILE UPLOAD / VIEW / DELETE ─────────────────────────────────────────────

ALLOWED_UPLOAD_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff",
    ".ppt", ".pptx", ".rtf", ".odt", ".ods",
}
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

# Magic-byte signatures for file-header validation (extension → byte prefix)
_MAGIC_BYTES = {
    ".pdf":  [b"%PDF"],
    ".png":  [b"\x89PNG"],
    ".jpg":  [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".gif":  [b"GIF87a", b"GIF89a"],
    ".bmp":  [b"BM"],
    ".tiff": [b"II\x2a\x00", b"MM\x00\x2a"],
    ".doc":  [b"\xd0\xcf\x11\xe0"],           # OLE2 (shared with .xls, .ppt)
    ".xls":  [b"\xd0\xcf\x11\xe0"],
    ".ppt":  [b"\xd0\xcf\x11\xe0"],
    ".docx": [b"PK\x03\x04"],                  # ZIP-based (shared with .xlsx, .pptx, .odt, .ods)
    ".xlsx": [b"PK\x03\x04"],
    ".pptx": [b"PK\x03\x04"],
    ".odt":  [b"PK\x03\x04"],
    ".ods":  [b"PK\x03\x04"],
    ".rtf":  [b"{\\rtf"],
}


def _validate_file_header(file_storage, extension):
    """Check that a file's leading bytes match expected magic for its extension.
    Returns True when the extension has no registered signature (e.g. .csv, .txt)."""
    sigs = _MAGIC_BYTES.get(extension)
    if not sigs:
        return True  # No signature to check (plain-text formats)
    pos = file_storage.tell()
    header = file_storage.read(8)
    file_storage.seek(pos)
    return any(header.startswith(sig) for sig in sigs)


@app.route("/api/rfpos/<int:rfpo_id>/files/upload", methods=["POST"])
@require_auth
def upload_rfpo_file(rfpo_id):
    """Upload a file to an RFPO"""
    try:
        rfpo = RFPO.query.get(rfpo_id)
        if not rfpo:
            return jsonify({"success": False, "message": "RFPO not found"}), 404

        if "file" not in request.files:
            return jsonify({"success": False, "message": "No file provided"}), 400

        file = request.files["file"]
        if not file.filename:
            return jsonify({"success": False, "message": "No file selected"}), 400

        document_type = request.form.get("document_type", "")
        description = request.form.get("description", "")

        from werkzeug.utils import secure_filename
        import uuid
        import mimetypes

        original_filename = secure_filename(file.filename)
        if not original_filename:
            return jsonify({"success": False, "message": "Invalid filename"}), 400

        file_extension = os.path.splitext(original_filename)[1].lower()
        if file_extension not in ALLOWED_UPLOAD_EXTENSIONS:
            return jsonify({"success": False, "message": f"File type '{file_extension}' is not allowed"}), 400

        # Validate file header matches claimed extension
        if not _validate_file_header(file, file_extension):
            return jsonify({"success": False, "message": f"File content does not match '{file_extension}' format"}), 400

        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        if file_size > MAX_UPLOAD_SIZE_BYTES:
            return jsonify({"success": False, "message": "File exceeds 10 MB limit"}), 400

        mime_type, _ = mimetypes.guess_type(original_filename)

        file_id = str(uuid.uuid4())
        stored_filename = f"{file_id}_{original_filename}"

        rfpo_dir = os.path.join("uploads", "rfpo_files", f"rfpo_{rfpo.id}")
        os.makedirs(rfpo_dir, exist_ok=True)

        file_path = os.path.join(rfpo_dir, stored_filename)
        file.save(file_path)

        user = request.current_user
        user_name = user.get_display_name() if hasattr(user, "get_display_name") else str(user)

        uploaded_file = UploadedFile(
            file_id=file_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
            file_extension=file_extension,
            document_type=document_type if document_type else None,
            description=description if description else None,
            rfpo_id=rfpo.id,
            uploaded_by=user_name,
        )

        db.session.add(uploaded_file)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f'File "{original_filename}" uploaded successfully',
            "file": uploaded_file.to_dict(),
        })

    except Exception as e:
        db.session.rollback()
        return _error_response(e)


@app.route("/api/rfpos/<int:rfpo_id>/files/<file_id>/view", methods=["GET"])
@require_auth
def view_rfpo_file(rfpo_id, file_id):
    """View/download an uploaded file"""
    try:
        rfpo = RFPO.query.get(rfpo_id)
        if not rfpo:
            return jsonify({"success": False, "message": "RFPO not found"}), 404

        uploaded_file = UploadedFile.query.filter_by(
            file_id=file_id, rfpo_id=rfpo.id
        ).first()
        if not uploaded_file:
            return jsonify({"success": False, "message": "File not found"}), 404

        if not os.path.exists(uploaded_file.file_path):
            return jsonify({"success": False, "message": "File not found on disk"}), 404

        from flask import send_file
        return send_file(
            uploaded_file.file_path,
            mimetype=uploaded_file.mime_type,
            as_attachment=False,
            download_name=uploaded_file.original_filename,
        )

    except Exception as e:
        return _error_response(e)


@app.route("/api/rfpos/<int:rfpo_id>/files/<file_id>", methods=["DELETE"])
@require_auth
def delete_rfpo_file(rfpo_id, file_id):
    """Delete an uploaded file"""
    try:
        rfpo = RFPO.query.get(rfpo_id)
        if not rfpo:
            return jsonify({"success": False, "message": "RFPO not found"}), 404

        uploaded_file = UploadedFile.query.filter_by(
            file_id=file_id, rfpo_id=rfpo.id
        ).first()
        if not uploaded_file:
            return jsonify({"success": False, "message": "File not found"}), 404

        if os.path.exists(uploaded_file.file_path):
            os.remove(uploaded_file.file_path)

        filename = uploaded_file.original_filename
        db.session.delete(uploaded_file)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f'File "{filename}" deleted successfully',
        })

    except Exception as e:
        db.session.rollback()
        return _error_response(e)


@app.route("/api/rfpos/doc-types", methods=["GET"])
@require_auth
def get_doc_types():
    """Get document type options for file upload"""
    try:
        doc_types = List.get_by_type("doc_types")
        types = [
            {"key": dt.key, "value": dt.value}
            for dt in doc_types
            if dt.value and dt.value.strip()
        ]
        return jsonify({"success": True, "doc_types": types})
    except Exception as e:
        return _error_response(e)


if __name__ == "__main__":
    app.logger.info("Starting Simple RFPO API")
    app.logger.info(f"Database: {app.config['SQLALCHEMY_DATABASE_URI']}")

    with app.app_context():
        app.logger.info(f"Users in database: {User.query.count()}")

    app.run(debug=False, host="0.0.0.0", port=5002)
