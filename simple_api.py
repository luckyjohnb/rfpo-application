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
import re
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
    Notification,
    EmailLog,
)
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

with app.app_context():
    db.create_all()


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
    "https://rfpo.uscar.org,"
    "https://rfpo-admin.uscar.org,"
    "https://rfpo-api.uscar.org"
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


def _get_authorized_approver_ids(instance, action):
    """Return the set of user record_ids authorized to execute this action.

    Authorized users are:
    - The designated primary approver (action.approver_id)
    - The backup approver from the workflow step snapshot (if any)

    Admins/super-admins are NOT authorized unless they are the designated approver or backup.
    """
    authorized = {action.approver_id}
    try:
        data = instance.get_instance_data()
        for stage in data.get("stages", []):
            if stage.get("stage_order") == action.stage_order:
                for step in stage.get("steps", []):
                    if step.get("step_order") == action.step_order:
                        backup_id = step.get("backup_approver_id")
                        if backup_id:
                            authorized.add(backup_id)
                        break
                break
    except Exception:
        pass  # If snapshot is corrupt, only primary approver is authorized
    return authorized


def _generate_and_save_pdf_snapshot(rfpo):
    """Generate an RFPO PDF snapshot and save it as an immutable file tied to the RFPO.

    Called at submission time so the PDF is frozen regardless of future data changes.
    Uses the RFPO format (REQUEST FOR PURCHASE ORDER) — not the PO format.
    Returns the relative path to the saved file, or None on failure.
    """
    try:
        from pdf_generator import RFPOPDFGenerator
        import uuid as _uuid

        consortium = Consortium.query.filter_by(consort_id=rfpo.consortium_id).first()
        project = Project.query.filter_by(project_id=rfpo.project_id).first()
        vendor = Vendor.query.get(rfpo.vendor_id) if rfpo.vendor_id else None
        vendor_site = None
        if rfpo.vendor_site_id:
            try:
                vendor_site = VendorSite.query.get(int(rfpo.vendor_site_id))
            except (ValueError, TypeError):
                pass

        if not consortium or not project:
            app.logger.warning(
                "Cannot generate PDF snapshot for RFPO %s: missing consortium or project",
                rfpo.rfpo_id,
            )
            return None

        # Look up requestor for display name
        requestor = None
        if rfpo.requestor_id:
            requestor = User.query.filter_by(record_id=rfpo.requestor_id).first()

        gen = RFPOPDFGenerator(positioning_config=None)
        pdf_buffer = gen.generate_rfpo_pdf(rfpo, consortium, project, vendor, vendor_site, requestor=requestor)

        # Save to uploads/rfpos/<rfpo_id>/snapshots/<timestamp>_snapshot.pdf
        snapshots_dir = os.path.join(app.root_path, "uploads", "rfpos", rfpo.rfpo_id, "snapshots")
        os.makedirs(snapshots_dir, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
        filename = f"{timestamp}_snapshot.pdf"
        filepath = os.path.join(snapshots_dir, filename)
        pdf_bytes = pdf_buffer.getvalue()
        with open(filepath, "wb") as f:
            f.write(pdf_bytes)

        relative_path = f"uploads/rfpos/{rfpo.rfpo_id}/snapshots/{filename}"
        app.logger.info("PDF snapshot saved for RFPO %s: %s", rfpo.rfpo_id, relative_path)

        # Upload PDF snapshot to cloud storage
        try:
            from docupload_client import upload_to_docupload, is_configured
            if is_configured():
                upload_to_docupload(
                    files={"snapshot": (filename, pdf_bytes, "application/pdf")},
                    folder_path=f"rfpo/{rfpo.rfpo_id}/snapshots",
                    form_id="rfpo-snapshot",
                    submitted_by="system",
                    tags={"rfpo-id": rfpo.rfpo_id, "asset-type": "pdf-snapshot", "source": "rfpo-api"},
                )
        except Exception as cloud_err:
            app.logger.warning("DOCUPLOAD snapshot upload failed for RFPO %s: %s", rfpo.rfpo_id, cloud_err)

        return relative_path

    except Exception as e:
        app.logger.error("PDF snapshot generation failed for RFPO %s: %s", rfpo.rfpo_id, e)
        return None


def _find_applicable_workflow_and_stage(rfpo):
    """Find the best applicable workflow + stage for an RFPO.

    Lookup priority: project → team → consortium.
    A workflow is only accepted if it has at least one stage with steps.
    Falls through to the next level if the found workflow is incomplete.

    Returns (workflow, applicable_stage) or (None, None).
    """
    rfpo_total = float(rfpo.total_amount or 0)

    candidates = []
    if rfpo.project_id:
        w = RFPOApprovalWorkflow.query.filter_by(
            project_id=rfpo.project_id, workflow_type="project",
            is_active=True, is_template=True
        ).first()
        if w:
            candidates.append(w)
    if rfpo.team_id:
        w = RFPOApprovalWorkflow.query.filter_by(
            team_id=rfpo.team_id, workflow_type="team", is_active=True, is_template=True
        ).first()
        if w:
            candidates.append(w)
    if rfpo.consortium_id:
        w = RFPOApprovalWorkflow.query.filter_by(
            consortium_id=rfpo.consortium_id, workflow_type="consortium",
            is_active=True, is_template=True
        ).first()
        if w:
            candidates.append(w)

    for workflow in candidates:
        if not workflow.stages:
            continue

        # Find applicable stage based on amount — only match if the RFPO
        # total actually fits within a defined bracket.  When the amount
        # exceeds every bracket in this workflow we must NOT silently fall
        # back to the highest bracket; instead skip this workflow so the
        # next priority level (team → consortium) gets a chance.
        applicable_stage = None
        for stage in sorted(workflow.stages, key=lambda s: float(s.budget_bracket_amount or 0)):
            if rfpo_total <= float(stage.budget_bracket_amount or 0):
                applicable_stage = stage
                break

        if applicable_stage and applicable_stage.steps:
            return workflow, applicable_stage
        # Amount exceeds all brackets for this workflow — fall through to next

    return None, None


def _find_all_applicable_workflows_and_stages(rfpo):
    """Find ALL applicable workflows and their cumulative stages for an RFPO.

    Collects workflows from all levels: project, team, consortium.
    Within each workflow, returns ALL stages at or below the matching bracket
    (cumulative/cascading) — higher-value purchases require everything lower
    tiers require, plus more.

    Returns list of (workflow, [stages]) tuples. Each tuple has the workflow
    and a list of applicable stages sorted by bracket amount ascending.
    """
    rfpo_total = float(rfpo.total_amount or 0)
    results = []

    workflow_queries = []
    if rfpo.project_id:
        w = RFPOApprovalWorkflow.query.filter_by(
            project_id=rfpo.project_id, workflow_type="project",
            is_active=True, is_template=True
        ).first()
        if w:
            workflow_queries.append(w)
    if rfpo.team_id:
        w = RFPOApprovalWorkflow.query.filter_by(
            team_id=rfpo.team_id, workflow_type="team", is_active=True, is_template=True
        ).first()
        if w:
            workflow_queries.append(w)
    if rfpo.consortium_id:
        w = RFPOApprovalWorkflow.query.filter_by(
            consortium_id=rfpo.consortium_id, workflow_type="consortium",
            is_active=True, is_template=True
        ).first()
        if w:
            workflow_queries.append(w)

    for workflow in workflow_queries:
        if not workflow.stages:
            continue

        sorted_stages = sorted(workflow.stages, key=lambda s: float(s.budget_bracket_amount or 0))

        # Cumulative: collect ALL stages at or below the matching bracket
        cumulative_stages = []
        for stage in sorted_stages:
            cumulative_stages.append(stage)
            if rfpo_total <= float(stage.budget_bracket_amount or 0):
                break  # This is the ceiling — include it and stop
        else:
            # Amount exceeds all brackets — skip this workflow entirely
            continue

        # Only include if at least one stage has steps
        stages_with_steps = [s for s in cumulative_stages if s.steps]
        if stages_with_steps:
            results.append((workflow, cumulative_stages))

    return results


def _find_global_workflow_stages():
    """Find the active global workflow and return its stages (sections) with steps.

    Returns a list of stages that have steps, ordered by stage_order.
    Returns empty list if no global workflow is active or has no stages with steps.
    """
    global_workflow = RFPOApprovalWorkflow.query.filter_by(
        workflow_type="global", is_active=True, is_template=True
    ).first()

    if not global_workflow or not global_workflow.stages:
        return []

    return [stage for stage in sorted(global_workflow.stages, key=lambda s: s.stage_order)
            if stage.steps]


def _validate_rfpo_for_approval(rfpo):
    """Validate an RFPO is ready for submission — checks fields, line items, files, workflow."""
    rfpo_total = float(rfpo.total_amount or 0)
    result = {
        "is_valid": True,
        "errors": [],
        "warnings": [],
        "sections": {
            "basic_info": {"complete": bool(rfpo.title and rfpo.title.strip()), "label": "Basic Information"},
            "vendor": {"complete": rfpo.vendor_id is not None, "label": "Vendor"},
            "line_items": {"complete": bool(rfpo.line_items and len(rfpo.line_items) > 0), "label": "Line Items"},
            "total": {"complete": bool(rfpo.total_amount and float(rfpo.total_amount) > 0), "label": "Total Amount"},
        },
        "files": {
            "uploaded_count": len(rfpo.files) if rfpo.files else 0,
            "required_documents": [],
            "missing_documents": [],
            "document_status": [],
        },
        "workflow_info": None,
    }

    # Basic field validation
    if not result["sections"]["basic_info"]["complete"]:
        result["errors"].append("RFPO title is required")
        result["is_valid"] = False
    if not result["sections"]["vendor"]["complete"]:
        result["warnings"].append("No vendor selected")
    if not result["sections"]["line_items"]["complete"]:
        result["errors"].append("RFPO must have at least one line item")
        result["is_valid"] = False
    if not result["sections"]["total"]["complete"]:
        result["errors"].append("RFPO total amount must be greater than zero")
        result["is_valid"] = False

    # Find applicable workflows — cumulative across ALL levels + global
    all_entity_workflows = _find_all_applicable_workflows_and_stages(rfpo)
    global_stages = _find_global_workflow_stages()

    # Also keep legacy single-winner lookup for backward compat (workflow_info display)
    workflow, applicable_stage = _find_applicable_workflow_and_stage(rfpo)

    if not all_entity_workflows and not global_stages:
        result["errors"].append("No active approval workflow found for this RFPO")
        result["is_valid"] = False
        return result

    # Build cumulative list of ALL applicable stages across all workflows
    # Order: entity stages (lowest bracket first, across project→team→consortium) → global stages
    all_entity_stages = []
    for _wf, stages in all_entity_workflows:
        for stage in stages:
            all_entity_stages.append(stage)

    GLOBAL_VALIDATION_ORDER = {
        "GLOBAL_FINANCIAL": 1,
        "GLOBAL_USCAR_INTERNAL": 2,
        "GLOBAL_PO_RELEASE": 3,
    }
    sorted_global_stages = sorted(
        global_stages,
        key=lambda s: GLOBAL_VALIDATION_ORDER.get((s.budget_bracket_key or "").upper(), 99)
    )
    all_stages_for_validation = all_entity_stages + sorted_global_stages

    # Collect approver info — dedup by approval_type_key, keeping tiered order
    approver_info = []
    seen_approval_types = set()
    for vstage in all_stages_for_validation:
        for step in sorted(vstage.steps, key=lambda s: s.step_order):
            dedup_key = step.approval_type_key
            if dedup_key and dedup_key in seen_approval_types:
                continue
            if dedup_key:
                seen_approval_types.add(dedup_key)
            approver = User.query.filter_by(record_id=step.primary_approver_id, active=True).first()
            approver_info.append({
                "step_name": step.step_name,
                "approval_type": step.approval_type_name,
                "approver_name": approver.get_display_name() if approver else "Unknown",
                "approver_valid": approver is not None,
                "stage_name": vstage.stage_name,
            })
            if not approver:
                result["errors"].append(f"Approver not found for step: {step.step_name}")
                result["is_valid"] = False

    wf_name = workflow.name if workflow else "Global Approvers"
    stg_name = applicable_stage.stage_name if applicable_stage else "Global Only"
    stg_amount = float(applicable_stage.budget_bracket_amount or 0) if applicable_stage else 0

    result["workflow_info"] = {
        "workflow_name": wf_name,
        "stage_name": stg_name,
        "budget_bracket": stg_amount,
        "rfpo_amount": rfpo_total,
        "approval_steps": approver_info,
    }

    # Required document validation — aggregate across ALL stages (entity + global)
    required_doc_keys = []
    seen_keys = set()
    for vstage in all_stages_for_validation:
        if hasattr(vstage, 'get_required_document_types'):
            for key in vstage.get_required_document_types():
                if key not in seen_keys:
                    required_doc_keys.append(key)
                    seen_keys.add(key)

    if required_doc_keys:
        uploaded_doc_types = [f.document_type for f in rfpo.files if f.document_type]

        for key in required_doc_keys:
            doc_item = List.query.filter_by(type="doc_types", key=key, active=True).first()
            doc_name = doc_item.value if doc_item and doc_item.value and doc_item.value.strip() else key
            is_uploaded = key in uploaded_doc_types or doc_name in uploaded_doc_types

            result["files"]["required_documents"].append(doc_name)
            result["files"]["document_status"].append({
                "key": key,
                "name": doc_name,
                "is_uploaded": is_uploaded,
            })
            if not is_uploaded:
                result["files"]["missing_documents"].append(doc_name)

        if result["files"]["missing_documents"]:
            missing = ", ".join(result["files"]["missing_documents"])
            result["errors"].append(f"Missing required documents: {missing}")
            result["is_valid"] = False

    # Count complete sections
    sections_done = sum(1 for s in result["sections"].values() if s["complete"])
    sections_total = len(result["sections"])
    # Include files section
    has_doc_req = len(result["files"]["required_documents"]) > 0
    files_complete = (not has_doc_req) or (len(result["files"]["missing_documents"]) == 0)
    result["sections"]["files"] = {
        "complete": files_complete,
        "label": "Required Documents",
        "has_requirements": has_doc_req,
    }
    sections_done = sum(1 for s in result["sections"].values() if s["complete"])
    sections_total = len(result["sections"])
    result["completeness"] = {
        "done": sections_done,
        "total": sections_total,
        "percent": int(sections_done / sections_total * 100) if sections_total > 0 else 0,
    }

    return result

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

            # Check permissions_version — reject tokens issued before a
            # restrictive permission change so stale privileges can't be used.
            token_pv = payload.get("pv", 0)
            current_pv = user.permissions_version or 0
            if token_pv < current_pv:
                app.logger.warning(
                    "Token rejected for %s: permissions_version mismatch "
                    "(token=%s, current=%s)", user.email, token_pv, current_pv,
                )
                return jsonify({
                    "error": "permissions_changed",
                    "message": "Your permissions have been updated. Please log in again.",
                }), 401

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

    # Create token (pv = permissions_version for forced re-auth on restriction)
    token = jwt.encode(
        {
            "user_id": user.id,
            "pv": user.permissions_version or 0,
            "exp": datetime.utcnow() + timedelta(hours=24),
        },
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


@app.route("/api/auth/sso-token", methods=["POST"])
@require_auth
def generate_sso_token():
    """Generate a short-lived SSO token for admin panel cross-auth. Admin/GOD only."""
    user = request.current_user
    perms = user.get_permissions() or []
    if "RFPO_ADMIN" not in perms and "GOD" not in perms:
        return jsonify({"success": False, "message": "Admin access required"}), 403

    sso_token = jwt.encode(
        {
            "user_id": user.id,
            "purpose": "admin_sso",
            "pv": user.permissions_version or 0,
            "exp": datetime.utcnow() + timedelta(seconds=30),
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    return jsonify({"success": True, "sso_token": sso_token})


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


@app.route("/api/teams", methods=["POST"])
@require_auth
def create_team():
    """Create a new team (admin only)"""
    user = request.current_user
    user_perms = user.get_permissions() or []
    if "RFPO_ADMIN" not in user_perms and "GOD" not in user_perms:
        return jsonify({"success": False, "message": "Admin access required"}), 403

    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        name = (data.get("name") or "").strip()
        abbrev = (data.get("abbrev") or "").strip().upper()
        consortium_id = (data.get("consortium_id") or "").strip()

        if not name:
            return jsonify({"success": False, "message": "Team name is required"}), 400
        if not abbrev:
            return jsonify({"success": False, "message": "Abbreviation is required"}), 400
        if not re.match(r'^[A-Z0-9\-]+$', abbrev):
            return jsonify({"success": False, "message": "Abbreviation must contain only letters, numbers, and hyphens"}), 400
        if not consortium_id:
            return jsonify({"success": False, "message": "Consortium is required"}), 400

        # Check uniqueness
        if Team.query.filter_by(abbrev=abbrev).first():
            return jsonify({"success": False, "message": "Abbreviation already in use"}), 400

        from api.utils import generate_next_id
        record_id = generate_next_id(Team, "record_id", "", 8)

        team = Team(
            record_id=record_id,
            name=name,
            abbrev=abbrev,
            description=(data.get("description") or "").strip() or None,
            consortium_consort_id=consortium_id,
            active=True,
            created_by=user.email,
        )

        # Set team member IDs if provided
        viewer_ids = data.get("rfpo_viewer_user_ids")
        admin_ids = data.get("rfpo_admin_user_ids")
        if viewer_ids and isinstance(viewer_ids, list):
            team.set_rfpo_viewer_users(viewer_ids)
        if admin_ids and isinstance(admin_ids, list):
            team.set_rfpo_admin_users(admin_ids)

        db.session.add(team)
        db.session.commit()

        return jsonify({"success": True, "team": team.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return _error_response(e)


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
                    user.email, user.fullname, user_ip,
                    context={'user_id': user.id},
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

        # Issue JWT (pv = permissions_version for forced re-auth on restriction)
        token = jwt.encode(
            {
                "user_id": user.id,
                "pv": user.permissions_version or 0,
                "exp": datetime.utcnow() + timedelta(hours=24),
            },
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
        # Filter by current stage; for parallel stages allow any step in the stage,
        # for sequential stages also require step_order to match.
        pending_actions_raw = (
            RFPOApprovalAction.query
            .join(RFPOApprovalInstance, RFPOApprovalAction.instance_id == RFPOApprovalInstance.id)
            .filter(
                RFPOApprovalAction.approver_id == user.record_id,
                RFPOApprovalAction.status == "pending",
                RFPOApprovalInstance.overall_status == "waiting",
                RFPOApprovalAction.stage_order == RFPOApprovalInstance.current_stage_order,
            )
            .all()
        )
        # Post-filter: for non-parallel stages, also require step_order match
        pending_actions = []
        for pa in pending_actions_raw:
            inst = pa.instance
            stage_data = inst.get_current_stage()
            if stage_data and stage_data.get("is_parallel"):
                pending_actions.append(pa)  # parallel: any step in stage
            elif pa.step_order == inst.current_step_order:
                pending_actions.append(pa)  # sequential: must match step

        # Also find actions where user is backup approver (from instance snapshots)
        # Only for the current stage/step of active instances
        all_active_instances = RFPOApprovalInstance.query.filter(
            RFPOApprovalInstance.overall_status == "waiting",
        ).all()

        backup_action_ids = set()
        for inst in all_active_instances:
            try:
                data = inst.get_instance_data()
                for stage in data.get("stages", []):
                    # Only check the current stage
                    if stage.get("stage_order") != inst.current_stage_order:
                        continue
                    is_parallel = stage.get("is_parallel", False)
                    for step in stage.get("steps", []):
                        # For sequential stages, also require step_order match
                        if not is_parallel and step.get("step_order") != inst.current_step_order:
                            continue
                        if step.get("backup_approver_id") == user.record_id:
                            for act in inst.actions:
                                if (act.status == "pending"
                                        and act.stage_order == stage.get("stage_order")
                                        and act.step_order == step.get("step_order")):
                                    backup_action_ids.add(act.id)
            except Exception as inst_err:
                app.logger.warning(
                    "Skipping corrupted approval instance %s (RFPO %s): %s",
                    inst.id, getattr(inst, 'rfpo_id', '?'), inst_err,
                )
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
        return jsonify({"success": False, "message": "Failed to load approval queue. Please try again or contact support."}), 500


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

        # Check if user is authorized (primary approver or backup only)
        authorized_ids = _get_authorized_approver_ids(action.instance, action)
        if user.record_id not in authorized_ids:
            app.logger.warning(
                "SECURITY: User %s (record_id=%s) attempted to approve action %s "
                "(authorized: %s)",
                user.email, user.record_id, action_id, authorized_ids,
            )
            return (
                jsonify(
                    {"success": False, "message": "Not authorized to take this action. "
                     "Only the designated approver or backup approver can act."}
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

        # Enforce sequential ordering — action must match the current stage pointer.
        # For parallel stages, any step within the stage is allowed.
        instance = action.instance
        if action.stage_order != instance.current_stage_order:
            return (
                jsonify(
                    {"success": False,
                     "message": "This approval step is not yet active. "
                                "Earlier steps must be completed first."}
                ),
                409,
            )
        if action.step_order != instance.current_step_order:
            current_stage_data = instance.get_current_stage()
            if not current_stage_data or not current_stage_data.get("is_parallel"):
                return (
                    jsonify(
                        {"success": False,
                         "message": "This approval step is not yet active. "
                                    "Earlier steps must be completed first."}
                    ),
                    409,
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
                # Generate PO number on final approval
                if not instance.rfpo.po_number:
                    consortium = Consortium.query.filter_by(
                        consort_id=instance.rfpo.consortium_id
                    ).first()
                    abbrev = consortium.abbrev if consortium else "GEN"
                    instance.rfpo.po_number = RFPO.generate_po_number(abbrev)
                    app.logger.info(
                        "PO number %s assigned to RFPO %s on approval (API)",
                        instance.rfpo.po_number, instance.rfpo.rfpo_id,
                    )
        else:
            # For approvals, advance workflow and check for completion
            instance.advance_to_next_step()

            # If workflow is now complete and approved, update RFPO status
            if instance.overall_status == "approved" and instance.rfpo:
                instance.rfpo.status = "Approved"
                instance.rfpo.updated_by = user.get_display_name()
                # Generate PO number on final approval
                if not instance.rfpo.po_number:
                    consortium = Consortium.query.filter_by(
                        consort_id=instance.rfpo.consortium_id
                    ).first()
                    abbrev = consortium.abbrev if consortium else "GEN"
                    instance.rfpo.po_number = RFPO.generate_po_number(abbrev)
                    app.logger.info(
                        "PO number %s assigned to RFPO %s on approval (API)",
                        instance.rfpo.po_number, instance.rfpo.rfpo_id,
                    )

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

        # Collect notification data and email tasks before returning.
        # In-app notifications are fast DB inserts (synchronous).
        # Emails are sent in a background thread to avoid blocking the
        # response — ACS/SMTP calls can take several seconds each.
        email_tasks = []  # list of (email, name, rfpo_id_str, subject, db_id, ctx)
        try:
            # Snapshot values we need (before leaving request context)
            _overall_status = instance.overall_status
            _rfpo_id_str = instance.rfpo.rfpo_id if instance.rfpo else None
            _rfpo_db_id = instance.rfpo.id if instance.rfpo else None
            _rfpo_ctx = (
                {'rfpo_id': instance.rfpo.id, 'project_id': instance.rfpo.project_id,
                 'consortium_id': instance.rfpo.consortium_id, 'team_id': instance.rfpo.team_id}
                if instance.rfpo else {}
            )

            # Notify requestor if workflow completed
            if _overall_status in ("approved", "refused") and instance.rfpo:
                requestor = User.query.filter_by(
                    record_id=instance.rfpo.created_by
                ).first() if instance.rfpo.created_by else None
                if requestor and requestor.email:
                    email_tasks.append((
                        requestor.email, requestor.get_display_name(),
                        _rfpo_id_str, f"RFPO {_overall_status.title()}",
                        _rfpo_db_id, _rfpo_ctx,
                    ))
                # In-app notification for requestor
                if requestor:
                    _create_notification(
                        user_id=requestor.id,
                        notif_type="rfpo_status",
                        title=f"RFPO {_overall_status.title()}",
                        message=f"RFPO {_rfpo_id_str} has been {_overall_status}.",
                        link=f"/rfpos/{_rfpo_db_id}",
                        entity_type="rfpo",
                        entity_id=str(_rfpo_db_id),
                    )
                # If refused, also notify remaining pending approvers so they
                # know the RFPO has been terminated and can clear their queues.
                if _overall_status == "refused" and instance.rfpo:
                    remaining = RFPOApprovalAction.query.filter_by(
                        instance_id=instance.id, status="pending",
                    ).all()
                    for ra in remaining:
                        peer = User.query.filter_by(record_id=ra.approver_id, active=True).first()
                        if peer and peer.email:
                            email_tasks.append((
                                peer.email, peer.get_display_name(),
                                _rfpo_id_str,
                                "RFPO Refused — No Action Required",
                                _rfpo_db_id, _rfpo_ctx,
                            ))
                        if peer:
                            _create_notification(
                                user_id=peer.id,
                                notif_type="rfpo_status",
                                title="RFPO Refused",
                                message=f"RFPO {_rfpo_id_str} has been refused. No action is required.",
                                link=f"/rfpos/{_rfpo_db_id}",
                                entity_type="rfpo",
                                entity_id=str(_rfpo_db_id),
                            )
            else:
                # Notify the next active approver(s)
                # For parallel stages, notify all pending in the stage
                if instance.rfpo:
                    adv_stage_data = instance.get_current_stage()
                    if adv_stage_data and adv_stage_data.get("is_parallel"):
                        next_actions = RFPOApprovalAction.query.filter_by(
                            instance_id=instance.id, status="pending",
                            stage_order=instance.current_stage_order,
                        ).all()
                    else:
                        next_actions = RFPOApprovalAction.query.filter_by(
                            instance_id=instance.id, status="pending",
                            stage_order=instance.current_stage_order,
                            step_order=instance.current_step_order,
                        ).all()
                    for na in next_actions:
                        next_approver = User.query.filter_by(record_id=na.approver_id, active=True).first()
                        if next_approver:
                            email_tasks.append((
                                next_approver.email,
                                next_approver.get_display_name(),
                                _rfpo_id_str,
                                na.step_name or "Approval Required",
                                _rfpo_db_id, _rfpo_ctx,
                            ))
                            # In-app notification
                            _create_notification(
                                user_id=next_approver.id,
                                notif_type="approval_request",
                                title="Approval Step Ready",
                                message=f"RFPO {_rfpo_id_str} is ready for your review ({na.step_name}).",
                                link=f"/rfpos/{_rfpo_db_id}",
                                entity_type="rfpo",
                                entity_id=str(_rfpo_db_id),
                            )
            db.session.commit()  # persist notifications
        except Exception as notif_err:
            app.logger.warning(f"Notification setup failed: {notif_err}")

        # Build the response first, then fire emails in background
        response_data = {
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

        # Fire email notifications in a background thread so the API
        # returns immediately.  Each task is a tuple of plain values
        # (no ORM objects) so it's safe outside the request context.
        if email_tasks:
            def _send_emails(tasks):
                try:
                    from email_service import send_approval_notification
                    for email, name, rfpo_id_str, subj, db_id, ctx in tasks:
                        try:
                            send_approval_notification(
                                email, name, rfpo_id_str, subj,
                                rfpo_db_id=db_id, context=ctx,
                            )
                        except Exception as e:
                            logging.getLogger(__name__).warning(
                                "Background email to %s failed: %s", email, e,
                            )
                except Exception as e:
                    logging.getLogger(__name__).warning(
                        "Background email thread error: %s", e,
                    )

            t = threading.Thread(target=_send_emails, args=(email_tasks,), daemon=True)
            t.start()

        return jsonify(response_data)

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
                bulk_authorized = _get_authorized_approver_ids(action.instance, action)
                if user.record_id not in bulk_authorized:
                    results["failed"] += 1
                    results["errors"].append(f"{action_id}: not authorized")
                    continue
                if action.status != "pending":
                    results["failed"] += 1
                    results["errors"].append(f"{action_id}: already completed")
                    continue

                # Enforce sequential ordering (parallel stages allow any step)
                bulk_instance = action.instance
                if action.stage_order != bulk_instance.current_stage_order:
                    results["failed"] += 1
                    results["errors"].append(f"{action_id}: step not yet active")
                    continue
                if action.step_order != bulk_instance.current_step_order:
                    bulk_stage_data = bulk_instance.get_current_stage()
                    if not bulk_stage_data or not bulk_stage_data.get("is_parallel"):
                        results["failed"] += 1
                        results["errors"].append(f"{action_id}: step not yet active")
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

        # Collect email tasks, then fire in background thread.
        bulk_email_tasks = []
        try:
            processed_instances = set()
            for action_id in action_ids:
                act = RFPOApprovalAction.query.filter_by(action_id=action_id).first()
                if not act or act.instance_id in processed_instances:
                    continue
                processed_instances.add(act.instance_id)
                inst = act.instance
                if not inst or not inst.rfpo:
                    continue
                _rfpo_id_str = inst.rfpo.rfpo_id
                _rfpo_db_id = inst.rfpo.id
                _rfpo_ctx = {'rfpo_id': inst.rfpo.id, 'project_id': inst.rfpo.project_id,
                             'consortium_id': inst.rfpo.consortium_id, 'team_id': inst.rfpo.team_id}
                if inst.overall_status in ("approved", "refused"):
                    # Workflow completed — notify requestor
                    requestor = User.query.filter_by(
                        record_id=inst.rfpo.created_by
                    ).first() if inst.rfpo.created_by else None
                    if requestor and requestor.email:
                        bulk_email_tasks.append((
                            requestor.email, requestor.get_display_name(),
                            _rfpo_id_str, f"RFPO {inst.overall_status.title()}",
                            _rfpo_db_id, _rfpo_ctx,
                        ))
                    # If refused, also notify remaining pending approvers
                    if inst.overall_status == "refused":
                        remaining = RFPOApprovalAction.query.filter_by(
                            instance_id=inst.id, status="pending",
                        ).all()
                        for ra in remaining:
                            peer = User.query.filter_by(record_id=ra.approver_id, active=True).first()
                            if peer and peer.email:
                                bulk_email_tasks.append((
                                    peer.email, peer.get_display_name(),
                                    _rfpo_id_str,
                                    "RFPO Refused — No Action Required",
                                    _rfpo_db_id, _rfpo_ctx,
                                ))
                else:
                    # Workflow advanced — notify next active approver(s)
                    bulk_notif_stage = inst.get_current_stage()
                    if bulk_notif_stage and bulk_notif_stage.get("is_parallel"):
                        next_actions = RFPOApprovalAction.query.filter_by(
                            instance_id=inst.id, status="pending",
                            stage_order=inst.current_stage_order,
                        ).all()
                    else:
                        next_actions = RFPOApprovalAction.query.filter_by(
                            instance_id=inst.id, status="pending",
                            stage_order=inst.current_stage_order,
                            step_order=inst.current_step_order,
                        ).all()
                    for na in next_actions:
                        next_approver = User.query.filter_by(record_id=na.approver_id, active=True).first()
                        if next_approver and next_approver.email:
                            bulk_email_tasks.append((
                                next_approver.email, next_approver.get_display_name(),
                                _rfpo_id_str, na.step_name or "Approval Required",
                                _rfpo_db_id, _rfpo_ctx,
                            ))
        except Exception as notif_err:
            app.logger.warning(f"Bulk approval notification setup failed: {notif_err}")

        # Fire emails in background thread
        if bulk_email_tasks:
            def _send_bulk_emails(tasks):
                try:
                    from email_service import send_approval_notification
                    for email, name, rfpo_id_str, subj, db_id, ctx in tasks:
                        try:
                            send_approval_notification(
                                email, name, rfpo_id_str, subj,
                                rfpo_db_id=db_id, context=ctx,
                            )
                        except Exception as e:
                            logging.getLogger(__name__).warning(
                                "Background bulk email to %s failed: %s", email, e,
                            )
                except Exception as e:
                    logging.getLogger(__name__).warning(
                        "Background bulk email thread error: %s", e,
                    )

            t = threading.Thread(target=_send_bulk_emails, args=(bulk_email_tasks,), daemon=True)
            t.start()

        return jsonify({
            "success": True,
            "message": f"{results['succeeded']} action(s) {status} successfully" +
                       (f", {results['failed']} failed" if results["failed"] else ""),
            "results": results,
        })

    except Exception as e:
        db.session.rollback()
        return _error_response(e)


@app.route("/api/rfpos/<int:rfpo_id>/validate", methods=["GET"])
@require_auth
def validate_rfpo(rfpo_id):
    """Check if an RFPO is ready for submission."""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)
        result = _validate_rfpo_for_approval(rfpo)
        return jsonify({"success": True, "validation": result})
    except Exception as e:
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

        # Validate RFPO readiness before submission
        validation = _validate_rfpo_for_approval(rfpo)
        if not validation["is_valid"]:
            return jsonify({
                "success": False,
                "message": "RFPO is not ready for submission",
                "errors": validation["errors"],
                "validation": validation,
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
        # Cumulative: collect ALL applicable workflows and stages across project→team→consortium
        all_entity_workflows = _find_all_applicable_workflows_and_stages(rfpo)
        global_stages = _find_global_workflow_stages()
        # Legacy single-winner for template reference
        workflow, applicable_stage = _find_applicable_workflow_and_stage(rfpo)

        if not all_entity_workflows and not global_stages:
            return jsonify({
                "success": False,
                "message": "No active approval workflow found for this RFPO's team or consortium. "
                           "Please configure a workflow in the admin panel first."
            }), 400

        # Build combined stages: entity stages (by bracket, across all workflow levels)
        # → global stages (Financial → US Car Internal → PO Release)
        def _build_stage_data(stage, is_global=False):
            steps_data = []
            for step in sorted(stage.steps, key=lambda s: s.step_order):
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
            return {
                "stage_id": stage.stage_id,
                "stage_name": stage.stage_name,
                "stage_order": 0,  # Will be renumbered below
                "budget_bracket_key": stage.budget_bracket_key,
                "budget_bracket_amount": float(stage.budget_bracket_amount or 0),
                "requires_all_steps": stage.requires_all_steps,
                "is_parallel": stage.is_parallel,
                "is_global": is_global,
                "steps": steps_data,
            }

        # Entity stages: cumulative from all workflows, lowest bracket first
        entity_stage_data = []
        for _wf, stages in all_entity_workflows:
            for stage in stages:
                if stage.steps:
                    entity_stage_data.append(_build_stage_data(stage, is_global=False))

        # Dedup entity stages by approval_type_key across steps — keep tiered order
        # (lower brackets come first, so their steps win the dedup)
        seen_approval_types = set()
        deduped_entity_stages = []
        for stage_data in entity_stage_data:
            deduped_steps = []
            for step in stage_data["steps"]:
                atype = step["approval_type_key"]
                if atype and atype in seen_approval_types:
                    continue
                if atype:
                    seen_approval_types.add(atype)
                deduped_steps.append(step)
            if deduped_steps:
                stage_data["steps"] = deduped_steps
                deduped_entity_stages.append(stage_data)

        # Global stages in fixed order: Financial → US Car Internal → PO Release
        GLOBAL_STAGE_ORDER = {
            "GLOBAL_FINANCIAL": 1,
            "GLOBAL_USCAR_INTERNAL": 2,
            "GLOBAL_PO_RELEASE": 3,
        }
        global_stage_data = []
        for gs in global_stages:
            gkey = (gs.budget_bracket_key or "").upper()
            gsd = _build_stage_data(gs, is_global=True)
            # Dedup global steps against already-seen entity approval types
            deduped_steps = []
            for step in gsd["steps"]:
                atype = step["approval_type_key"]
                if atype and atype in seen_approval_types:
                    continue
                if atype:
                    seen_approval_types.add(atype)
                deduped_steps.append(step)
            if deduped_steps:
                gsd["steps"] = deduped_steps
                gsd["_sort_key"] = GLOBAL_STAGE_ORDER.get(gkey, 99)
                global_stage_data.append(gsd)
        global_stage_data.sort(key=lambda s: s["_sort_key"])
        for gsd in global_stage_data:
            gsd.pop("_sort_key", None)

        # Combine: entity stages (tiered) → global stages (Financial → US Car Internal → PO Release)
        stages_data = deduped_entity_stages + global_stage_data

        # Renumber stage_order sequentially (1-based)
        for idx, stage in enumerate(stages_data, start=1):
            stage["stage_order"] = idx

        if not stages_data:
            return jsonify({
                "success": False,
                "message": "No approval stages with steps found for this RFPO"
            }), 400

        # Determine which workflow to reference as template
        template_workflow = workflow
        if not template_workflow:
            # If no consortium workflow, reference the global workflow
            global_wf = RFPOApprovalWorkflow.query.filter_by(
                workflow_type="global", is_active=True, is_template=True
            ).first()
            template_workflow = global_wf

        # Create the approval instance
        instance = RFPOApprovalInstance(
            instance_id=uuid_mod.uuid4().hex[:16],
            rfpo_id=rfpo.id,
            template_workflow_id=template_workflow.id,
            workflow_name=template_workflow.name,
            workflow_version=template_workflow.version or "1.0",
            consortium_id=rfpo.consortium_id or (workflow.consortium_id if workflow else "") or "",
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

        # Generate and save PDF snapshot at submission time
        snapshot_path = _generate_and_save_pdf_snapshot(rfpo)
        if snapshot_path:
            rfpo.pdf_snapshot_path = snapshot_path

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
            "workflow_name": template_workflow.name,
            "instance_id": instance.instance_id,
            "total_amount": float(rfpo.total_amount or 0),
        })
        db.session.add(audit)

        # In-app notifications (fast DB inserts — keep synchronous)
        first_stage = stages_data[0] if stages_data else None
        email_tasks = []
        if first_stage:
            for step_data in first_stage["steps"]:
                approver = User.query.filter_by(
                    record_id=step_data["primary_approver_id"], active=True
                ).first()
                if approver:
                    _create_notification(
                        user_id=approver.id,
                        notif_type="approval_request",
                        title="New Approval Required",
                        message=f"RFPO {rfpo.rfpo_id} ({rfpo.title}) needs your approval.",
                        link=f"/rfpos/{rfpo.id}",
                        entity_type="rfpo",
                        entity_id=str(rfpo.id),
                    )
                    if approver.email:
                        email_tasks.append((
                            approver.email,
                            approver.get_display_name(),
                            rfpo.rfpo_id,
                            step_data["approval_type_name"],
                            rfpo.id,
                            {'rfpo_id': rfpo.id, 'project_id': rfpo.project_id,
                             'consortium_id': rfpo.consortium_id, 'team_id': rfpo.team_id},
                        ))

        db.session.commit()

        # Build response before firing background emails
        response_data = {
            "success": True,
            "message": f"RFPO submitted for approval via '{template_workflow.name}'",
            "instance": instance.to_dict(),
            "rfpo_status": rfpo.status,
        }

        # Fire emails in background thread (non-blocking)
        if email_tasks:
            def _send_submit_emails(tasks):
                from email_service import send_approval_notification
                for email, name, rfpo_id_str, approval_type, db_id, ctx in tasks:
                    try:
                        send_approval_notification(
                            email, name, rfpo_id_str, approval_type,
                            rfpo_db_id=db_id, context=ctx,
                        )
                    except Exception as e:
                        logging.getLogger(__name__).warning(
                            "Background email to %s failed: %s", email, e
                        )

            threading.Thread(target=_send_submit_emails, args=(email_tasks,), daemon=True).start()

        return jsonify(response_data), 201

    except Exception as e:
        db.session.rollback()
        return _error_response(e)


@app.route("/api/rfpos/<int:rfpo_id>/pdf-snapshot")
@require_auth
def get_pdf_snapshot(rfpo_id):
    """Serve the immutable PDF snapshot generated at submission time."""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)
        if not rfpo.pdf_snapshot_path:
            return jsonify({"success": False, "message": "No PDF snapshot available for this RFPO"}), 404

        filepath = os.path.join(app.root_path, rfpo.pdf_snapshot_path)
        if not os.path.isfile(filepath):
            return jsonify({"success": False, "message": "PDF snapshot file not found on disk"}), 404

        from flask import send_file
        return send_file(
            filepath,
            mimetype="application/pdf",
            download_name=f"RFPO_SNAPSHOT_{rfpo.rfpo_id}.pdf",
            as_attachment=False,
        )
    except Exception as e:
        return _error_response(e)


@app.route("/api/rfpos/<int:rfpo_id>/regenerate-snapshot", methods=["POST"])
@require_auth
def regenerate_pdf_snapshot(rfpo_id):
    """Regenerate the PDF snapshot for an RFPO (admin only)."""
    try:
        user = request.current_user
        user_perms = user.get_permissions() or []
        if "RFPO_ADMIN" not in user_perms and "GOD" not in user_perms:
            return jsonify({"success": False, "message": "Admin access required"}), 403

        rfpo = RFPO.query.get_or_404(rfpo_id)
        snapshot_path = _generate_and_save_pdf_snapshot(rfpo)
        if snapshot_path:
            rfpo.pdf_snapshot_path = snapshot_path
            db.session.commit()
            return jsonify({"success": True, "message": "PDF snapshot regenerated", "path": snapshot_path})
        return jsonify({"success": False, "message": "Failed to generate PDF snapshot"}), 500
    except Exception as e:
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
                    rfpo.rfpo_id, f"Reassigned: {action.step_name}",
                    rfpo_db_id=rfpo.id,
                    context={'rfpo_id': rfpo.id, 'project_id': rfpo.project_id, 'consortium_id': rfpo.consortium_id, 'team_id': rfpo.team_id},
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

        # Admins (GOD or RFPO_ADMIN) can see all RFPOs
        user_perms = user.get_permissions() or []
        is_admin = "GOD" in user_perms or "RFPO_ADMIN" in user_perms

        if is_admin:
            query = RFPO.query.filter(RFPO.deleted_at.is_(None))
        else:
            accessible_rfpo_ids = set()

            # 1. RFPOs the user created (requestor)
            own_rfpos = RFPO.query.filter(
                RFPO.requestor_id == user.record_id,
                RFPO.deleted_at.is_(None)
            ).with_entities(RFPO.id).all()
            accessible_rfpo_ids.update(r.id for r in own_rfpos)

            # 2. Team access — via UserTeam junction table
            user_teams = user.get_teams()
            team_ids = [team.id for team in user_teams]

            # Also check team-level viewer/admin JSON arrays
            all_teams = Team.query.filter_by(active=True).all()
            for team in all_teams:
                viewers = team.get_rfpo_viewer_users()
                admins = team.get_rfpo_admin_users()
                if user.record_id in viewers or \
                   user.record_id in admins:
                    if team.id not in team_ids:
                        team_ids.append(team.id)

            # 3. Consortium access — viewer/admin JSON arrays
            accessible_consortium_ids = []
            all_consortiums = Consortium.query.filter_by(
                active=True
            ).all()
            for consortium in all_consortiums:
                viewers = consortium.get_rfpo_viewer_users()
                admins = consortium.get_rfpo_admin_users()
                if user.record_id in viewers or \
                   user.record_id in admins:
                    accessible_consortium_ids.append(
                        consortium.consort_id
                    )

            # 4. Project access — viewer JSON arrays
            all_projects = Project.query.filter_by(active=True).all()
            accessible_project_ids = []
            for project in all_projects:
                viewer_users = project.get_rfpo_viewer_users()
                if user.record_id in viewer_users:
                    accessible_project_ids.append(
                        project.project_id
                    )

            # 5. Approver access — assigned in workflow steps
            #    (primary or backup approver)
            approver_step_rfpo_ids = set()
            try:
                steps = RFPOApprovalStep.query.filter(
                    db.or_(
                        RFPOApprovalStep.primary_approver_id
                        == user.record_id,
                        RFPOApprovalStep.backup_approver_id
                        == user.record_id,
                    )
                ).all()
                for step in steps:
                    stage = step.stage
                    if stage and stage.workflow:
                        wf = stage.workflow
                        instances = (
                            RFPOApprovalInstance.query
                            .filter_by(workflow_id=wf.id)
                            .all()
                        )
                        for inst in instances:
                            if inst.rfpo_id:
                                approver_step_rfpo_ids.add(
                                    inst.rfpo_id
                                )
            except Exception:
                pass

            # Also check existing approval actions
            try:
                user_actions = RFPOApprovalAction.query.filter_by(
                    approver_id=user.record_id
                ).all()
                for action in user_actions:
                    if action.instance and action.instance.rfpo_id:
                        approver_step_rfpo_ids.add(
                            action.instance.rfpo_id
                        )
            except Exception:
                pass

            accessible_rfpo_ids.update(approver_step_rfpo_ids)

            # Build query filters
            filters = []
            if team_ids:
                filters.append(RFPO.team_id.in_(team_ids))
            if accessible_consortium_ids:
                filters.append(
                    RFPO.consortium_id.in_(accessible_consortium_ids)
                )
            if accessible_project_ids:
                filters.append(
                    RFPO.project_id.in_(accessible_project_ids)
                )
            if accessible_rfpo_ids:
                filters.append(RFPO.id.in_(accessible_rfpo_ids))

            # Apply filters
            if filters:
                query = RFPO.query.filter(
                    RFPO.deleted_at.is_(None),
                    db.or_(*filters)
                )
            else:
                return jsonify({
                    "success": True, "rfpos": [],
                    "total": 0, "page": page, "pages": 0
                })

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

        # Find max sequence number for this project and date to avoid collisions
        import re as _re
        like_pattern = f"RFPO-{project_ref}-{date_str}-N%"
        existing_rfpos = RFPO.query.filter(
            RFPO.rfpo_id.like(like_pattern)
        ).with_entities(RFPO.rfpo_id).all()
        max_seq = 0
        for (rid,) in existing_rfpos:
            match = _re.search(r'-N(\d+)$', rid)
            if match:
                max_seq = max(max_seq, int(match.group(1)))
        rfpo_id = f"RFPO-{project_ref}-{date_str}-N{max_seq + 1:02d}"

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
            # Check if user has access to this RFPO via requestor, team, project, or approval
            has_access = False

            # Check if user is the requestor (creator) of this RFPO
            if rfpo.requestor_id == user.record_id:
                has_access = True

            # Check team access
            if not has_access:
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

            # Requestor can always edit their own RFPO
            if rfpo.requestor_id == user.record_id:
                has_access = True

            if not has_access:
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

        # Requestor or admin can add line items
        user = request.current_user
        user_perms = user.get_permissions() or []
        is_admin = 'RFPO_ADMIN' in user_perms or 'GOD' in user_perms
        is_requestor = rfpo.requestor_id == user.record_id
        if not is_admin and not is_requestor:
            return jsonify({"success": False, "message": "Access denied"}), 403

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

        # Requestor or admin can delete line items
        user = request.current_user
        user_perms = user.get_permissions() or []
        is_admin = 'RFPO_ADMIN' in user_perms or 'GOD' in user_perms
        is_requestor = rfpo.requestor_id == user.record_id
        if not is_admin and not is_requestor:
            return jsonify({"success": False, "message": "Access denied"}), 403

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

        # Requestor or admin can update line items
        user = request.current_user
        user_perms = user.get_permissions() or []
        is_admin = 'RFPO_ADMIN' in user_perms or 'GOD' in user_perms
        is_requestor = rfpo.requestor_id == user.record_id
        if not is_admin and not is_requestor:
            return jsonify({"success": False, "message": "Access denied"}), 403

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


@app.route("/api/consortiums", methods=["POST"])
@require_auth
def create_consortium():
    """Create a new consortium (admin only)"""
    user = request.current_user
    user_perms = user.get_permissions() or []
    if "RFPO_ADMIN" not in user_perms and "GOD" not in user_perms:
        return jsonify({"success": False, "message": "Admin access required"}), 403

    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        name = (data.get("name") or "").strip()
        abbrev = (data.get("abbrev") or "").strip().upper()

        if not name:
            return jsonify({"success": False, "message": "Consortium name is required"}), 400
        if not abbrev:
            return jsonify({"success": False, "message": "Abbreviation is required"}), 400
        if len(abbrev) > 20:
            return jsonify({"success": False, "message": "Abbreviation must be 20 characters or less"}), 400
        if not re.match(r'^[A-Z0-9\-]+$', abbrev):
            return jsonify({"success": False, "message": "Abbreviation must contain only letters, numbers, and hyphens"}), 400

        # Check uniqueness
        if Consortium.query.filter(db.func.lower(Consortium.name) == name.lower()).first():
            return jsonify({"success": False, "message": "A consortium with this name already exists"}), 400
        if Consortium.query.filter(db.func.lower(Consortium.abbrev) == abbrev.lower()).first():
            return jsonify({"success": False, "message": "This abbreviation is already in use"}), 400

        from api.utils import generate_next_id
        consort_id = generate_next_id(Consortium, "consort_id", "", 8)

        consortium = Consortium(
            consort_id=consort_id,
            name=name,
            abbrev=abbrev,
            active=True,
            created_by=user.email,
        )
        db.session.add(consortium)
        db.session.commit()

        return jsonify({
            "success": True,
            "consortium": {
                "id": consortium.id,
                "consort_id": consortium.consort_id,
                "name": consortium.name,
                "abbrev": consortium.abbrev,
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        return _error_response(e)


@app.route("/api/projects", methods=["POST"])
@require_auth
def create_project():
    """Create a new project (admin only)"""
    user = request.current_user
    user_perms = user.get_permissions() or []
    if "RFPO_ADMIN" not in user_perms and "GOD" not in user_perms:
        return jsonify({"success": False, "message": "Admin access required"}), 403

    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        name = (data.get("name") or "").strip()
        ref = (data.get("ref") or "").strip().upper()
        consortium_id = (data.get("consortium_id") or "").strip()
        description = (data.get("description") or "").strip() or None
        gov_funded = data.get("gov_funded", True)
        uni_project = data.get("uni_project", False)

        if not name:
            return jsonify({"success": False, "message": "Project name is required"}), 400
        if not ref:
            return jsonify({"success": False, "message": "Reference code is required"}), 400
        if len(ref) > 20:
            return jsonify({"success": False, "message": "Reference code must be 20 characters or less"}), 400
        if not re.match(r'^[A-Z0-9\-]+$', ref):
            return jsonify({"success": False, "message": "Reference code must contain only letters, numbers, and hyphens"}), 400
        if not consortium_id:
            return jsonify({"success": False, "message": "Consortium is required"}), 400

        # Verify consortium exists
        consortium = Consortium.query.filter_by(consort_id=consortium_id).first()
        if not consortium:
            return jsonify({"success": False, "message": "Consortium not found"}), 400

        # Check ref uniqueness
        if Project.query.filter(db.func.lower(Project.ref) == ref.lower()).first():
            return jsonify({"success": False, "message": "This reference code is already in use"}), 400

        from api.utils import generate_next_id
        project_id = generate_next_id(Project, "project_id", "", 8)

        project = Project(
            project_id=project_id,
            name=name,
            ref=ref,
            description=description,
            gov_funded=bool(gov_funded),
            uni_project=bool(uni_project),
            active=True,
            created_by=user.email,
        )

        # Support consortium_ids array (multi-consortium) or single consortium_id
        consortium_ids_list = data.get("consortium_ids")
        if consortium_ids_list and isinstance(consortium_ids_list, list):
            # Validate all consortium IDs exist
            for cid in consortium_ids_list:
                if not Consortium.query.filter_by(consort_id=cid).first():
                    return jsonify({"success": False, "message": f"Consortium '{cid}' not found"}), 400
            project.set_consortium_ids(consortium_ids_list)
        else:
            project.set_consortium_ids([consortium_id])
        db.session.add(project)
        db.session.commit()

        return jsonify({
            "success": True,
            "project": {
                "id": project.project_id,
                "ref": project.ref,
                "name": project.name,
                "description": project.description,
                "gov_funded": project.gov_funded,
                "uni_project": project.uni_project,
            }
        }), 201
    except Exception as e:
        db.session.rollback()
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


@app.route("/api/vendors", methods=["POST"])
@require_auth
def create_vendor():
    """Create a new vendor (admin only)"""
    user = request.current_user
    user_perms = user.get_permissions() or []
    if "RFPO_ADMIN" not in user_perms and "GOD" not in user_perms:
        return jsonify({"success": False, "message": "Admin access required"}), 403

    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        company_name = (data.get("company_name") or "").strip()
        if not company_name:
            return jsonify({"success": False, "message": "Company name is required"}), 400

        from api.utils import generate_next_id
        vendor_id = generate_next_id(Vendor, "vendor_id", "", 8)

        vendor = Vendor(
            vendor_id=vendor_id,
            company_name=company_name,
            contact_name=(data.get("contact_name") or "").strip() or None,
            contact_tel=(data.get("contact_tel") or "").strip() or None,
            contact_city=(data.get("contact_city") or "").strip() or None,
            contact_state=(data.get("contact_state") or "").strip() or None,
            status="live",
            active=True,
            created_by=user.email,
        )
        db.session.add(vendor)
        db.session.commit()

        return jsonify({
            "success": True,
            "vendor": {
                "id": vendor.id,
                "vendor_id": vendor.vendor_id,
                "company_name": vendor.company_name,
                "contact_name": vendor.contact_name,
                "contact_tel": vendor.contact_tel,
                "active": vendor.active,
            }
        }), 201
    except Exception as e:
        db.session.rollback()
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

        rfpo_dir = os.path.join("uploads", "rfpos", rfpo.rfpo_id, "documents")
        os.makedirs(rfpo_dir, exist_ok=True)

        file_path = os.path.join(rfpo_dir, stored_filename)
        file.save(file_path)

        user = request.current_user
        user_name = user.get_display_name() if hasattr(user, "get_display_name") else str(user)

        # Upload to DOCUPLOAD (Azure Blob Storage)
        cloud_result = None
        try:
            from docupload_client import upload_to_docupload, is_configured
            if is_configured():
                with open(file_path, "rb") as f:
                    file_bytes = f.read()
                doc_type_folder = (document_type or "general").lower().replace(" ", "-")
                cloud_result = upload_to_docupload(
                    files={doc_type_folder: (original_filename, file_bytes, mime_type or "application/octet-stream")},
                    folder_path=f"rfpo/{rfpo.rfpo_id}/{doc_type_folder}",
                    form_id="rfpo-documents",
                    submitted_by=user_name,
                    tags={"rfpo-number": rfpo.rfpo_id, "document-type": doc_type_folder, "source": "rfpo-api"},
                )
        except Exception as cloud_err:
            logger.warning("DOCUPLOAD cloud upload failed (file saved locally): %s", cloud_err)

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

        response_data = {
            "success": True,
            "message": f'File "{original_filename}" uploaded successfully',
            "file": uploaded_file.to_dict(),
        }
        if cloud_result and cloud_result.get("success"):
            response_data["cloud_upload"] = {
                "success": True,
                "folder_path": cloud_result.get("folder_path"),
                "uploaded_files": cloud_result.get("uploaded_files", []),
                "scan_status": cloud_result.get("scan_status"),
            }

        return jsonify(response_data)

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


# ─── Notification Endpoints ──────────────────────────────────────────────

def _create_notification(user_id, notif_type, title, message, link=None, entity_type=None, entity_id=None):
    """Helper: create and persist a Notification row."""
    notif = Notification(
        user_id=user_id,
        type=notif_type,
        title=title,
        message=message,
        link=link,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.session.add(notif)
    return notif


@app.route("/api/notifications", methods=["GET"])
@require_auth
def get_notifications():
    """List current user's notifications (newest first, unread first)."""
    try:
        user = request.current_user
        page = request.args.get("page", 1, type=int)
        per_page = min(request.args.get("per_page", 20, type=int), 100)
        unread_only = request.args.get("unread_only", "").lower() == "true"

        query = Notification.query.filter_by(user_id=user.id)
        if unread_only:
            query = query.filter_by(is_read=False)
        query = query.order_by(Notification.is_read.asc(), Notification.created_at.desc())

        paginated = query.paginate(page=page, per_page=per_page, error_out=False)

        return jsonify({
            "success": True,
            "notifications": [n.to_dict() for n in paginated.items],
            "total": paginated.total,
            "page": paginated.page,
            "pages": paginated.pages,
            "unread_count": Notification.query.filter_by(user_id=user.id, is_read=False).count(),
        })
    except Exception as e:
        return _error_response(e)


@app.route("/api/notifications/unread-count", methods=["GET"])
@require_auth
def get_unread_notification_count():
    """Return unread notification count for the badge."""
    try:
        count = Notification.query.filter_by(user_id=request.current_user.id, is_read=False).count()
        return jsonify({"success": True, "unread_count": count})
    except Exception as e:
        return _error_response(e)


@app.route("/api/notifications/<int:notif_id>/read", methods=["PUT"])
@require_auth
def mark_notification_read(notif_id):
    """Mark a single notification as read."""
    try:
        notif = Notification.query.filter_by(id=notif_id, user_id=request.current_user.id).first()
        if not notif:
            return jsonify({"success": False, "message": "Notification not found"}), 404
        notif.mark_read()
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return _error_response(e)


@app.route("/api/notifications/mark-all-read", methods=["POST"])
@require_auth
def mark_all_notifications_read():
    """Mark all of the current user's notifications as read."""
    try:
        Notification.query.filter_by(
            user_id=request.current_user.id, is_read=False
        ).update({"is_read": True, "read_at": datetime.utcnow()})
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return _error_response(e)


# ─── Audit Trail Endpoint ────────────────────────────────────────────────

@app.route("/api/rfpos/<int:rfpo_id>/audit-trail", methods=["GET"])
@require_auth
def get_rfpo_audit_trail(rfpo_id):
    """Return the AuditLog entries for a given RFPO (newest first)."""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)
        logs = (
            AuditLog.query
            .filter_by(entity_type="rfpo", entity_id=str(rfpo.id))
            .order_by(AuditLog.created_at.desc())
            .all()
        )
        # Also include approval-related audit logs
        approval_logs = (
            AuditLog.query
            .filter_by(entity_type="rfpo_approval", entity_id=str(rfpo.id))
            .order_by(AuditLog.created_at.desc())
            .all()
        )
        all_logs = sorted(logs + approval_logs, key=lambda l: l.created_at, reverse=True)
        return jsonify({
            "success": True,
            "audit_trail": [l.to_dict() for l in all_logs],
        })
    except Exception as e:
        return _error_response(e)


# ─── CSV Export Endpoint ─────────────────────────────────────────────────

@app.route("/api/rfpos/export", methods=["GET"])
@require_auth
def export_rfpos_csv():
    """Export the user's visible RFPOs as a CSV file."""
    import csv
    import io

    try:
        user = request.current_user
        user_perms = user.get_permissions() or []
        is_admin = "RFPO_ADMIN" in user_perms or "GOD" in user_perms

        if is_admin:
            rfpos = RFPO.query.filter(RFPO.deleted_at.is_(None)).order_by(RFPO.created_at.desc()).all()
        else:
            accessible_team_ids = [ut.team_id for ut in UserTeam.query.filter_by(user_id=user.id).all()]
            rfpos = RFPO.query.filter(
                RFPO.deleted_at.is_(None),
                RFPO.team_id.in_(accessible_team_ids)
            ).order_by(RFPO.created_at.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "RFPO ID", "Title", "Status", "Vendor", "Team",
            "Subtotal", "Cost Share", "Total Amount",
            "Created By", "Created At", "Due Date",
        ])

        for r in rfpos:
            writer.writerow([
                r.rfpo_id or "",
                r.title or "",
                r.status or "",
                r.vendor_name or "",
                r.team_name or "",
                f"{float(r.subtotal or 0):.2f}",
                f"{float(r.cost_share_amount or 0):.2f}",
                f"{float(r.total_amount or 0):.2f}",
                r.created_by or "",
                r.created_at.strftime("%Y-%m-%d") if r.created_at else "",
                r.delivery_date.strftime("%Y-%m-%d") if r.delivery_date else "",
            ])

        from flask import Response
        resp = Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=rfpos_export.csv"},
        )
        return resp
    except Exception as e:
        return _error_response(e)


# ─── Cost Analytics Endpoint ─────────────────────────────────────────────

@app.route("/api/rfpos/analytics", methods=["GET"])
@require_auth
def get_rfpo_analytics():
    """Return cost analytics: totals by status, team, and monthly trend."""
    try:
        user = request.current_user
        user_perms = user.get_permissions() or []
        is_admin = "RFPO_ADMIN" in user_perms or "GOD" in user_perms

        if is_admin:
            rfpos = RFPO.query.filter(RFPO.deleted_at.is_(None)).all()
        else:
            accessible_team_ids = [ut.team_id for ut in UserTeam.query.filter_by(user_id=user.id).all()]
            rfpos = RFPO.query.filter(
                RFPO.deleted_at.is_(None),
                RFPO.team_id.in_(accessible_team_ids)
            ).all()

        total_spend = sum(float(r.total_amount or 0) for r in rfpos)
        avg_amount = total_spend / len(rfpos) if rfpos else 0.0

        # By status
        by_status = {}
        for r in rfpos:
            s = r.status or "Unknown"
            if s not in by_status:
                by_status[s] = {"count": 0, "total": 0.0}
            by_status[s]["count"] += 1
            by_status[s]["total"] += float(r.total_amount or 0)

        # By team
        by_team = {}
        for r in rfpos:
            t = r.team_name or "Unassigned"
            if t not in by_team:
                by_team[t] = {"count": 0, "total": 0.0}
            by_team[t]["count"] += 1
            by_team[t]["total"] += float(r.total_amount or 0)

        # Monthly trend (last 12 months)
        from collections import OrderedDict
        monthly = OrderedDict()
        for r in rfpos:
            if r.created_at:
                key = r.created_at.strftime("%Y-%m")
                if key not in monthly:
                    monthly[key] = {"count": 0, "total": 0.0}
                monthly[key]["count"] += 1
                monthly[key]["total"] += float(r.total_amount or 0)

        return jsonify({
            "success": True,
            "analytics": {
                "total_rfpos": len(rfpos),
                "total_spend": round(total_spend, 2),
                "average_amount": round(avg_amount, 2),
                "by_status": by_status,
                "by_team": by_team,
                "monthly_trend": monthly,
            },
        })
    except Exception as e:
        return _error_response(e)


if __name__ == "__main__":
    app.logger.info("Starting Simple RFPO API")
    app.logger.info(f"Database: {app.config['SQLALCHEMY_DATABASE_URI']}")

    with app.app_context():
        app.logger.info(f"Users in database: {User.query.count()}")

    app.run(debug=False, host="0.0.0.0", port=5002)
