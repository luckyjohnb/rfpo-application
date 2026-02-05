#!/usr/bin/env python3
"""
Custom RFPO Admin Panel - NO Flask-Admin Dependencies
Built from scratch to avoid WTForms compatibility issues.
"""

import io
import json
import mimetypes
import os
import re
import secrets
import uuid
from datetime import datetime

from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from sqlalchemy import desc
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

# Import error handling
from error_handlers import register_error_handlers
from logging_config import setup_logging

# Import your models
from models import (
    RFPO,
    Consortium,
    List,
    PDFPositioning,
    Project,
    RFPOApprovalAction,
    RFPOApprovalInstance,
    RFPOApprovalStage,
    RFPOApprovalStep,
    RFPOApprovalWorkflow,
    RFPOLineItem,
    Team,
    UploadedFile,
    User,
    UserTeam,
    Vendor,
    VendorSite,
    db,
)

# Optional heavy deps used for import/export
try:
    import pandas as pd
except Exception:  # pragma: no cover - optional in runtime
    pd = None
from pdf_generator import RFPOPDFGenerator


def _parse_budget_amount(value):
    """Parse a numeric amount from various bracket value formats.

    Supports plain numbers like '5000' and textual ranges like 'Under $1,000' or '$1,000 - $5,000'.
    Returns a float amount; returns 0.0 if nothing can be parsed.
    """
    if value is None:
        return 0.0
    try:
        # Already numeric-like
        return float(value)
    except Exception:
        s = str(value)
        nums = re.findall(r"[\d,]+(?:\.\d+)?", s)
        if nums:
            try:
                # Use the maximum number found in the string as the bracket ceiling
                return max(float(n.replace(",", "")) for n in nums)
            except Exception:
                return 0.0
        return 0.0


def sync_all_users_approver_status(updated_by=None):
    """Sync approver status for all users - useful after workflow changes"""
    try:
        users = User.query.all()
        updated_count = 0

        for user in users:
            if user.update_approver_status(updated_by=updated_by):
                updated_count += 1

        db.session.commit()
        return updated_count
    except Exception as e:
        db.session.rollback()
        print(f"Error syncing approver status: {e}")
        return 0


def sync_user_approver_status_for_workflow(workflow_id, updated_by=None):
    """Sync approver status for users affected by a specific workflow"""
    try:
        # Get all users who are approvers in this workflow
        affected_user_ids = set()

        workflow = RFPOApprovalWorkflow.query.get(workflow_id)
        if not workflow:
            return 0

        for stage in workflow.stages:
            for step in stage.steps:
                if step.primary_approver_id:
                    affected_user_ids.add(step.primary_approver_id)
                if step.backup_approver_id:
                    affected_user_ids.add(step.backup_approver_id)

        updated_count = 0
        for user_record_id in affected_user_ids:
            user = User.query.filter_by(record_id=user_record_id).first()
            if user and user.update_approver_status(updated_by=updated_by):
                updated_count += 1

        db.session.commit()
        return updated_count
    except Exception as e:
        db.session.rollback()
        print(f"Error syncing approver status for workflow {workflow_id}: {e}")
        return 0


def get_user_mindmap_data(user):
    """Get comprehensive permissions mindmap data for a user"""
    try:
        # System permissions
        system_permissions = user.get_permissions() or []

        # Team associations (both direct membership and viewer/admin access)
        team_data = []
        accessible_consortium_ids = set()

        # 1. Direct team memberships (UserTeam table)
        direct_teams = user.get_teams()
        team_ids_found = set()

        for team in direct_teams:
            team_info = {
                "id": team.id,
                "record_id": team.record_id,
                "name": team.name,
                "abbrev": team.abbrev,
                "consortium_id": team.consortium_consort_id,
                "consortium_name": None,
                "rfpo_count": RFPO.query.filter_by(team_id=team.id).count(),
                "access_type": "member",
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
            team_ids_found.add(team.id)

        # 2. Teams where user is viewer/admin (JSON fields)
        all_teams = Team.query.all()
        for team in all_teams:
            if team.id in team_ids_found:
                continue  # Already added above

            viewer_users = team.get_rfpo_viewer_users()
            admin_users = team.get_rfpo_admin_users()

            access_type = None
            if user.record_id in admin_users:
                access_type = "admin"
            elif user.record_id in viewer_users:
                access_type = "viewer"

            if access_type:
                team_info = {
                    "id": team.id,
                    "record_id": team.record_id,
                    "name": team.name,
                    "abbrev": team.abbrev,
                    "consortium_id": team.consortium_consort_id,
                    "consortium_name": None,
                    "rfpo_count": RFPO.query.filter_by(team_id=team.id).count(),
                    "access_type": access_type,
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
                # Count RFPOs directly associated with this project
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
        team_ids = [team["id"] for team in team_data]
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

        # Approval workflow access
        approval_access = []
        if user.is_rfpo_admin() or user.is_super_admin():
            approval_workflows = RFPOApprovalWorkflow.query.filter_by(
                is_template=True, is_active=True
            ).count()
            approval_access.append(
                {
                    "type": "admin_access",
                    "description": "All approval workflows (Admin access)",
                    "count": approval_workflows,
                }
            )

        # Build mindmap structure
        return {
            "user": {
                "id": user.id,
                "record_id": user.record_id,
                "email": user.email,
                "display_name": user.get_display_name(),
            },
            "system_permissions": {
                "permissions": system_permissions,
                "is_super_admin": user.is_super_admin(),
                "is_rfpo_admin": user.is_rfpo_admin(),
                "is_rfpo_user": user.is_rfpo_user(),
            },
            "associations": {
                "teams": {"count": len(team_data), "list": team_data},
                "consortiums": {
                    "count": len(direct_consortium_access),
                    "list": direct_consortium_access,
                },
                "projects": {"count": len(project_access), "list": project_access},
            },
            "access_summary": {
                "total_rfpos": len(accessible_rfpos),
                "total_consortiums": len(accessible_consortium_ids),
                "total_teams": len(team_data),
                "total_projects": len(project_access),
                "has_admin_access": user.is_rfpo_admin() or user.is_super_admin(),
                "approval_workflows": approval_access,
            },
            "capabilities": {
                "can_access_admin_panel": user.is_rfpo_admin() or user.is_super_admin(),
                "can_create_rfpos": len(team_data) > 0
                or len(project_access) > 0
                or user.is_rfpo_admin()
                or user.is_super_admin(),
                "can_approve_rfpos": user.is_rfpo_admin() or user.is_super_admin(),
                "can_manage_users": user.is_rfpo_admin() or user.is_super_admin(),
                "can_manage_workflows": user.is_rfpo_admin() or user.is_super_admin(),
            },
        }

    except Exception as e:
        print(f"Error in get_user_mindmap_data: {e}")
        import traceback

        traceback.print_exc()
        return None


class APIHelper:
    """
    Safe API helper with fallback to direct database access
    This allows gradual migration from direct DB to API calls
    """

    def __init__(self, api_base_url="http://localhost:5002/api"):
        self.api_base_url = api_base_url
        self.session = None  # Will store admin session/token

    def make_api_call(self, endpoint, method="GET", data=None, fallback_func=None):
        """
        Make API call with fallback to direct database function
        If API fails, use the fallback function (original DB code)
        """
        try:
            import requests

            url = f"{self.api_base_url}{endpoint}"

            headers = {"Content-Type": "application/json"}
            if self.session and self.session.get("token"):
                headers["Authorization"] = f"Bearer {self.session['token']}"

            if method == "GET":
                response = requests.get(url, headers=headers, timeout=5)
            elif method == "POST":
                response = requests.post(url, json=data, headers=headers, timeout=5)
            elif method == "PUT":
                response = requests.put(url, json=data, headers=headers, timeout=5)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, timeout=5)

            if response.status_code == 200:
                return response.json()
            else:
                print(f"API call failed: {response.status_code}")
                if fallback_func:
                    print("Using database fallback...")
                    return fallback_func()

        except Exception as e:
            print(f"API call exception: {e}")
            if fallback_func:
                print("Using database fallback...")
                return fallback_func()

        return None

    def authenticate_admin(self, email, password):
        """Authenticate admin and store session"""
        try:
            import requests

            response = requests.post(
                f"{self.api_base_url}/auth/login",
                json={"username": email, "password": password},
                timeout=5,
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    self.session = {"token": data["token"], "user": data["user"]}
                    return True
        except Exception as e:
            print(f"API authentication failed: {e}")

        return False


def create_app():
    """Create Flask application with custom admin panel"""
    app = Flask(__name__)

    # Configuration
    app.config["SECRET_KEY"] = os.environ.get(
        "ADMIN_SECRET_KEY", "rfpo-admin-secret-key-change-in-production"
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        f'sqlite:///{os.path.join(os.getcwd(), "instance", "rfpo_admin.db")}',
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialize extensions
    db.init_app(app)

    # Setup logging
    logger = setup_logging("admin", log_to_file=True)
    app.logger = logger

    # Register error handlers
    register_error_handlers(app, "admin")

    # Initialize API Helper (for gradual migration to API)
    api_helper = APIHelper("http://rfpo-api:5002/api")  # Use container name for Docker
    app.api_helper = api_helper

    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "login"

    # Expose build/version info to all admin templates
    @app.context_processor
    def inject_build_info():
        build_sha = os.environ.get("APP_BUILD_SHA", "")
        short_sha = build_sha[:7] if build_sha else ""
        # Determine email sender info (ACS vs SMTP) for display
        acs_conn = os.environ.get("ACS_CONNECTION_STRING", "").strip()
        acs_sender = os.environ.get("ACS_SENDER_EMAIL", "").strip()

        smtp_username = (
            os.environ.get("MAIL_USERNAME")
            or os.environ.get("SMTP_USERNAME")
            or os.environ.get("GMAIL_USER")
            or ""
        ).strip()
        smtp_default_sender = (
            os.environ.get("MAIL_DEFAULT_SENDER")
            or os.environ.get("SMTP_DEFAULT_SENDER")
            or ""
        ).strip()

        if acs_conn and acs_sender:
            sender_mode = "ACS"
            sender_label = f"ACS: {acs_sender}"
        elif smtp_default_sender or smtp_username:
            sender_mode = "SMTP"
            sender_email = smtp_default_sender or smtp_username
            sender_label = f"SMTP: {sender_email}"
        else:
            sender_mode = "Email: disabled"
            sender_label = "Email: disabled"
        return {
            "APP_BUILD_SHA": build_sha,
            "APP_BUILD_SHA_SHORT": short_sha,
            "ADMIN_EMAIL_SENDER_MODE": sender_mode,
            "ADMIN_EMAIL_SENDER_LABEL": sender_label,
        }

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

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

    # Helper functions
    def format_json_field(value):
        """Format JSON field for display"""
        if not value:
            return "None"
        try:
            if isinstance(value, str):
                data = json.loads(value)
            else:
                data = value
            return ", ".join(data) if isinstance(data, list) else str(data)
        except Exception:
            return str(value)

    def parse_comma_list(value):
        """Parse comma-separated string to list"""
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]

    def generate_next_id(model_class, id_field, prefix="", length=8):
        """Generate next auto-incremented ID for external ID fields"""
        try:
            # Get the highest existing ID and increment
            max_record = (
                db.session.query(model_class)
                .order_by(getattr(model_class, id_field).desc())
                .first()
            )
            if max_record:
                current_id = getattr(max_record, id_field)
                try:
                    # Extract numeric part and increment
                    current_num = int(current_id.replace(prefix, "").lstrip("0") or "0")
                    next_num = current_num + 1
                except (ValueError, AttributeError):
                    # If parsing fails, use count + 1
                    next_num = db.session.query(model_class).count() + 1
            else:
                next_num = 1

            # Keep trying until we find a unique ID
            for attempt in range(100):  # Prevent infinite loop
                candidate_id = (
                    f"{prefix}{(next_num + attempt):0{length}d}"
                    if prefix
                    else f"{(next_num + attempt):0{length}d}"
                )
                existing = (
                    db.session.query(model_class)
                    .filter(getattr(model_class, id_field) == candidate_id)
                    .first()
                )
                if not existing:
                    return candidate_id

            # Final fallback to timestamp
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            return f"{prefix}{timestamp}" if prefix else timestamp

        except Exception:
            # Fallback to timestamp-based ID
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            return f"{prefix}{timestamp}" if prefix else timestamp

    def handle_file_upload(file, upload_folder):
        """Handle file upload and return filename"""
        if file and file.filename and file.filename != "":
            try:
                # Secure the filename
                filename = secure_filename(file.filename)

                # Add timestamp to avoid conflicts
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_")
                filename = f"{timestamp}{filename}"

                # Ensure upload folder exists
                os.makedirs(upload_folder, exist_ok=True)

                # Save file
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)

                return filename
            except Exception as e:
                print(f"File upload error: {e}")
                return None
        return None

    def _process_vendor_site_id(vendor_site_id_str):
        # Process vendor_site_id which could be a regular ID
        # or special 'vendor_X' format
        if not vendor_site_id_str:
            return None

        # If it's the special vendor primary contact format (vendor_123),
        # store None since the vendor's primary contact info
        # is already in the vendor record
        if vendor_site_id_str.startswith("vendor_"):
            return None

        # Otherwise, convert to integer for regular vendor site IDs
        try:
            return int(vendor_site_id_str)
        except (ValueError, TypeError):
            return None

    def get_applicable_workflows(rfpo):
        """Get ALL applicable approval workflows for an RFPO in sequential order: Project -> Team -> Consortium"""
        applicable_workflows = []

        # 1. Check for project-specific workflow (Phase 1)
        if rfpo.project_id:
            project_workflow = RFPOApprovalWorkflow.query.filter_by(
                project_id=rfpo.project_id,
                workflow_type="project",
                is_template=True,
                is_active=True,
            ).first()
            if project_workflow:
                applicable_workflows.append(("project", project_workflow, 1))

        # 2. Check for team-specific workflow (Phase 2)
        if rfpo.team_id:
            team_workflow = RFPOApprovalWorkflow.query.filter_by(
                team_id=rfpo.team_id,
                workflow_type="team",
                is_template=True,
                is_active=True,
            ).first()
            if team_workflow:
                phase = len(applicable_workflows) + 1
                applicable_workflows.append(("team", team_workflow, phase))

        # 3. Check for consortium workflow (Phase 3)
        if rfpo.consortium_id:
            consortium_workflow = RFPOApprovalWorkflow.query.filter_by(
                consortium_id=rfpo.consortium_id,
                workflow_type="consortium",
                is_template=True,
                is_active=True,
            ).first()
            if consortium_workflow:
                phase = len(applicable_workflows) + 1
                applicable_workflows.append(("consortium", consortium_workflow, phase))

        return applicable_workflows

    def get_applicable_workflow(rfpo):
        """Get the first applicable workflow (for backward compatibility)"""
        workflows = get_applicable_workflows(rfpo)
        return workflows[0][1] if workflows else None

    def determine_rfpo_stage(rfpo, workflow):
        """Determine which approval stage an RFPO falls into based on its total amount"""
        if not rfpo.total_amount or not workflow:
            return None

        # Get all stages for this workflow, sorted by budget bracket amount
        stages = sorted(workflow.stages, key=lambda s: float(s.budget_bracket_amount))

        # Find the appropriate stage based on RFPO total amount
        for stage in stages:
            if float(rfpo.total_amount) <= float(stage.budget_bracket_amount):
                return stage

        # If RFPO amount exceeds all brackets, use the highest bracket stage
        return stages[-1] if stages else None

    def validate_rfpo_for_approval(rfpo):
        """Validate an RFPO against all applicable sequential workflow phases"""
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "workflow_phases": [],  # Sequential phases: Project -> Team -> Consortium
            "basic_validation": {},
            "total_phases": 0,
        }

        try:
            # Basic RFPO validation first
            basic_issues = []
            if not rfpo.title or not rfpo.title.strip():
                basic_issues.append("RFPO title is required")
                validation_result["is_valid"] = False

            if not rfpo.vendor_id:
                basic_issues.append("No vendor selected")

            if not rfpo.line_items or len(rfpo.line_items) == 0:
                basic_issues.append("RFPO must have at least one line item")
                validation_result["is_valid"] = False

            if not rfpo.total_amount or float(rfpo.total_amount) <= 0:
                basic_issues.append("RFPO total amount must be greater than zero")
                validation_result["is_valid"] = False

            validation_result["basic_validation"] = {
                "issues": basic_issues,
                "rfpo_amount": float(rfpo.total_amount or 0),
                "line_items_count": len(rfpo.line_items) if rfpo.line_items else 0,
                "files_count": len(rfpo.files) if rfpo.files else 0,
            }

            # Get all applicable workflows in sequential order
            applicable_workflows = get_applicable_workflows(rfpo)
            validation_result["total_phases"] = len(applicable_workflows)

            if not applicable_workflows:
                validation_result["is_valid"] = False
                validation_result["errors"].append(
                    "No active approval workflows found for this RFPO"
                )

                # Still show what workflows would be checked
                workflow_types_to_check = [
                    ("project", rfpo.project_id, "Project-specific"),
                    ("team", rfpo.team_id, "Team-specific"),
                    ("consortium", rfpo.consortium_id, "Consortium-wide"),
                ]

                for workflow_type, entity_id, display_name in workflow_types_to_check:
                    workflow_phase = {
                        "workflow_type": workflow_type,
                        "display_name": display_name,
                        "entity_id": str(entity_id) if entity_id else None,
                        "has_workflow": False,
                        "phase_number": 0,
                        "is_required": entity_id is not None,
                    }
                    validation_result["workflow_phases"].append(workflow_phase)
            else:
                # Process each applicable workflow phase
                for workflow_type, workflow, phase_number in applicable_workflows:
                    display_name = (
                        f"Phase {phase_number}: {workflow_type.title()}-specific"
                    )

                    # Determine stage for this workflow
                    stage = determine_rfpo_stage(rfpo, workflow)
                    stage_info = None

                    if stage:
                        # Validate documents for this stage
                        document_validation = validate_stage_documents(rfpo, stage)

                        # Get approval steps
                        approval_steps = []
                        for step in stage.steps:
                            primary_approver = User.query.filter_by(
                                record_id=step.primary_approver_id, active=True
                            ).first()
                            backup_approver = (
                                User.query.filter_by(
                                    record_id=step.backup_approver_id, active=True
                                ).first()
                                if step.backup_approver_id
                                else None
                            )

                            step_info = {
                                "step_id": step.step_id,
                                "step_name": step.step_name,
                                "step_order": step.step_order,
                                "approval_type": step.approval_type_name,
                                "primary_approver": (
                                    primary_approver.get_display_name()
                                    if primary_approver
                                    else "Unknown User"
                                ),
                                "backup_approver": (
                                    backup_approver.get_display_name()
                                    if backup_approver
                                    else None
                                ),
                                "is_required": step.is_required,
                                "description": step.description,
                                "approver_valid": primary_approver is not None,
                            }
                            approval_steps.append(step_info)

                            # Check for missing approvers
                            if not primary_approver:
                                validation_result["errors"].append(
                                    f"Phase {phase_number} - Primary approver not found for step: {step.step_name}"
                                )
                                validation_result["is_valid"] = False

                        stage_info = {
                            "stage_id": stage.stage_id,
                            "stage_name": stage.stage_name,
                            "stage_order": stage.stage_order,
                            "budget_bracket_amount": float(stage.budget_bracket_amount),
                            "rfpo_amount": float(rfpo.total_amount or 0),
                            "description": stage.description,
                            "document_validation": document_validation,
                            "approval_steps": approval_steps,
                        }

                        # Add summary warnings for document issues
                        if document_validation["missing_documents"]:
                            # Missing required documents should be an error, not a warning
                            missing_count = len(
                                document_validation["missing_documents"]
                            )
                            msg = (
                                f"{workflow_type.title()}: Missing {missing_count} "
                                "required documents"
                            )
                            validation_result["errors"].append(msg)
                            validation_result["is_valid"] = False

                    # Create workflow phase info
                    workflow_phase = {
                        "workflow_type": workflow_type,
                        "display_name": display_name,
                        "entity_id": workflow.get_entity_identifier(),
                        "has_workflow": True,
                        "phase_number": phase_number,
                        "workflow_id": workflow.workflow_id,
                        "name": workflow.name,
                        "version": workflow.version,
                        "entity_name": workflow.get_entity_name(),
                        "stage_info": stage_info,
                        "is_required": True,
                    }

                    validation_result["workflow_phases"].append(workflow_phase)

                # Also add any missing workflow types for completeness
                all_workflow_types = ["project", "team", "consortium"]
                existing_types = [wf[0] for wf in applicable_workflows]

                for workflow_type in all_workflow_types:
                    if workflow_type not in existing_types:
                        entity_id = None
                        if workflow_type == "project":
                            entity_id = rfpo.project_id
                        elif workflow_type == "team":
                            entity_id = rfpo.team_id
                        elif workflow_type == "consortium":
                            entity_id = rfpo.consortium_id

                        if (
                            entity_id
                        ):  # Only show if RFPO is associated with this entity
                            workflow_phase = {
                                "workflow_type": workflow_type,
                                "display_name": f"{workflow_type.title()}-specific",
                                "entity_id": str(entity_id),
                                "has_workflow": False,
                                "phase_number": 0,
                                "is_required": True,
                            }
                            validation_result["workflow_phases"].append(workflow_phase)

        except Exception as e:
            validation_result["is_valid"] = False
            validation_result["errors"].append(f"Validation error: {str(e)}")

        return validation_result

    def validate_stage_documents(rfpo, stage):
        """Validate documents for a specific stage"""
        required_doc_type_keys = stage.get_required_document_types()
        # Note: names can be derived from types if needed in the future

        document_validation = {
            "required_documents": [],
            "uploaded_documents": [],
            "missing_documents": [],
            "document_status": [],
        }

        if not required_doc_type_keys:
            return document_validation

        # Get uploaded document types for this RFPO (both keys and values)
        uploaded_doc_types = [f.document_type for f in rfpo.files if f.document_type]

        # Create mapping of doc_type keys to values for comparison
        doc_type_mapping = {}
        for key in required_doc_type_keys:
            doc_item = List.query.filter_by(
                type="doc_types", key=key, active=True
            ).first()
            if doc_item and doc_item.value.strip():
                doc_type_mapping[key] = doc_item.value

        # Check each required document
        for key in required_doc_type_keys:
            doc_name = doc_type_mapping.get(key, key)

            # Check if document is uploaded (compare both key and value)
            is_uploaded = key in uploaded_doc_types or doc_name in uploaded_doc_types

            document_status = {
                "key": key,
                "name": doc_name,
                "is_uploaded": is_uploaded,
                "is_required": True,
            }

            document_validation["document_status"].append(document_status)
            document_validation["required_documents"].append(doc_name)

            if not is_uploaded:
                document_validation["missing_documents"].append(doc_name)

        # Add uploaded documents info
        document_validation["uploaded_documents"] = [
            {"type": f.document_type, "filename": f.original_filename}
            for f in rfpo.files
            if f.document_type
        ]

        return document_validation

    # Authentication routes
    # Health check endpoint for Docker
    @app.route("/health", methods=["GET"])
    def health_check():
        """Health check endpoint"""
        return jsonify(
            {
                "status": "healthy",
                "service": "RFPO Admin Panel",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0",
            }
        )

    # Simple email test form (admin-only)
    @app.route("/tools/email-test", methods=["GET", "POST"])
    @login_required
    def email_test_tool():
        from email_service import email_service

        if request.method == "POST":
            to_email = request.form.get("to_email")
            subject = request.form.get("subject") or "Test Email from RFPO"
            message = request.form.get("message") or (
                "This is a test email from RFPO Admin."
            )

            ok = email_service.send_email(
                to_emails=[to_email], subject=subject, body_text=message
            )
            diag = (
                email_service.get_last_send_result()
                if hasattr(email_service, "get_last_send_result")
                else {}
            )
            if ok:
                prov = diag.get("provider") or "unknown"
                sndr = diag.get("sender") or "(no sender)"
                status = diag.get("status") or "unknown"
                msg_id = diag.get("message_id") or "(n/a)"
                flash(
                    f"✅ Test email sent via {prov} from {sndr}. Status: {status}. Message ID: {msg_id}",
                    "success",
                )
            else:
                err = diag.get("error") or "unknown error"
                prov = diag.get("provider") or "unknown"
                flash(f"❌ Failed to send test email via {prov}: {err}", "error")
            return redirect(url_for("email_test_tool"))

        return render_template("admin/tools/email_test.html")

    # Test route for API integration (safe - doesn't break anything)
    @app.route("/api-test")
    @login_required
    def api_test():
        """Test API integration without breaking existing functionality"""

        # Test 1: Direct database count (current way)
        db_user_count = User.query.count()

        # Test 2: API health check
        api_status = "unknown"
        try:
            import requests

            response = requests.get("http://rfpo-api:5002/api/health", timeout=3)
            if response.status_code == 200:
                api_status = "connected"
            else:
                api_status = f"error_{response.status_code}"
        except Exception as e:
            api_status = f"failed_{str(e)[:50]}"

        # Test 3: Try to authenticate with API (if current user has email)
        api_auth_status = "not_tested"
        if current_user and hasattr(current_user, "email"):
            try:
                _ = app.api_helper.authenticate_admin(current_user.email, "test")
                api_auth_status = "tested_but_no_password"
            except Exception as e:
                api_auth_status = f"auth_error_{str(e)[:30]}"

        return jsonify(
            {
                "database_users": db_user_count,
                "api_status": api_status,
                "api_auth_status": api_auth_status,
                "current_user_email": current_user.email if current_user else None,
                "message": "API integration test - existing functionality unchanged",
            }
        )

    # Note: Removed temporary /version diagnostics route after verification

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email")
            password = request.form.get("password")

            user = User.query.filter_by(email=email, active=True).first()

            if user and check_password_hash(user.password_hash, password):
                if user.is_super_admin() or user.is_rfpo_admin():
                    login_user(user)
                    flash(f"Welcome {user.get_display_name()}! 🎉", "success")
                    return redirect(url_for("dashboard"))
                else:
                    flash("❌ You do not have admin privileges.", "error")
            else:
                flash("❌ Invalid email or password.", "error")

        return render_template("admin/login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("👋 You have been logged out.", "info")
        return redirect(url_for("login"))

    @app.route("/")
    @login_required
    def dashboard():
        """Main dashboard"""
        stats = {
            "consortiums": Consortium.query.filter_by(active=True).count(),
            "teams": Team.query.filter_by(active=True).count(),
            "rfpos": RFPO.query.count(),
            "users": User.query.filter_by(active=True).count(),
            "vendors": Vendor.query.filter_by(active=True).count(),
            "projects": Project.query.filter_by(active=True).count(),
            "uploaded_files": UploadedFile.query.count(),
            "approval_workflows": RFPOApprovalWorkflow.query.filter_by(
                is_template=True, is_active=True
            ).count(),
            "consortium_workflows": RFPOApprovalWorkflow.query.filter_by(
                workflow_type="consortium", is_template=True, is_active=True
            ).count(),
            "team_workflows": RFPOApprovalWorkflow.query.filter_by(
                workflow_type="team", is_template=True, is_active=True
            ).count(),
            "project_workflows": RFPOApprovalWorkflow.query.filter_by(
                workflow_type="project", is_template=True, is_active=True
            ).count(),
            "approval_instances": RFPOApprovalInstance.query.count(),
            "pending_approvals": RFPOApprovalAction.query.filter_by(
                status="pending"
            ).count(),
        }

        recent_rfpos = RFPO.query.order_by(desc(RFPO.created_at)).limit(5).all()
        recent_files = (
            UploadedFile.query.order_by(desc(UploadedFile.uploaded_at)).limit(5).all()
        )

        return render_template(
            "admin/dashboard.html",
            stats=stats,
            recent_rfpos=recent_rfpos,
            recent_files=recent_files,
        )

    # Consortium routes
    @app.route("/consortiums")
    @login_required
    def consortiums():
        """List all consortiums with counts"""
        consortiums = Consortium.query.all()

        # Calculate counts for each consortium
        for consortium in consortiums:
            # Count projects associated with this consortium
            consortium.project_count = Project.query.filter(
                Project.consortium_ids.like(f"%{consortium.consort_id}%"),
                Project.active.is_(True),
            ).count()

            # Count RFPOs through teams associated with this consortium
            consortium.rfpo_count = (
                RFPO.query.join(Team)
                .filter(Team.consortium_consort_id == consortium.consort_id)
                .count()
            )

            # Count viewers and admins
            consortium.viewer_count = len(consortium.get_rfpo_viewer_users())
            consortium.admin_count = len(consortium.get_rfpo_admin_users())

        return render_template(
            "admin/consortiums.html",
            consortiums=consortiums,
            format_json=format_json_field,
        )

    @app.route("/consortium/new", methods=["GET", "POST"])
    @login_required
    def consortium_new():
        """Create new consortium"""
        if request.method == "POST":
            try:
                # Auto-generate consortium ID
                consort_id = generate_next_id(Consortium, "consort_id", "", 8)

                # Handle logo upload
                logo_filename = None
                if "logo_file" in request.files:
                    logo_file = request.files["logo_file"]
                    if logo_file.filename and logo_file.filename != "":
                        logo_filename = handle_file_upload(logo_file, "uploads/logos")
                        if logo_filename:
                            flash(f"📷 Logo uploaded: {logo_filename}", "info")

                # Handle terms PDF upload
                terms_pdf_filename = None
                if "terms_pdf_file" in request.files:
                    terms_pdf_file = request.files["terms_pdf_file"]
                    if terms_pdf_file.filename and terms_pdf_file.filename != "":
                        # Validate it's a PDF file
                        if terms_pdf_file.filename.lower().endswith(".pdf"):
                            terms_pdf_filename = handle_file_upload(
                                terms_pdf_file, "uploads/terms"
                            )
                            if terms_pdf_filename:
                                flash(
                                    f"📄 Terms PDF uploaded: {terms_pdf_filename}",
                                    "info",
                                )
                        else:
                            flash("❌ Terms file must be a PDF", "error")

                # Build invoicing address from structured inputs
                invoicing_parts = []
                if request.form.get("invoicing_street"):
                    invoicing_parts.append(request.form.get("invoicing_street"))

                city_state_zip = []
                if request.form.get("invoicing_city"):
                    city_state_zip.append(request.form.get("invoicing_city"))
                if request.form.get("invoicing_state"):
                    city_state_zip[-1] = (
                        f"{city_state_zip[-1]}, {request.form.get('invoicing_state')}"
                        if city_state_zip
                        else request.form.get("invoicing_state")
                    )
                if request.form.get("invoicing_zip"):
                    city_state_zip[-1] = (
                        f"{city_state_zip[-1]} {request.form.get('invoicing_zip')}"
                        if city_state_zip
                        else request.form.get("invoicing_zip")
                    )

                if city_state_zip:
                    invoicing_parts.extend(city_state_zip)
                if request.form.get("invoicing_country"):
                    invoicing_parts.append(request.form.get("invoicing_country"))

                invoicing_address = "\n".join(invoicing_parts)

                consortium = Consortium(
                    consort_id=consort_id,
                    name=request.form.get("name"),
                    abbrev=request.form.get("abbrev"),
                    logo=logo_filename,
                    terms_pdf=terms_pdf_filename,
                    require_approved_vendors=bool(
                        request.form.get("require_approved_vendors")
                    ),
                    non_government_project_id=request.form.get(
                        "non_government_project_id"
                    )
                    or None,
                    invoicing_address=invoicing_address,
                    doc_fax_name=request.form.get("doc_fax_name"),
                    doc_fax_number=request.form.get("doc_fax_number"),
                    doc_email_name=request.form.get("doc_email_name"),
                    doc_email_address=request.form.get("doc_email_address"),
                    doc_post_name=request.form.get("doc_post_name"),
                    doc_post_address=request.form.get("doc_post_address"),
                    po_email=request.form.get("po_email"),
                    active=bool(request.form.get("active", True)),
                    created_by=current_user.get_display_name(),
                )

                # Handle JSON fields from user selection interface
                viewer_users = parse_comma_list(
                    request.form.get("rfpo_viewer_user_ids")
                )
                admin_users = parse_comma_list(request.form.get("rfpo_admin_user_ids"))

                if viewer_users:
                    consortium.set_rfpo_viewer_users(viewer_users)
                if admin_users:
                    consortium.set_rfpo_admin_users(admin_users)

                db.session.add(consortium)
                db.session.commit()

                flash("✅ Consortium created successfully!", "success")
                return redirect(url_for("consortiums"))

            except Exception as e:
                db.session.rollback()  # Important: rollback the failed transaction
                flash(f"❌ Error creating consortium: {str(e)}", "error")

        # Get non-government projects for dropdown
        non_gov_projects = Project.query.filter_by(gov_funded=False, active=True).all()
        return render_template(
            "admin/consortium_form.html",
            consortium=None,
            action="Create",
            non_gov_projects=non_gov_projects,
        )

    @app.route("/consortium/<int:id>/edit", methods=["GET", "POST"])
    @login_required
    def consortium_edit(id):
        """Edit consortium"""
        consortium = Consortium.query.get_or_404(id)

        if request.method == "POST":
            try:
                # Handle logo upload
                if "logo_file" in request.files:
                    logo_file = request.files["logo_file"]
                    if logo_file.filename:
                        # Delete old logo if exists
                        if consortium.logo:
                            old_logo_path = os.path.join(
                                "uploads/logos", consortium.logo
                            )
                            if os.path.exists(old_logo_path):
                                os.remove(old_logo_path)

                        # Upload new logo
                        consortium.logo = handle_file_upload(logo_file, "uploads/logos")

                # Handle terms PDF upload
                if "terms_pdf_file" in request.files:
                    terms_pdf_file = request.files["terms_pdf_file"]
                    if terms_pdf_file.filename:
                        # Validate it's a PDF file
                        if terms_pdf_file.filename.lower().endswith(".pdf"):
                            # Delete old terms PDF if exists
                            if consortium.terms_pdf:
                                old_terms_path = os.path.join(
                                    "uploads/terms", consortium.terms_pdf
                                )
                                if os.path.exists(old_terms_path):
                                    os.remove(old_terms_path)

                            # Upload new terms PDF
                            consortium.terms_pdf = handle_file_upload(
                                terms_pdf_file, "uploads/terms"
                            )
                            if consortium.terms_pdf:
                                flash(
                                    f"📄 Terms PDF updated: {consortium.terms_pdf}",
                                    "info",
                                )
                        else:
                            flash("❌ Terms file must be a PDF", "error")

                # Build invoicing address from structured inputs
                invoicing_parts = []
                if request.form.get("invoicing_street"):
                    invoicing_parts.append(request.form.get("invoicing_street"))

                city_state_zip = []
                if request.form.get("invoicing_city"):
                    city_state_zip.append(request.form.get("invoicing_city"))
                if request.form.get("invoicing_state"):
                    city_state_zip[-1] = (
                        f"{city_state_zip[-1]}, {request.form.get('invoicing_state')}"
                        if city_state_zip
                        else request.form.get("invoicing_state")
                    )
                if request.form.get("invoicing_zip"):
                    city_state_zip[-1] = (
                        f"{city_state_zip[-1]} {request.form.get('invoicing_zip')}"
                        if city_state_zip
                        else request.form.get("invoicing_zip")
                    )

                if city_state_zip:
                    invoicing_parts.extend(city_state_zip)
                if request.form.get("invoicing_country"):
                    invoicing_parts.append(request.form.get("invoicing_country"))

                consortium.name = request.form.get("name")
                consortium.abbrev = request.form.get("abbrev")
                consortium.require_approved_vendors = bool(
                    request.form.get("require_approved_vendors")
                )
                consortium.non_government_project_id = (
                    request.form.get("non_government_project_id") or None
                )
                consortium.invoicing_address = "\n".join(invoicing_parts)
                consortium.doc_fax_name = request.form.get("doc_fax_name")
                consortium.doc_fax_number = request.form.get("doc_fax_number")
                consortium.doc_email_name = request.form.get("doc_email_name")
                consortium.doc_email_address = request.form.get("doc_email_address")
                consortium.doc_post_name = request.form.get("doc_post_name")
                consortium.doc_post_address = request.form.get("doc_post_address")
                consortium.po_email = request.form.get("po_email")
                consortium.active = bool(request.form.get("active"))
                consortium.updated_by = current_user.get_display_name()

                # Handle JSON fields from user selection interface
                viewer_users = parse_comma_list(
                    request.form.get("rfpo_viewer_user_ids")
                )
                admin_users = parse_comma_list(request.form.get("rfpo_admin_user_ids"))

                consortium.set_rfpo_viewer_users(viewer_users)
                consortium.set_rfpo_admin_users(admin_users)

                db.session.commit()

                flash("✅ Consortium updated successfully!", "success")
                return redirect(url_for("consortiums"))

            except Exception as e:
                db.session.rollback()
                flash(f"❌ Error updating consortium: {str(e)}", "error")

        # Pre-populate JSON fields for editing
        consortium.rfpo_viewer_user_ids_display = ", ".join(
            consortium.get_rfpo_viewer_users()
        )
        consortium.rfpo_admin_user_ids_display = ", ".join(
            consortium.get_rfpo_admin_users()
        )

        # Parse invoicing address for structured inputs
        if consortium.invoicing_address:
            address_lines = consortium.invoicing_address.split("\n")
            consortium.invoicing_street = (
                address_lines[0] if len(address_lines) > 0 else ""
            )
            if len(address_lines) > 1:
                # Parse city, state, zip from second line
                city_state_zip = address_lines[1]
                parts = city_state_zip.split(",")
                consortium.invoicing_city = parts[0].strip() if len(parts) > 0 else ""
                if len(parts) > 1:
                    state_zip = parts[1].strip().split(" ")
                    consortium.invoicing_state = (
                        state_zip[0] if len(state_zip) > 0 else ""
                    )
                    consortium.invoicing_zip = (
                        state_zip[1] if len(state_zip) > 1 else ""
                    )
            consortium.invoicing_country = (
                address_lines[2] if len(address_lines) > 2 else "United States"
            )

        non_gov_projects = Project.query.filter_by(gov_funded=False, active=True).all()
        return render_template(
            "admin/consortium_form.html",
            consortium=consortium,
            action="Edit",
            non_gov_projects=non_gov_projects,
        )

    @app.route("/consortium/<int:id>/delete", methods=["POST"])
    @login_required
    def consortium_delete(id):
        """Delete consortium"""
        consortium = Consortium.query.get_or_404(id)
        try:
            db.session.delete(consortium)
            db.session.commit()
            flash("✅ Consortium deleted successfully!", "success")
        except Exception as e:
            flash(f"❌ Error deleting consortium: {str(e)}", "error")
        return redirect(url_for("consortiums"))

    @app.route("/uploads/logos/<filename>")
    def uploaded_logo(filename):
        """Serve uploaded logo files"""
        from flask import send_from_directory

        return send_from_directory("uploads/logos", filename)

    @app.route("/uploads/terms/<filename>")
    def uploaded_terms(filename):
        """Serve uploaded terms PDF files"""
        from flask import send_from_directory

        return send_from_directory("uploads/terms", filename)

    # Teams routes
    @app.route("/teams")
    @login_required
    def teams():
        """List all teams with counts and consortium info"""
        teams = Team.query.all()

        # Calculate counts and consortium info for each team
        for team in teams:
            # Count projects associated with this team
            team.project_count = Project.query.filter_by(
                team_record_id=team.record_id, active=True
            ).count()

            # Count RFPOs associated with this team
            team.rfpo_count = RFPO.query.filter_by(team_id=team.id).count()

            # Count workflows associated with this team
            team.workflow_count = RFPOApprovalWorkflow.query.filter_by(
                team_id=team.id
            ).count()

            # Check if team can be deleted (no dependencies)
            team.can_delete = team.rfpo_count == 0 and team.workflow_count == 0

            # Count viewers and admins
            team.viewer_count = len(team.get_rfpo_viewer_users())
            team.admin_count = len(team.get_rfpo_admin_users())

            # Get consortium info for badge display
            if team.consortium_consort_id:
                consortium = Consortium.query.filter_by(
                    consort_id=team.consortium_consort_id
                ).first()
                if consortium:
                    team.consortium_name = consortium.name
                    team.consortium_abbrev = consortium.abbrev
                else:
                    team.consortium_name = team.consortium_consort_id
                    team.consortium_abbrev = team.consortium_consort_id
            else:
                team.consortium_name = None
                team.consortium_abbrev = None

        return render_template(
            "admin/teams.html", teams=teams, format_json=format_json_field
        )

    @app.route("/teams/export")
    @login_required
    def teams_export():
        """Export teams as JSON or Excel"""
        export_format = request.args.get("format", "xlsx").lower()

        all_teams = Team.query.order_by(Team.id).all()
        rows = []
        for t in all_teams:
            rows.append(
                {
                    "record_id": t.record_id,
                    "name": t.name,
                    "abbrev": t.abbrev,
                    "description": t.description,
                    "consortium_consort_id": t.consortium_consort_id,
                    "rfpo_viewer_user_ids": t.get_rfpo_viewer_users(),
                    "rfpo_admin_user_ids": t.get_rfpo_admin_users(),
                    "active": bool(t.active),
                }
            )

        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")

        if export_format == "json":
            payload = json.dumps(rows, indent=2)
            return Response(
                payload,
                mimetype="application/json",
                headers={
                    "Content-Disposition": (
                        f"attachment; filename=teams-{timestamp}.json"
                    )
                },
            )

        if pd is None:
            flash("❌ Excel export requires pandas to be installed.", "error")
            return redirect(url_for("teams"))

        # Normalize JSON lists to comma-separated strings for Excel
        excel_rows = []
        for r in rows:
            excel_rows.append(
                {
                    **r,
                    "rfpo_viewer_user_ids": ", ".join(
                        r.get("rfpo_viewer_user_ids") or []
                    ),
                    "rfpo_admin_user_ids": ", ".join(
                        r.get("rfpo_admin_user_ids") or []
                    ),
                }
            )

        df = pd.DataFrame(excel_rows)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Teams", index=False)
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name=f"teams-{timestamp}.xlsx",
            mimetype=(
                "application/vnd.openxmlformats-" "officedocument.spreadsheetml.sheet"
            ),
        )

    @app.route("/teams/export/template")
    @login_required
    def teams_export_template():
        """Download an Excel template for team import"""
        if pd is None:
            flash("❌ Excel export requires pandas to be installed.", "error")
            return redirect(url_for("teams"))

        columns = [
            "record_id",
            "name",
            "abbrev",
            "description",
            "consortium_consort_id",
            "rfpo_viewer_user_ids",  # comma-separated user record_ids
            "rfpo_admin_user_ids",  # comma-separated user record_ids
            "active",  # TRUE/FALSE
        ]
        df = pd.DataFrame(columns=columns)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Teams", index=False)
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name="teams-template.xlsx",
            mimetype=(
                "application/vnd.openxmlformats-" "officedocument.spreadsheetml.sheet"
            ),
        )

    @app.route("/teams/import", methods=["POST"])
    @login_required
    def teams_import():
        """Import teams from JSON/Excel (upsert by record_id or abbrev)"""
        file = request.files.get("import_file")
        if not file or file.filename == "":
            flash("❌ Please choose a file to import.", "error")
            return redirect(url_for("teams"))

        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()

        created = 0
        updated = 0
        skipped = 0
        errors = []

        def _parse_bool(val, default=True):
            if val is None:
                return default
            if isinstance(val, bool):
                return val
            s = str(val).strip().lower()
            return s in ("1", "true", "yes", "y", "t")

        def _parse_list(val):
            if val is None:
                return []
            if isinstance(val, list):
                return [str(x).strip() for x in val if str(x).strip()]
            if isinstance(val, str):
                return [p.strip() for p in val.split(",") if p.strip()]
            return []

        try:
            records = []
            if ext in (".json",):
                try:
                    payload = json.load(file.stream)
                    records = payload if isinstance(payload, list) else [payload]
                except Exception as e:
                    flash(f"❌ Invalid JSON: {str(e)}", "error")
                    return redirect(url_for("teams"))
            elif ext in (".xlsx", ".xls"):
                if pd is None:
                    flash(
                        "❌ Excel import requires pandas to be installed.",
                        "error",
                    )
                    return redirect(url_for("teams"))
                try:
                    df = pd.read_excel(file.stream)
                    records = df.to_dict(orient="records")
                except Exception as e:
                    flash(f"❌ Failed to read Excel: {str(e)}", "error")
                    return redirect(url_for("teams"))
            else:
                flash("❌ Unsupported file type. Use .json or .xlsx", "error")
                return redirect(url_for("teams"))

            for idx, rec in enumerate(records, start=1):
                try:
                    name = (rec.get("name") or "").strip()
                    abbrev = (rec.get("abbrev") or "").strip()
                    if not name or not abbrev:
                        skipped += 1
                        errors.append(f"Row {idx}: missing name or abbrev")
                        continue

                    record_id = (rec.get("record_id") or "").strip()
                    existing = None
                    if record_id:
                        existing = Team.query.filter_by(record_id=record_id).first()
                    if not existing and abbrev:
                        existing = Team.query.filter_by(abbrev=abbrev).first()

                    viewer_ids = _parse_list(rec.get("rfpo_viewer_user_ids"))
                    admin_ids = _parse_list(rec.get("rfpo_admin_user_ids"))
                    active = _parse_bool(rec.get("active"), True)

                    if existing:
                        existing.name = name
                        existing.abbrev = abbrev or existing.abbrev
                        existing.description = (
                            rec.get("description") or existing.description
                        )
                        existing.consortium_consort_id = (
                            rec.get("consortium_consort_id")
                            or existing.consortium_consort_id
                        )
                        existing.active = active
                        existing.set_rfpo_viewer_users(viewer_ids)
                        existing.set_rfpo_admin_users(admin_ids)
                        existing.updated_by = current_user.email
                        updated += 1
                    else:
                        # Auto-generate record_id if missing
                        if not record_id:
                            record_id = generate_next_id(Team, "record_id", "", 8)
                        team = Team(
                            record_id=record_id,
                            name=name,
                            abbrev=abbrev,
                            description=rec.get("description"),
                            consortium_consort_id=(
                                rec.get("consortium_consort_id") or None
                            ),
                            active=active,
                            created_by=current_user.email,
                            updated_by=current_user.email,
                        )
                        team.set_rfpo_viewer_users(viewer_ids)
                        team.set_rfpo_admin_users(admin_ids)
                        db.session.add(team)
                        created += 1
                except Exception as row_err:
                    skipped += 1
                    errors.append(f"Row {idx}: {str(row_err)}")

            db.session.commit()

            summary = (
                "✅ Import complete. Created: "
                f"{created}, Updated: {updated}, Skipped: {skipped}."
            )
            flash(summary, "success")
            if errors:
                flash("\n".join(["⚠️ Issues:"] + errors[:10]), "warning")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Import failed: {str(e)}", "error")

        return redirect(url_for("teams"))

    @app.route("/team/new", methods=["GET", "POST"])
    @login_required
    def team_new():
        """Create new team"""
        if request.method == "POST":
            try:
                # Auto-generate team record ID
                record_id = generate_next_id(Team, "record_id", "", 8)

                team = Team(
                    record_id=record_id,
                    name=request.form.get("name"),
                    abbrev=request.form.get("abbrev"),
                    description=request.form.get("description"),
                    consortium_consort_id=request.form.get("consortium_consort_id")
                    or None,
                    active=bool(request.form.get("active", True)),
                    created_by=current_user.get_display_name(),
                )

                # Handle JSON fields
                viewer_users = parse_comma_list(
                    request.form.get("rfpo_viewer_user_ids")
                )
                admin_users = parse_comma_list(request.form.get("rfpo_admin_user_ids"))

                if viewer_users:
                    team.set_rfpo_viewer_users(viewer_users)
                if admin_users:
                    team.set_rfpo_admin_users(admin_users)

                db.session.add(team)
                db.session.commit()

                flash("✅ Team created successfully!", "success")
                return redirect(url_for("teams"))

            except Exception as e:
                db.session.rollback()
                flash(f"❌ Error creating team: {str(e)}", "error")

        consortiums = Consortium.query.filter_by(active=True).all()
        return render_template(
            "admin/team_form.html", team=None, action="Create", consortiums=consortiums
        )

    @app.route("/team/<int:id>/edit", methods=["GET", "POST"])
    @login_required
    def team_edit(id):
        """Edit team"""
        team = Team.query.get_or_404(id)

        if request.method == "POST":
            try:
                team.record_id = request.form.get("record_id")
                team.name = request.form.get("name")
                team.abbrev = request.form.get("abbrev")
                team.description = request.form.get("description")
                team.consortium_consort_id = (
                    request.form.get("consortium_consort_id") or None
                )
                team.active = bool(request.form.get("active"))
                team.updated_by = current_user.get_display_name()

                # Handle JSON fields
                viewer_users = parse_comma_list(
                    request.form.get("rfpo_viewer_user_ids")
                )
                admin_users = parse_comma_list(request.form.get("rfpo_admin_user_ids"))

                team.set_rfpo_viewer_users(viewer_users)
                team.set_rfpo_admin_users(admin_users)

                db.session.commit()

                flash("✅ Team updated successfully!", "success")
                return redirect(url_for("teams"))

            except Exception as e:
                db.session.rollback()
                flash(f"❌ Error updating team: {str(e)}", "error")

        # Pre-populate JSON fields for editing
        team.rfpo_viewer_user_ids_display = ", ".join(team.get_rfpo_viewer_users())
        team.rfpo_admin_user_ids_display = ", ".join(team.get_rfpo_admin_users())

        consortiums = Consortium.query.filter_by(active=True).all()
        return render_template(
            "admin/team_form.html", team=team, action="Edit", consortiums=consortiums
        )

    @app.route("/team/<int:id>/delete", methods=["POST"])
    @login_required
    def team_delete(id):
        """Delete team"""
        team = Team.query.get_or_404(id)

        # Check for dependencies before deletion
        rfpo_count = RFPO.query.filter_by(team_id=team.id).count()
        user_team_count = UserTeam.query.filter_by(team_id=team.id).count()
        workflow_count = RFPOApprovalWorkflow.query.filter_by(team_id=team.id).count()

        if rfpo_count > 0:
            msg = (
                "❌ Cannot delete team: "
                f"{rfpo_count} RFPOs are associated with this team."
            )
            msg += " Please reassign or delete the RFPOs first."
            flash(msg, "error")
            return redirect(url_for("teams"))

        if workflow_count > 0:
            msg = (
                "❌ Cannot delete team: "
                f"{workflow_count} approval workflows are associated with this team."
            )
            msg += " Please delete the workflows first."
            flash(msg, "error")
            return redirect(url_for("teams"))

        try:
            # Delete user-team associations first (these can be safely deleted)
            if user_team_count > 0:
                UserTeam.query.filter_by(team_id=team.id).delete()

            # Now delete the team
            db.session.delete(team)
            db.session.commit()

            flash("✅ Team deleted successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error deleting team: {str(e)}", "error")
        return redirect(url_for("teams"))

    # Users routes
    @app.route("/users")
    @login_required
    def users():
        """List all users"""
        users = User.query.all()
        return render_template(
            "admin/users.html", users=users, format_json=format_json_field
        )

    @app.route("/users/export")
    @login_required
    def users_export():
        """Export users as JSON or Excel"""
        export_format = request.args.get("format", "xlsx").lower()

        # Build export data (keep only non-sensitive fields)
        users = User.query.order_by(User.id).all()
        rows = []
        for u in users:
            try:
                permissions = u.get_permissions() or []
            except Exception:
                permissions = []
            rows.append(
                {
                    "record_id": u.record_id,
                    "fullname": u.fullname,
                    "email": u.email,
                    "company": u.company,
                    "position": u.position,
                    "permissions": permissions,
                    "active": bool(u.active),
                }
            )

        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")

        if export_format == "json":
            payload = json.dumps(rows, indent=2)
            return Response(
                payload,
                mimetype="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=users-{timestamp}.json"
                },
            )

        # Default to Excel
        if pd is None:
            flash(
                "❌ Excel export requires pandas to be installed.",
                "error",
            )
            return redirect(url_for("users"))

        # Normalize permissions to comma-separated for Excel
        excel_rows = []
        for r in rows:
            excel_rows.append(
                {
                    **r,
                    "permissions": ", ".join(r.get("permissions") or []),
                }
            )

        df = pd.DataFrame(excel_rows)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Users", index=False)
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name=f"users-{timestamp}.xlsx",
            mimetype=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )

    @app.route("/users/export/template")
    @login_required
    def users_export_template():
        """Download an Excel template for user import"""
        if pd is None:
            flash(
                "❌ Excel export requires pandas to be installed.",
                "error",
            )
            return redirect(url_for("users"))

        columns = [
            "record_id",
            "fullname",
            "email",
            "company",
            "position",
            "permissions",  # comma-separated, e.g., "RFPO_USER, RFPO_ADMIN"
            "active",  # TRUE/FALSE
        ]
        df = pd.DataFrame(columns=columns)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Users", index=False)
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name="users-template.xlsx",
            mimetype=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )

    @app.route("/users/import", methods=["POST"])
    @login_required
    def users_import():
        """Import users from uploaded JSON or Excel file"""
        file = request.files.get("import_file")
        if not file or file.filename == "":
            flash("❌ Please choose a file to import.", "error")
            return redirect(url_for("users"))

        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()

        created = 0
        updated = 0
        skipped = 0
        errors = []

        try:
            records = []
            if ext in (".json",):
                try:
                    payload = json.load(file.stream)
                    if isinstance(payload, dict):
                        # Support single-object
                        records = [payload]
                    elif isinstance(payload, list):
                        records = payload
                    else:
                        raise ValueError("JSON must be an object or array")
                except Exception as e:
                    flash(f"❌ Invalid JSON: {str(e)}", "error")
                    return redirect(url_for("users"))
            elif ext in (".xlsx", ".xls"):
                if pd is None:
                    flash(
                        "❌ Excel import requires pandas to be installed.",
                        "error",
                    )
                    return redirect(url_for("users"))
                try:
                    df = pd.read_excel(file.stream)
                    records = df.to_dict(orient="records")
                except Exception as e:
                    flash(f"❌ Failed to read Excel: {str(e)}", "error")
                    return redirect(url_for("users"))
            else:
                flash("❌ Unsupported file type. Use .json or .xlsx", "error")
                return redirect(url_for("users"))

            from werkzeug.security import generate_password_hash

            # Helpers to normalize Excel/JSON values
            def _is_nan(v):
                try:
                    return pd is not None and pd.isna(v)
                except Exception:
                    return False

            def _norm_str(v):
                if v is None or _is_nan(v):
                    return ""
                try:
                    s = str(v)
                except Exception:
                    return ""
                return s.strip()

            def _parse_permissions(v):
                if v is None or _is_nan(v):
                    return []
                if isinstance(v, list):
                    return [str(p).strip() for p in v if str(p).strip()]
                # Treat everything else as string and split by comma
                s = _norm_str(v)
                if not s:
                    return []
                return [p.strip() for p in s.split(",") if p.strip()]

            def _parse_bool(v, default=True):
                if v is None or _is_nan(v):
                    return default
                if isinstance(v, bool):
                    return v
                if isinstance(v, (int, float)):
                    try:
                        return int(v) == 1
                    except Exception:
                        return default
                s = _norm_str(v).lower()
                if s in ("1", "true", "yes", "y", "t"):  # common truthy strings
                    return True
                if s in ("0", "false", "no", "n", "f"):
                    return False
                return default

            for idx, rec in enumerate(records, start=1):
                try:
                    email = _norm_str(rec.get("email"))
                    fullname = _norm_str(rec.get("fullname"))
                    if not email or not fullname:
                        skipped += 1
                        errors.append(f"Row {idx}: missing email or fullname")
                        continue

                    existing = User.query.filter_by(email=email).first()

                    # Normalize permissions and active flag
                    permissions = _parse_permissions(rec.get("permissions"))
                    active = _parse_bool(rec.get("active"), default=True)

                    if existing:
                        # Update basic fields
                        existing.fullname = fullname
                        company = _norm_str(rec.get("company"))
                        position = _norm_str(rec.get("position"))
                        existing.company = company or existing.company
                        existing.position = position or existing.position
                        existing.active = active
                        existing.set_permissions(permissions)
                        existing.updated_by = current_user.email
                        updated += 1
                    else:
                        # Create new user with random secure password
                        record_id = _norm_str(rec.get("record_id")) or generate_next_id(
                            User, "record_id", "", 8
                        )
                        temp_password = secrets.token_urlsafe(12)
                        user = User(
                            record_id=record_id,
                            fullname=fullname,
                            email=email,
                            password_hash=generate_password_hash(temp_password),
                            company=_norm_str(rec.get("company")) or None,
                            position=_norm_str(rec.get("position")) or None,
                            active=active,
                            created_by=current_user.email,
                            updated_by=current_user.email,
                        )
                        user.set_permissions(permissions)
                        db.session.add(user)
                        created += 1
                except Exception as row_err:
                    skipped += 1
                    errors.append(f"Row {idx}: {str(row_err)}")

            db.session.commit()

            # Summarize
            summary = f"✅ Import complete. Created: {created}, Updated: {updated}, Skipped: {skipped}."
            flash(summary, "success")
            if errors:
                flash("\n".join(["⚠️ Issues:"] + errors[:10]), "warning")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Import failed: {str(e)}", "error")

        return redirect(url_for("users"))

    @app.route("/user/new", methods=["GET", "POST"])
    @login_required
    def user_new():
        """Create new user"""
        if request.method == "POST":
            try:
                from werkzeug.security import generate_password_hash

                try:
                    from email_service import email_service, send_welcome_email

                    EMAIL_SERVICE_AVAILABLE = True
                except ImportError:
                    print(
                        "Warning: email_service not available - user creation will work but no welcome email"
                    )
                    EMAIL_SERVICE_AVAILABLE = False
                    send_welcome_email = None

                # Auto-generate user record ID
                record_id = generate_next_id(User, "record_id", "", 8)

                # Get form data
                user_password = request.form.get("password", "changeme123")
                user_email = request.form.get("email")
                user_fullname = request.form.get("fullname")

                user = User(
                    record_id=record_id,
                    fullname=user_fullname,
                    email=user_email,
                    password_hash=generate_password_hash(user_password),
                    sex=request.form.get("sex"),
                    company_code=request.form.get("company_code"),
                    company=request.form.get("company"),
                    position=request.form.get("position"),
                    department=request.form.get("department"),
                    phone=request.form.get("phone"),
                    active=bool(request.form.get("active", True)),
                    agreed_to_terms=bool(request.form.get("agreed_to_terms")),
                    created_by=current_user.get_display_name(),
                )

                # Handle permissions from checkboxes
                permissions = request.form.getlist(
                    "permissions"
                )  # Get all checked permission values

                # Validate that at least one permission is selected
                if not permissions:
                    flash(
                        "❌ Error: At least one permission must be selected for the user.",
                        "error",
                    )

                    # Preserve form data by creating a temporary user object with form values
                    class TempUser:
                        def __init__(self):
                            self.record_id = None  # Will be auto-generated
                            self.fullname = user_fullname
                            self.email = user_email
                            self.sex = request.form.get("sex")
                            self.company_code = request.form.get("company_code")
                            self.company = request.form.get("company")
                            self.position = request.form.get("position")
                            self.department = request.form.get("department")
                            self.phone = request.form.get("phone")
                            self.active = bool(request.form.get("active", True))
                            self.agreed_to_terms = bool(
                                request.form.get("agreed_to_terms")
                            )

                        def get_permissions(self):
                            return []  # No permissions selected

                    temp_user = TempUser()
                    return render_template(
                        "admin/user_form.html", user=temp_user, action="Create"
                    )

                user.set_permissions(permissions)

                db.session.add(user)
                db.session.commit()

                # Send welcome email
                try:
                    if user_email and user_fullname and EMAIL_SERVICE_AVAILABLE:
                        # Determine which app links to include
                        perms_set = set(permissions or [])
                        show_user_link = "RFPO_USER" in perms_set
                        show_admin_link = ("RFPO_ADMIN" in perms_set) or (
                            "GOD" in perms_set
                        )
                        # Super Admin (GOD) -> both; RFPO_ADMIN -> admin; RFPO_USER -> user
                        if "GOD" in perms_set:
                            show_user_link = True
                            show_admin_link = True

                        email_sent = send_welcome_email(
                            user_email=user_email,
                            user_name=user_fullname,
                            temp_password=user_password,
                            show_user_link=show_user_link,
                            show_admin_link=show_admin_link,
                        )
                        diag = (
                            email_service.get_last_send_result()
                            if hasattr(email_service, "get_last_send_result")
                            else {}
                        )
                        if email_sent:
                            prov = diag.get("provider") or "unknown"
                            status = diag.get("status") or "unknown"
                            msg_id = diag.get("message_id") or "(n/a)"
                            sndr = diag.get("sender") or "(no sender)"
                            msg = (
                                f"✅ User created and welcome email sent via {prov} from {sndr}. "
                                f"Status: {status}. Message ID: {msg_id}"
                            )
                            flash(msg, "success")
                        else:
                            prov = diag.get("provider") or "unknown"
                            err = diag.get("error") or "unknown error"
                            flash(
                                f"✅ User created, but welcome email failed via {prov}: {err}",
                                "warning",
                            )
                    else:
                        flash("✅ User created successfully!", "success")
                except Exception as email_error:
                    # Log the email error but don't fail the user creation
                    print(f"Email sending failed: {str(email_error)}")
                    flash(
                        "✅ User created successfully, but welcome email could not be sent.",
                        "warning",
                    )

                return redirect(url_for("users"))

            except Exception as e:
                db.session.rollback()  # Important: rollback the failed transaction
                flash(f"❌ Error creating user: {str(e)}", "error")

        return render_template("admin/user_form.html", user=None, action="Create")

    @app.route("/user/<int:id>/edit", methods=["GET", "POST"])
    @login_required
    def user_edit(id):
        """Edit user"""
        user = User.query.get_or_404(id)

        if request.method == "POST":
            try:
                # Check for email conflicts before making changes
                new_email = request.form.get("email")
                if new_email and new_email != user.email:
                    existing_user = User.query.filter_by(email=new_email).first()
                    if existing_user:
                        flash(
                            f'❌ Email address "{new_email}" is already in use by another user.',
                            "error",
                        )
                        return render_template(
                            "admin/user_form.html", user=user, action="Edit"
                        )

                user.fullname = request.form.get("fullname")
                user.email = new_email
                user.sex = request.form.get("sex")
                user.company_code = request.form.get("company_code")
                user.company = request.form.get("company")
                user.position = request.form.get("position")
                user.department = request.form.get("department")
                user.phone = request.form.get("phone")
                user.active = bool(request.form.get("active"))
                user.agreed_to_terms = bool(request.form.get("agreed_to_terms"))
                user.updated_by = current_user.get_display_name()

                # Handle permissions from checkboxes
                permissions = request.form.getlist("permissions")

                # Validate that at least one permission is selected
                if not permissions:
                    flash(
                        "❌ Error: At least one permission must be selected for the user.",
                        "error",
                    )
                    # Preserve form data by updating user object with form values (but don't save to DB)
                    user.fullname = request.form.get("fullname")
                    user.email = new_email
                    user.sex = request.form.get("sex")
                    user.company_code = request.form.get("company_code")
                    user.company = request.form.get("company")
                    user.position = request.form.get("position")
                    user.department = request.form.get("department")
                    user.phone = request.form.get("phone")
                    user.active = bool(request.form.get("active"))
                    user.agreed_to_terms = bool(request.form.get("agreed_to_terms"))
                    # Keep original permissions for display (don't clear them)
                    return render_template(
                        "admin/user_form.html", user=user, action="Edit"
                    )

                user.set_permissions(permissions)

                db.session.commit()

                flash("✅ User updated successfully!", "success")
                return redirect(url_for("users"))

            except Exception as e:
                db.session.rollback()  # Important: rollback the failed transaction
                flash(f"❌ Error updating user: {str(e)}", "error")

        # Get user permissions mindmap data for display
        try:
            user_mindmap = get_user_mindmap_data(user)
            # Debug output for troubleshooting
            if user_mindmap:
                print(f"🔍 Mindmap Debug for {user.email}:")
                print(
                    f"  Consortiums: {user_mindmap.get('associations', {}).get('consortiums', {})}"
                )
                print(
                    f"  Projects: {user_mindmap.get('associations', {}).get('projects', {})}"
                )
        except Exception as e:
            print(f"Error getting user mindmap: {e}")
            import traceback

            traceback.print_exc()
            user_mindmap = None

        return render_template(
            "admin/user_form.html", user=user, action="Edit", user_mindmap=user_mindmap
        )

    @app.route("/user/<int:id>/delete", methods=["POST"])
    @login_required
    def user_delete(id):
        """Delete user"""
        user = User.query.get_or_404(id)
        try:
            db.session.delete(user)
            db.session.commit()
            flash("✅ User deleted successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error deleting user: {str(e)}", "error")
        return redirect(url_for("users"))

    # RFPOs routes
    @app.route("/rfpos")
    @login_required
    def rfpos():
        """List all RFPOs"""
        rfpos = RFPO.query.all()

        # Add additional info for each RFPO
        for rfpo in rfpos:
            # Check if RFPO has approval instances
            rfpo.approval_instance = RFPOApprovalInstance.query.filter_by(
                rfpo_id=rfpo.id
            ).first()

            # Allow deletion if no approval instance OR if approval instance is completed
            if rfpo.approval_instance is None:
                rfpo.can_delete = True
                rfpo.delete_reason = "No approval workflow"
            elif rfpo.approval_instance.is_complete():
                rfpo.can_delete = True
                rfpo.delete_reason = f"Approval workflow completed ({rfpo.approval_instance.overall_status})"
            else:
                rfpo.can_delete = False
                rfpo.delete_reason = f"Has active approval workflow ({rfpo.approval_instance.overall_status})"

            # Count line items and files
            rfpo.line_item_count = len(rfpo.line_items) if rfpo.line_items else 0
            rfpo.file_count = len(rfpo.files) if rfpo.files else 0

        return render_template("admin/rfpos.html", rfpos=rfpos)

    @app.route("/rfpo/new", methods=["GET"])
    @login_required
    def rfpo_new():
        """Start RFPO creation process - redirect to stage 1"""
        return redirect(url_for("rfpo_create_stage1"))

    @app.route("/rfpo/create/stage1", methods=["GET", "POST"])
    @login_required
    def rfpo_create_stage1():
        """RFPO Creation Stage 1: Select Consortium and Project"""
        if request.method == "POST":
            try:
                consortium_id = request.form.get("consortium_id")
                project_id = request.form.get("project_id")

                if not consortium_id or not project_id:
                    flash("❌ Please select both consortium and project.", "error")
                    return redirect(url_for("rfpo_create_stage1"))

                # Store selections in session for next stage
                from flask import session

                session["rfpo_consortium_id"] = consortium_id
                session["rfpo_project_id"] = project_id

                return redirect(url_for("rfpo_create_stage2"))

            except Exception as e:
                flash(f"❌ Error in stage 1: {str(e)}", "error")

        consortiums = Consortium.query.filter_by(active=True).all()
        return render_template("admin/rfpo_stage1.html", consortiums=consortiums)

    @app.route("/rfpo/create/stage2", methods=["GET", "POST"])
    @login_required
    def rfpo_create_stage2():
        """RFPO Creation Stage 2: Basic Information and Vendor Selection"""
        from flask import session

        consortium_id = session.get("rfpo_consortium_id")
        project_id = session.get("rfpo_project_id")

        if not consortium_id or not project_id:
            flash("❌ Please start from stage 1.", "error")
            return redirect(url_for("rfpo_create_stage1"))

        consortium = Consortium.query.filter_by(consort_id=consortium_id).first()
        project = Project.query.filter_by(project_id=project_id).first()

        if request.method == "POST":
            try:
                # Generate RFPO ID based on project
                today = datetime.now()
                date_str = today.strftime("%Y-%m-%d")
                existing_count = RFPO.query.filter(
                    RFPO.rfpo_id.like(f"RFPO-{project.ref}-%{date_str}%")
                ).count()
                rfpo_id = f"RFPO-{project.ref}-{date_str}-N{existing_count + 1:02d}"

                # Get team from project or create a default team if none exists
                team = (
                    Team.query.filter_by(record_id=project.team_record_id).first()
                    if project.team_record_id
                    else None
                )
                if not team:
                    team = Team.query.filter_by(active=True).first()

                # If no team exists, create a default "No Team" team
                if not team:
                    print("No teams found - creating default team for RFPO creation")
                    default_team = Team(
                        record_id=f"DEFAULT-{datetime.now().strftime('%Y%m%d')}",
                        name="Default Team (No Team Assignment)",
                        abbrev="DEFAULT",
                        description="Auto-created default team for RFPOs without team assignment",
                        consortium_consort_id=consortium_id,
                        active=True,
                        created_by=current_user.get_display_name(),
                    )
                    db.session.add(default_team)
                    db.session.flush()  # Get the ID
                    team = default_team
                    flash("ℹ️ Created default team for RFPO creation.", "info")

                # Create RFPO with enhanced model
                rfpo = RFPO(
                    rfpo_id=rfpo_id,
                    title=request.form.get("title"),
                    description=request.form.get("description"),
                    project_id=project.project_id,
                    consortium_id=consortium.consort_id,
                    team_id=team.id if team else None,
                    government_agreement_number=request.form.get(
                        "government_agreement_number"
                    ),
                    requestor_id=current_user.record_id,
                    requestor_tel=request.form.get("requestor_tel")
                    or current_user.phone,
                    requestor_location=request.form.get("requestor_location")
                    or f"{current_user.company or 'USCAR'}, {current_user.state or 'MI'}",
                    shipto_name=request.form.get("shipto_name"),
                    shipto_tel=request.form.get("shipto_tel"),
                    shipto_address=request.form.get("shipto_address"),
                    invoice_address=consortium.invoicing_address
                    or """United States Council for Automotive
Research LLC
Attn: Accounts Payable
3000 Town Center Building, Suite 35
Southfield, MI  48075""",
                    delivery_date=(
                        datetime.strptime(
                            request.form.get("delivery_date"), "%Y-%m-%d"
                        ).date()
                        if request.form.get("delivery_date")
                        else None
                    ),
                    delivery_type=request.form.get("delivery_type"),
                    delivery_payment=request.form.get("delivery_payment"),
                    delivery_routing=request.form.get("delivery_routing"),
                    payment_terms=request.form.get("payment_terms", "Net 30"),
                    vendor_id=(
                        int(request.form.get("vendor_id"))
                        if request.form.get("vendor_id")
                        else None
                    ),
                    vendor_site_id=_process_vendor_site_id(
                        request.form.get("vendor_site_id")
                    ),
                    created_by=current_user.get_display_name(),
                )

                db.session.add(rfpo)
                db.session.commit()

                # Clear session data
                session.pop("rfpo_consortium_id", None)
                session.pop("rfpo_project_id", None)

                flash(
                    "✅ RFPO created successfully! You can now add line items.",
                    "success",
                )
                return redirect(url_for("rfpo_edit", id=rfpo.id))

            except Exception as e:
                db.session.rollback()
                flash(f"❌ Error creating RFPO: {str(e)}", "error")

        teams = Team.query.filter_by(active=True).all()
        vendors = Vendor.query.filter_by(active=True).all()

        # Pre-fill form with current user data
        current_user_data = {
            "requestor_tel": current_user.phone or "",  # Don't show 'None'
            "requestor_location": f"{current_user.company or 'USCAR'}, {current_user.state or 'MI'}",
            "shipto_name": current_user.get_display_name(),
            "shipto_address": f"{current_user.company or 'USCAR'}, {current_user.state or 'MI'}",
        }

        return render_template(
            "admin/rfpo_stage2.html",
            consortium=consortium,
            project=project,
            teams=teams,
            vendors=vendors,
            current_user_data=current_user_data,
        )

    @app.route("/rfpo/<int:id>/edit", methods=["GET", "POST"])
    @login_required
    def rfpo_edit(id):
        """Edit RFPO with line items"""
        rfpo = RFPO.query.get_or_404(id)

        if request.method == "POST":
            try:
                # Update RFPO information - only update fields that are provided
                # This allows partial updates from different tabs

                # Basic Information fields (only update if provided)
                if "title" in request.form and request.form.get("title") is not None:
                    rfpo.title = request.form.get("title")
                if "description" in request.form:
                    rfpo.description = request.form.get("description")
                if "government_agreement_number" in request.form:
                    rfpo.government_agreement_number = request.form.get(
                        "government_agreement_number"
                    )
                if "requestor_tel" in request.form:
                    rfpo.requestor_tel = request.form.get("requestor_tel")
                if "requestor_location" in request.form:
                    rfpo.requestor_location = request.form.get("requestor_location")
                if "status" in request.form:
                    rfpo.status = request.form.get("status", "Draft")
                if "comments" in request.form:
                    rfpo.comments = request.form.get("comments")

                # Shipping Information fields
                if "shipto_name" in request.form:
                    rfpo.shipto_name = request.form.get("shipto_name")
                if "shipto_tel" in request.form:
                    rfpo.shipto_tel = request.form.get("shipto_tel")
                if "shipto_address" in request.form:
                    rfpo.shipto_address = request.form.get("shipto_address")
                if "delivery_date" in request.form:
                    rfpo.delivery_date = (
                        datetime.strptime(
                            request.form.get("delivery_date"), "%Y-%m-%d"
                        ).date()
                        if request.form.get("delivery_date")
                        else None
                    )
                if "delivery_type" in request.form:
                    rfpo.delivery_type = request.form.get("delivery_type")
                if "delivery_payment" in request.form:
                    rfpo.delivery_payment = request.form.get("delivery_payment")
                if "delivery_routing" in request.form:
                    rfpo.delivery_routing = request.form.get("delivery_routing")
                if "payment_terms" in request.form:
                    rfpo.payment_terms = request.form.get("payment_terms", "Net 30")

                # Vendor Information fields
                if "vendor_id" in request.form:
                    rfpo.vendor_id = (
                        int(request.form.get("vendor_id"))
                        if request.form.get("vendor_id")
                        else None
                    )
                if "vendor_site_id" in request.form:
                    rfpo.vendor_site_id = _process_vendor_site_id(
                        request.form.get("vendor_site_id")
                    )

                # Always update audit fields
                rfpo.updated_by = current_user.get_display_name()

                # Handle cost sharing (only update if provided)
                if "cost_share_description" in request.form:
                    rfpo.cost_share_description = request.form.get(
                        "cost_share_description"
                    )
                if "cost_share_type" in request.form:
                    rfpo.cost_share_type = request.form.get("cost_share_type", "total")
                if "cost_share_amount" in request.form:
                    cost_share_amount = request.form.get("cost_share_amount")
                    if cost_share_amount:
                        try:
                            rfpo.cost_share_amount = float(cost_share_amount)
                        except ValueError:
                            rfpo.cost_share_amount = 0.00

                # Recalculate totals using the new method that handles percentage cost sharing
                rfpo.update_totals()

                db.session.commit()

                flash("✅ RFPO updated successfully!", "success")
                return redirect(url_for("rfpo_edit", id=rfpo.id))

            except Exception as e:
                db.session.rollback()
                flash(f"❌ Error updating RFPO: {str(e)}", "error")

        teams = Team.query.filter_by(active=True).all()
        vendors = Vendor.query.filter_by(active=True).all()

        # Get project and consortium info
        project = Project.query.filter_by(project_id=rfpo.project_id).first()
        consortium = Consortium.query.filter_by(consort_id=rfpo.consortium_id).first()

        # Get document types for file upload dropdown
        doc_types = List.get_by_type("doc_types")

        return render_template(
            "admin/rfpo_edit.html",
            rfpo=rfpo,
            teams=teams,
            vendors=vendors,
            project=project,
            consortium=consortium,
            doc_types=doc_types,
        )

    @app.route("/rfpo/<int:rfpo_id>/line-item/add", methods=["POST"])
    @login_required
    def rfpo_add_line_item(rfpo_id):
        """Add line item to RFPO"""
        rfpo = RFPO.query.get_or_404(rfpo_id)

        try:
            # Get next line number
            max_line = (
                db.session.query(db.func.max(RFPOLineItem.line_number))
                .filter_by(rfpo_id=rfpo.id)
                .scalar()
            )
            next_line_number = (max_line or 0) + 1

            # Create line item
            line_item = RFPOLineItem(
                rfpo_id=rfpo.id,
                line_number=next_line_number,
                quantity=int(request.form.get("quantity", 1)),
                description=request.form.get("description", ""),
                unit_price=float(request.form.get("unit_price", 0.00)),
                is_capital_equipment=bool(request.form.get("is_capital_equipment")),
                capital_description=request.form.get("capital_description"),
                capital_serial_id=request.form.get("capital_serial_id"),
                capital_location=request.form.get("capital_location"),
                capital_condition=request.form.get("capital_condition"),
            )

            # Handle capital equipment date
            capital_date = request.form.get("capital_acquisition_date")
            if capital_date:
                try:
                    line_item.capital_acquisition_date = datetime.strptime(
                        capital_date, "%Y-%m-%d"
                    ).date()
                except ValueError:
                    pass

            # Handle capital cost
            capital_cost = request.form.get("capital_acquisition_cost")
            if capital_cost:
                try:
                    line_item.capital_acquisition_cost = float(capital_cost)
                except ValueError:
                    pass

            line_item.calculate_total()

            db.session.add(line_item)
            db.session.flush()  # Flush to get the line item in the session

            # Update RFPO totals using the new method that handles percentage cost sharing
            rfpo.update_totals()

            db.session.commit()

            flash(f"✅ Line item #{next_line_number} added successfully!", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error adding line item: {str(e)}", "error")

        return redirect(url_for("rfpo_edit", id=rfpo_id))

    @app.route(
        "/rfpo/<int:rfpo_id>/line-item/<int:line_item_id>/delete", methods=["POST"]
    )
    @login_required
    def rfpo_delete_line_item(rfpo_id, line_item_id):
        """Delete line item from RFPO"""
        rfpo = RFPO.query.get_or_404(rfpo_id)
        line_item = RFPOLineItem.query.get_or_404(line_item_id)

        if line_item.rfpo_id != rfpo.id:
            flash("❌ Line item does not belong to this RFPO.", "error")
            return redirect(url_for("rfpo_edit", id=rfpo_id))

        try:
            db.session.delete(line_item)

            # Update RFPO totals using the new method that handles percentage cost sharing
            rfpo.update_totals()

            db.session.commit()

            flash(
                f"✅ Line item #{line_item.line_number} deleted successfully!",
                "success",
            )

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error deleting line item: {str(e)}", "error")

        return redirect(url_for("rfpo_edit", id=rfpo_id))

    @app.route("/rfpo/<int:rfpo_id>/file/upload", methods=["POST"])
    @login_required
    def rfpo_upload_file(rfpo_id):
        """Upload file to RFPO"""
        rfpo = RFPO.query.get_or_404(rfpo_id)

        if "file" not in request.files:
            flash("❌ No file selected.", "error")
            return redirect(url_for("rfpo_edit", id=rfpo_id))

        file = request.files["file"]
        document_type = request.form.get("document_type")
        description = request.form.get("description", "")

        if file.filename == "":
            flash("❌ No file selected.", "error")
            return redirect(url_for("rfpo_edit", id=rfpo_id))

        if not document_type:
            flash("❌ Please select a document type.", "error")
            return redirect(url_for("rfpo_edit", id=rfpo_id))

        try:
            # Validate file size (10 MB max)
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)

            if file_size > 10 * 1024 * 1024:  # 10 MB
                flash("❌ File size exceeds 10 MB limit.", "error")
                return redirect(url_for("rfpo_edit", id=rfpo_id))

            # Get file extension and MIME type
            original_filename = secure_filename(file.filename)
            file_extension = os.path.splitext(original_filename)[1].lower()
            mime_type, _ = mimetypes.guess_type(original_filename)

            # Generate unique file ID and stored filename
            file_id = str(uuid.uuid4())
            stored_filename = f"{file_id}_{original_filename}"

            # Create RFPO-specific directory
            rfpo_dir = os.path.join("uploads", "rfpo_files", f"rfpo_{rfpo.id}")
            os.makedirs(rfpo_dir, exist_ok=True)

            # Full file path
            file_path = os.path.join(rfpo_dir, stored_filename)

            # Save the file
            file.save(file_path)

            # Create database record
            uploaded_file = UploadedFile(
                file_id=file_id,
                original_filename=original_filename,
                stored_filename=stored_filename,
                file_path=file_path,
                file_size=file_size,
                mime_type=mime_type,
                file_extension=file_extension,
                document_type=document_type,
                description=description if description else None,
                rfpo_id=rfpo.id,
                uploaded_by=current_user.get_display_name(),
                processing_status="completed",  # No RAG processing for now
            )

            db.session.add(uploaded_file)
            db.session.commit()

            flash(f'✅ File "{original_filename}" uploaded successfully!', "success")

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error uploading file: {str(e)}", "error")

        return redirect(url_for("rfpo_edit", id=rfpo_id))

    @app.route("/rfpo/<int:rfpo_id>/file/<file_id>/view")
    @login_required
    def view_rfpo_file(rfpo_id, file_id):
        """View/download uploaded file"""
        rfpo = RFPO.query.get_or_404(rfpo_id)
        uploaded_file = UploadedFile.query.filter_by(
            file_id=file_id, rfpo_id=rfpo.id
        ).first_or_404()

        try:
            if not os.path.exists(uploaded_file.file_path):
                flash("❌ File not found on disk.", "error")
                return redirect(url_for("rfpo_edit", id=rfpo_id))

            return send_file(
                uploaded_file.file_path,
                mimetype=uploaded_file.mime_type,
                as_attachment=False,  # Display in browser if possible
                download_name=uploaded_file.original_filename,
            )

        except Exception as e:
            flash(f"❌ Error accessing file: {str(e)}", "error")
            return redirect(url_for("rfpo_edit", id=rfpo_id))

    @app.route("/rfpo/<int:rfpo_id>/file/<file_id>/delete", methods=["POST"])
    @login_required
    def delete_rfpo_file(rfpo_id, file_id):
        """Delete uploaded file"""
        rfpo = RFPO.query.get_or_404(rfpo_id)
        uploaded_file = UploadedFile.query.filter_by(
            file_id=file_id, rfpo_id=rfpo.id
        ).first_or_404()

        try:
            # Delete the physical file
            if os.path.exists(uploaded_file.file_path):
                os.remove(uploaded_file.file_path)

            # Delete the database record (this will cascade delete document chunks)
            filename = uploaded_file.original_filename
            db.session.delete(uploaded_file)
            db.session.commit()

            flash(f'✅ File "{filename}" deleted successfully!', "success")

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error deleting file: {str(e)}", "error")

        return redirect(url_for("rfpo_edit", id=rfpo_id))

    @app.route("/rfpo/<int:rfpo_id>/generate-po-proof")
    @login_required
    def rfpo_generate_po_proof(rfpo_id):
        """Generate PO Proof PDF for RFPO using legacy template approach"""
        rfpo = RFPO.query.get_or_404(rfpo_id)

        try:
            # Get related data
            project = Project.query.filter_by(project_id=rfpo.project_id).first()
            consortium = Consortium.query.filter_by(
                consort_id=rfpo.consortium_id
            ).first()
            vendor = Vendor.query.get(rfpo.vendor_id) if rfpo.vendor_id else None

            # Handle vendor_site_id - regular VendorSite ID or None (uses vendor primary contact)
            vendor_site = None
            if rfpo.vendor_site_id:
                try:
                    vendor_site = VendorSite.query.get(int(rfpo.vendor_site_id))
                except (ValueError, TypeError):
                    vendor_site = None

            if not project or not consortium:
                flash(
                    "❌ Missing project or consortium information for PO Proof generation.",
                    "error",
                )
                return redirect(url_for("rfpo_edit", id=rfpo_id))

            # Get positioning configuration for this consortium (if available)
            positioning_config = PDFPositioning.query.filter_by(
                consortium_id=consortium.consort_id,
                template_name="po_template",
                active=True,
            ).first()

            # Generate PO Proof PDF following legacy pattern:
            # 1. Use po.pdf as background
            # 2. Add consortium logo
            # 3. Use po_page2.pdf for additional line items if needed
            # 4. Merge consortium terms PDF
            pdf_generator = RFPOPDFGenerator(positioning_config=positioning_config)
            pdf_buffer = pdf_generator.generate_po_pdf(
                rfpo, consortium, project, vendor, vendor_site
            )

            # Prepare filename following legacy naming pattern
            date_str = datetime.now().strftime("%Y%m%d")
            filename = f"PO_PROOF_{rfpo.rfpo_id}_{date_str}.pdf"

            # Return PDF as response
            return Response(
                pdf_buffer.getvalue(),
                mimetype="application/pdf",
                headers={
                    "Content-Disposition": f'inline; filename="{filename}"',
                    "Content-Type": "application/pdf",
                },
            )

        except Exception as e:
            print(f"PO Proof generation error: {e}")
            flash(f"❌ Error generating PO Proof: {str(e)}", "error")
            return redirect(url_for("rfpo_edit", id=rfpo_id))

    @app.route("/rfpo/<int:rfpo_id>/generate-po")
    @login_required
    def rfpo_generate_po(rfpo_id):
        """Generate PO PDF for RFPO"""
        rfpo = RFPO.query.get_or_404(rfpo_id)

        try:
            # Get related data
            project = Project.query.filter_by(project_id=rfpo.project_id).first()
            consortium = Consortium.query.filter_by(
                consort_id=rfpo.consortium_id
            ).first()
            vendor = Vendor.query.get(rfpo.vendor_id) if rfpo.vendor_id else None

            # Handle vendor_site_id - regular VendorSite ID or None (uses vendor primary contact)
            vendor_site = None
            if rfpo.vendor_site_id:
                try:
                    vendor_site = VendorSite.query.get(int(rfpo.vendor_site_id))
                except (ValueError, TypeError):
                    vendor_site = None

            if not project or not consortium:
                flash(
                    "❌ Missing project or consortium information for PDF generation.",
                    "error",
                )
                return redirect(url_for("rfpo_edit", id=rfpo_id))

            # Get positioning configuration for this consortium
            positioning_config = PDFPositioning.query.filter_by(
                consortium_id=consortium.consort_id,
                template_name="po_template",
                active=True,
            ).first()

            # Generate PDF with positioning configuration
            pdf_generator = RFPOPDFGenerator(positioning_config=positioning_config)
            pdf_buffer = pdf_generator.generate_po_pdf(
                rfpo, consortium, project, vendor, vendor_site
            )

            # Prepare filename
            filename = f"PO_{rfpo.rfpo_id}_{datetime.now().strftime('%Y%m%d')}.pdf"

            # Return PDF as response
            return Response(
                pdf_buffer.getvalue(),
                mimetype="application/pdf",
                headers={
                    "Content-Disposition": f'inline; filename="{filename}"',
                    "Content-Type": "application/pdf",
                },
            )

        except Exception as e:
            print(f"PDF generation error: {e}")
            flash(f"❌ Error generating PDF: {str(e)}", "error")
            return redirect(url_for("rfpo_edit", id=rfpo_id))

    @app.route("/rfpo/<int:rfpo_id>/generate-rfpo")
    @login_required
    def rfpo_generate_rfpo(rfpo_id):
        """Generate RFPO HTML preview for viewing and printing"""
        rfpo = RFPO.query.get_or_404(rfpo_id)

        try:
            # Get related data
            project = Project.query.filter_by(project_id=rfpo.project_id).first()
            consortium = Consortium.query.filter_by(
                consort_id=rfpo.consortium_id
            ).first()
            vendor = Vendor.query.get(rfpo.vendor_id) if rfpo.vendor_id else None
            vendor_site = None

            # Handle vendor_site_id - regular VendorSite ID or None (uses vendor primary contact)
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

            # Render the RFPO HTML template
            return render_template(
                "admin/rfpo_preview.html",
                rfpo=rfpo,
                project=project,
                consortium=consortium,
                vendor=vendor,
                vendor_site=vendor_site,
                requestor=requestor,
            )

        except Exception as e:
            print(f"RFPO generation error: {e}")
            flash(f"❌ Error generating RFPO: {str(e)}", "error")
            return redirect(url_for("rfpo_edit", id=rfpo_id))

    @app.route("/api/rfpo/<int:rfpo_id>/rendered-html")
    def api_rfpo_rendered_html(rfpo_id):
        """API endpoint to get RFPO rendered HTML (for user app)"""
        try:
            rfpo = RFPO.query.get_or_404(rfpo_id)

            # Get related data (same as generate-rfpo route)
            project = Project.query.filter_by(project_id=rfpo.project_id).first()
            consortium = Consortium.query.filter_by(
                consort_id=rfpo.consortium_id
            ).first()
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

            # Render the same template as admin panel
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

        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

    @app.route("/rfpo/<int:id>/delete", methods=["POST"])
    @login_required
    def rfpo_delete(id):
        """Delete RFPO"""
        rfpo = RFPO.query.get_or_404(id)

        # Check for approval instances that might prevent deletion
        approval_instance = RFPOApprovalInstance.query.filter_by(
            rfpo_id=rfpo.id
        ).first()
        if approval_instance and not approval_instance.is_complete():
            msg = (
                "❌ Cannot delete RFPO: It has an active approval workflow "
                f"(Instance: {approval_instance.instance_id}, "
                f"Status: {approval_instance.overall_status}). "
                "Please complete or cancel the approval process first."
            )
            flash(msg, "error")
            return redirect(url_for("rfpos"))

        try:
            # The following will be automatically deleted due to cascade settings:
            # - RFPOLineItem (line items)
            # - UploadedFile (uploaded files and their document chunks)
            db.session.delete(rfpo)
            db.session.commit()
            flash("✅ RFPO deleted successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error deleting RFPO: {str(e)}", "error")
        return redirect(url_for("rfpos"))

    # Projects routes
    @app.route("/projects")
    @login_required
    def projects():
        """List all projects with consortium and team info"""
        projects = Project.query.all()

        # Populate consortium and team info for each project
        for project in projects:
            # Get consortium information for badges
            project.consortium_info = []
            consortium_ids = project.get_consortium_ids()
            for consortium_id in consortium_ids:
                consortium = Consortium.query.filter_by(
                    consort_id=consortium_id
                ).first()
                if consortium:
                    project.consortium_info.append(
                        {
                            "id": consortium.consort_id,
                            "name": consortium.name,
                            "abbrev": consortium.abbrev,
                        }
                    )

            # Get team information for badge
            if project.team_record_id:
                team = Team.query.filter_by(record_id=project.team_record_id).first()
                if team:
                    project.team_info = {
                        "id": team.record_id,
                        "name": team.name,
                        "abbrev": team.abbrev,
                    }
                else:
                    project.team_info = None
            else:
                project.team_info = None

        return render_template(
            "admin/projects.html", projects=projects, format_json=format_json_field
        )

    @app.route("/projects/export")
    @login_required
    def projects_export():
        """Export projects as JSON or Excel"""
        export_format = request.args.get("format", "xlsx").lower()

        all_projects = Project.query.order_by(Project.id).all()
        rows = []
        for p in all_projects:
            rows.append(
                {
                    "project_id": p.project_id,
                    "ref": p.ref,
                    "name": p.name,
                    "description": p.description,
                    "consortium_ids": p.get_consortium_ids(),
                    "team_record_id": p.team_record_id,
                    "rfpo_viewer_user_ids": p.get_rfpo_viewer_users(),
                    "gov_funded": bool(p.gov_funded),
                    "uni_project": bool(p.uni_project),
                    "active": bool(p.active),
                }
            )

        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")

        if export_format == "json":
            payload = json.dumps(rows, indent=2)
            return Response(
                payload,
                mimetype="application/json",
                headers={
                    "Content-Disposition": (
                        f"attachment; filename=projects-{timestamp}.json"
                    )
                },
            )

        if pd is None:
            flash("❌ Excel export requires pandas to be installed.", "error")
            return redirect(url_for("projects"))

        excel_rows = []
        for r in rows:
            excel_rows.append(
                {
                    **r,
                    "consortium_ids": ", ".join(r.get("consortium_ids") or []),
                    "rfpo_viewer_user_ids": ", ".join(
                        r.get("rfpo_viewer_user_ids") or []
                    ),
                }
            )

        df = pd.DataFrame(excel_rows)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Projects", index=False)
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name=f"projects-{timestamp}.xlsx",
            mimetype=(
                "application/vnd.openxmlformats-" "officedocument.spreadsheetml.sheet"
            ),
        )

    @app.route("/projects/export/template")
    @login_required
    def projects_export_template():
        """Download an Excel template for project import"""
        if pd is None:
            flash("❌ Excel export requires pandas to be installed.", "error")
            return redirect(url_for("projects"))

        columns = [
            "project_id",
            "ref",
            "name",
            "description",
            "consortium_ids",  # comma-separated consort_ids
            "team_record_id",
            "rfpo_viewer_user_ids",  # comma-separated user record_ids
            "gov_funded",  # TRUE/FALSE
            "uni_project",  # TRUE/FALSE
            "active",  # TRUE/FALSE
        ]
        df = pd.DataFrame(columns=columns)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Projects", index=False)
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name="projects-template.xlsx",
            mimetype=(
                "application/vnd.openxmlformats-" "officedocument.spreadsheetml.sheet"
            ),
        )

    @app.route("/projects/import", methods=["POST"])
    @login_required
    def projects_import():
        """Import projects from JSON/Excel (upsert by project_id or ref)"""
        file = request.files.get("import_file")
        if not file or file.filename == "":
            flash("❌ Please choose a file to import.", "error")
            return redirect(url_for("projects"))

        filename = secure_filename(file.filename or "upload")
        ext = os.path.splitext(filename)[1].lower()

        created = 0
        updated = 0
        skipped = 0
        errors = []

        def _parse_bool(val, default=True):
            if val is None:
                return default
            if isinstance(val, bool):
                return val
            s = str(val).strip().lower()
            return s in ("1", "true", "yes", "y", "t")

        def _parse_list(val):
            if val is None:
                return []
            if isinstance(val, list):
                return [str(x).strip() for x in val if str(x).strip()]
            if isinstance(val, str):
                return [p.strip() for p in val.split(",") if p.strip()]
            return []

        try:
            records = []
            if ext in (".json",):
                try:
                    payload = json.load(file.stream)
                    records = payload if isinstance(payload, list) else [payload]
                except Exception as e:
                    flash(f"❌ Invalid JSON: {str(e)}", "error")
                    return redirect(url_for("projects"))
            elif ext in (".xlsx", ".xls"):
                if pd is None:
                    flash(
                        "❌ Excel import requires pandas to be installed.",
                        "error",
                    )
                    return redirect(url_for("projects"))
                try:
                    df = pd.read_excel(file.stream)
                    records = df.to_dict(orient="records")
                except Exception as e:
                    flash(f"❌ Failed to read Excel: {str(e)}", "error")
                    return redirect(url_for("projects"))
            else:
                flash("❌ Unsupported file type. Use .json or .xlsx", "error")
                return redirect(url_for("projects"))

            for idx, rec in enumerate(records, start=1):
                try:
                    name = (rec.get("name") or "").strip()
                    ref = (rec.get("ref") or "").strip()
                    if not name or not ref:
                        skipped += 1
                        errors.append("Row {}: missing name or ref".format(idx))
                        continue

                    project_id = (rec.get("project_id") or "").strip()
                    existing = None
                    if project_id:
                        existing = Project.query.filter_by(
                            project_id=project_id
                        ).first()
                    if not existing and ref:
                        existing = Project.query.filter_by(ref=ref).first()

                    cons_ids = _parse_list(rec.get("consortium_ids"))
                    viewer_ids = _parse_list(rec.get("rfpo_viewer_user_ids"))
                    gov_funded = _parse_bool(rec.get("gov_funded"), True)
                    uni_project = _parse_bool(rec.get("uni_project"), False)
                    active = _parse_bool(rec.get("active"), True)

                    if existing:
                        existing.ref = ref or existing.ref
                        existing.name = name
                        existing.description = (
                            rec.get("description") or existing.description
                        )
                        existing.team_record_id = (
                            rec.get("team_record_id") or existing.team_record_id
                        )
                        existing.gov_funded = gov_funded
                        existing.uni_project = uni_project
                        existing.active = active
                        existing.set_consortium_ids(cons_ids)
                        existing.set_rfpo_viewer_users(viewer_ids)
                        existing.updated_by = current_user.email
                        updated += 1
                    else:
                        # Auto-generate project_id if missing
                        if not project_id:
                            project_id = generate_next_id(Project, "project_id", "", 8)
                        project = Project(
                            project_id=project_id,
                            ref=ref,
                            name=name,
                            description=rec.get("description"),
                            team_record_id=rec.get("team_record_id") or None,
                            gov_funded=gov_funded,
                            uni_project=uni_project,
                            active=active,
                            created_by=current_user.email,
                            updated_by=current_user.email,
                        )
                        project.set_consortium_ids(cons_ids)
                        project.set_rfpo_viewer_users(viewer_ids)
                        db.session.add(project)
                        created += 1
                except Exception as row_err:
                    skipped += 1
                    errors.append(f"Row {idx}: {str(row_err)}")

            db.session.commit()

            summary = (
                "✅ Import complete. Created: "
                f"{created}, Updated: {updated}, Skipped: {skipped}."
            )
            flash(summary, "success")
            if errors:
                flash("\n".join(["⚠️ Issues:"] + errors[:10]), "warning")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Import failed: {str(e)}", "error")

        return redirect(url_for("projects"))

    @app.route("/project/new", methods=["GET", "POST"])
    @login_required
    def project_new():
        """Create new project"""
        if request.method == "POST":
            try:
                # Auto-generate project ID
                project_id = generate_next_id(Project, "project_id", "", 8)

                project = Project(
                    project_id=project_id,
                    ref=request.form.get("ref"),
                    name=request.form.get("name"),
                    description=request.form.get("description"),
                    team_record_id=request.form.get("team_record_id") or None,
                    gov_funded=bool(request.form.get("gov_funded")),
                    uni_project=bool(request.form.get("uni_project")),
                    active=bool(request.form.get("active", True)),
                    created_by=current_user.get_display_name(),
                )

                # Handle JSON fields
                consortium_ids = parse_comma_list(request.form.get("consortium_ids"))
                viewer_users = parse_comma_list(
                    request.form.get("rfpo_viewer_user_ids")
                )

                if consortium_ids:
                    project.set_consortium_ids(consortium_ids)
                if viewer_users:
                    project.set_rfpo_viewer_users(viewer_users)

                db.session.add(project)
                db.session.commit()

                flash("✅ Project created successfully!", "success")

                # If opened inside a modal, return a minimal page that posts a message to the parent
                if request.args.get("modal") == "1":
                    try:
                        consortium_ids = project.get_consortium_ids()
                    except Exception:
                        consortium_ids = []
                    return render_template(
                        "admin/project_created_modal.html",
                        project=project,
                        consortium_ids=consortium_ids,
                    )

                return redirect(url_for("projects"))

            except Exception as e:
                db.session.rollback()
                flash(f"❌ Error creating project: {str(e)}", "error")

        teams = Team.query.filter_by(active=True).all()
        return render_template(
            "admin/project_form.html", project=None, action="Create", teams=teams
        )

    @app.route("/project/<int:id>/edit", methods=["GET", "POST"])
    @login_required
    def project_edit(id):
        """Edit project"""
        project = Project.query.get_or_404(id)

        if request.method == "POST":
            try:
                project.ref = request.form.get("ref")
                project.name = request.form.get("name")
                project.description = request.form.get("description")
                project.team_record_id = request.form.get("team_record_id") or None
                project.gov_funded = bool(request.form.get("gov_funded"))
                project.uni_project = bool(request.form.get("uni_project"))
                project.active = bool(request.form.get("active"))
                project.updated_by = current_user.get_display_name()

                # Handle JSON fields
                consortium_ids = parse_comma_list(request.form.get("consortium_ids"))
                viewer_users = parse_comma_list(
                    request.form.get("rfpo_viewer_user_ids")
                )

                project.set_consortium_ids(consortium_ids)
                project.set_rfpo_viewer_users(viewer_users)

                db.session.commit()

                flash("✅ Project updated successfully!", "success")
                return redirect(url_for("projects"))

            except Exception as e:
                db.session.rollback()
                flash(f"❌ Error updating project: {str(e)}", "error")

        # Pre-populate JSON fields for editing
        project.consortium_ids_display = ", ".join(project.get_consortium_ids())
        project.rfpo_viewer_user_ids_display = ", ".join(
            project.get_rfpo_viewer_users()
        )

        teams = Team.query.filter_by(active=True).all()
        return render_template(
            "admin/project_form.html", project=project, action="Edit", teams=teams
        )

    @app.route("/project/<int:id>/delete", methods=["POST"])
    @login_required
    def project_delete(id):
        """Delete project"""
        project = Project.query.get_or_404(id)
        try:
            db.session.delete(project)
            db.session.commit()
            flash("✅ Project deleted successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error deleting project: {str(e)}", "error")
        return redirect(url_for("projects"))

    # Vendors routes
    @app.route("/vendors")
    @login_required
    def vendors():
        """List all vendors with consortium info"""
        vendors = Vendor.query.all()

        # Populate consortium info for each vendor
        for vendor in vendors:
            # Get consortium information for badges
            vendor.consortium_info = []
            approved_consortiums = vendor.get_approved_consortiums()
            for consortium_abbrev in approved_consortiums:
                consortium = Consortium.query.filter_by(
                    abbrev=consortium_abbrev
                ).first()
                if consortium:
                    vendor.consortium_info.append(
                        {
                            "abbrev": consortium.abbrev,
                            "name": consortium.name,
                            "id": consortium.consort_id,
                        }
                    )
                else:
                    # If consortium not found, still show the abbreviation
                    vendor.consortium_info.append(
                        {
                            "abbrev": consortium_abbrev,
                            "name": consortium_abbrev,
                            "id": consortium_abbrev,
                        }
                    )

        return render_template(
            "admin/vendors.html", vendors=vendors, format_json=format_json_field
        )

    @app.route("/vendors/export")
    @login_required
    def vendors_export():
        """Export vendors as JSON or Excel"""
        export_format = request.args.get("format", "xlsx").lower()

        all_vendors = Vendor.query.order_by(Vendor.id).all()
        rows = []
        for v in all_vendors:
            rows.append(
                {
                    "vendor_id": v.vendor_id,
                    "company_name": v.company_name,
                    "status": v.status,
                    "vendor_type": v.vendor_type,
                    "certs_reps": bool(v.certs_reps),
                    "cert_date": (
                        v.cert_date.strftime("%Y-%m-%d") if v.cert_date else None
                    ),
                    "cert_expire_date": (
                        v.cert_expire_date.strftime("%Y-%m-%d")
                        if v.cert_expire_date
                        else None
                    ),
                    "is_university": bool(v.is_university),
                    "approved_consortiums": v.get_approved_consortiums(),
                    "onetime_project_id": v.onetime_project_id,
                    "contact_name": v.contact_name,
                    "contact_dept": v.contact_dept,
                    "contact_tel": v.contact_tel,
                    "contact_fax": v.contact_fax,
                    "contact_address": v.contact_address,
                    "contact_city": v.contact_city,
                    "contact_state": v.contact_state,
                    "contact_zip": v.contact_zip,
                    "contact_country": v.contact_country,
                    "active": bool(v.active),
                }
            )

        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")

        if export_format == "json":
            payload = json.dumps(rows, indent=2)
            return Response(
                payload,
                mimetype="application/json",
                headers={
                    "Content-Disposition": (
                        f"attachment; filename=vendors-{timestamp}.json"
                    )
                },
            )

        if pd is None:
            flash("❌ Excel export requires pandas to be installed.", "error")
            return redirect(url_for("vendors"))

        excel_rows = []
        for r in rows:
            excel_rows.append(
                {
                    **r,
                    "approved_consortiums": ", ".join(
                        r.get("approved_consortiums") or []
                    ),
                }
            )

        df = pd.DataFrame(excel_rows)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Vendors", index=False)
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name=f"vendors-{timestamp}.xlsx",
            mimetype=(
                "application/vnd.openxmlformats-" "officedocument.spreadsheetml.sheet"
            ),
        )

    @app.route("/vendors/export/template")
    @login_required
    def vendors_export_template():
        """Download an Excel template for vendor import"""
        if pd is None:
            flash("❌ Excel export requires pandas to be installed.", "error")
            return redirect(url_for("vendors"))

        columns = [
            "vendor_id",
            "company_name",
            "status",
            "vendor_type",
            "certs_reps",
            "cert_date",
            "cert_expire_date",
            "is_university",
            "approved_consortiums",  # comma-separated consortium abbrevs
            "onetime_project_id",
            "contact_name",
            "contact_dept",
            "contact_tel",
            "contact_fax",
            "contact_address",
            "contact_city",
            "contact_state",
            "contact_zip",
            "contact_country",
            "active",
        ]
        df = pd.DataFrame(columns=columns)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Vendors", index=False)
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name="vendors-template.xlsx",
            mimetype=(
                "application/vnd.openxmlformats-" "officedocument.spreadsheetml.sheet"
            ),
        )

    @app.route("/vendors/import", methods=["POST"])
    @login_required
    def vendors_import():
        # Import vendors from JSON/Excel (upsert by id or company name)
        file = request.files.get("import_file")
        if not file or file.filename == "":
            flash("❌ Please choose a file to import.", "error")
            return redirect(url_for("vendors"))

        filename = secure_filename(file.filename or "upload")
        ext = os.path.splitext(filename)[1].lower()

        created = 0
        updated = 0
        skipped = 0
        errors = []

        def _parse_bool(val, default=True):
            if val is None:
                return default
            if isinstance(val, bool):
                return val
            s = str(val).strip().lower()
            return s in ("1", "true", "yes", "y", "t")

        def _parse_int(val, default=0):
            try:
                return int(val)
            except Exception:
                return default

        def _parse_date(val):
            if not val:
                return None
            try:
                if isinstance(val, str):
                    return datetime.strptime(val, "%Y-%m-%d").date()
                # pandas may give Timestamp
                return val.date() if hasattr(val, "date") else None
            except Exception:
                return None

        def _parse_list(val):
            if val is None:
                return []
            if isinstance(val, list):
                return [str(x).strip() for x in val if str(x).strip()]
            if isinstance(val, str):
                return [p.strip() for p in val.split(",") if p.strip()]
            return []

        try:
            records = []
            if ext in (".json",):
                try:
                    payload = json.load(file.stream)
                    records = payload if isinstance(payload, list) else [payload]
                except Exception as e:
                    flash(f"❌ Invalid JSON: {str(e)}", "error")
                    return redirect(url_for("vendors"))
            elif ext in (".xlsx", ".xls"):
                if pd is None:
                    flash(
                        "❌ Excel import requires pandas to be installed.",
                        "error",
                    )
                    return redirect(url_for("vendors"))
                try:
                    df = pd.read_excel(file.stream)
                    records = df.to_dict(orient="records")
                except Exception as e:
                    flash(f"❌ Failed to read Excel: {str(e)}", "error")
                    return redirect(url_for("vendors"))
            else:
                flash("❌ Unsupported file type. Use .json or .xlsx", "error")
                return redirect(url_for("vendors"))

            for idx, rec in enumerate(records, start=1):
                try:
                    company_name = (rec.get("company_name") or "").strip()
                    if not company_name:
                        skipped += 1
                        errors.append(f"Row {idx}: missing company_name")
                        continue

                    vendor_id = (rec.get("vendor_id") or "").strip()
                    existing = None
                    if vendor_id:
                        existing = Vendor.query.filter_by(vendor_id=vendor_id).first()
                    if not existing and company_name:
                        existing = Vendor.query.filter_by(
                            company_name=company_name
                        ).first()

                    approved = _parse_list(rec.get("approved_consortiums"))

                    # parse fields
                    status = (rec.get("status") or "live").strip()
                    vtype = _parse_int(rec.get("vendor_type"), 0)
                    certs_reps = _parse_bool(rec.get("certs_reps"), False)
                    cert_date = _parse_date(rec.get("cert_date"))
                    cert_expire_date = _parse_date(rec.get("cert_expire_date"))
                    is_university = _parse_bool(rec.get("is_university"), False)
                    active = _parse_bool(rec.get("active"), True)

                    if existing:
                        existing.company_name = company_name
                        existing.status = status or existing.status
                        existing.vendor_type = vtype
                        existing.certs_reps = certs_reps
                        existing.cert_date = cert_date
                        existing.cert_expire_date = cert_expire_date
                        existing.is_university = is_university
                        existing.onetime_project_id = (
                            rec.get("onetime_project_id") or existing.onetime_project_id
                        )
                        existing.contact_name = (
                            rec.get("contact_name") or existing.contact_name
                        )
                        existing.contact_dept = (
                            rec.get("contact_dept") or existing.contact_dept
                        )
                        existing.contact_tel = (
                            rec.get("contact_tel") or existing.contact_tel
                        )
                        existing.contact_fax = (
                            rec.get("contact_fax") or existing.contact_fax
                        )
                        existing.contact_address = (
                            rec.get("contact_address") or existing.contact_address
                        )
                        existing.contact_city = (
                            rec.get("contact_city") or existing.contact_city
                        )
                        existing.contact_state = (
                            rec.get("contact_state") or existing.contact_state
                        )
                        existing.contact_zip = (
                            rec.get("contact_zip") or existing.contact_zip
                        )
                        existing.contact_country = (
                            rec.get("contact_country") or existing.contact_country
                        )
                        existing.active = active
                        existing.set_approved_consortiums(approved)
                        existing.updated_by = current_user.email
                        updated += 1
                    else:
                        if not vendor_id:
                            vendor_id = generate_next_id(Vendor, "vendor_id", "", 8)
                        vendor = Vendor(
                            vendor_id=vendor_id,
                            company_name=company_name,
                            status=status,
                            vendor_type=vtype,
                            certs_reps=certs_reps,
                            cert_date=cert_date,
                            cert_expire_date=cert_expire_date,
                            is_university=is_university,
                            onetime_project_id=(rec.get("onetime_project_id") or None),
                            contact_name=rec.get("contact_name"),
                            contact_dept=rec.get("contact_dept"),
                            contact_tel=rec.get("contact_tel"),
                            contact_fax=rec.get("contact_fax"),
                            contact_address=rec.get("contact_address"),
                            contact_city=rec.get("contact_city"),
                            contact_state=rec.get("contact_state"),
                            contact_zip=rec.get("contact_zip"),
                            contact_country=rec.get("contact_country"),
                            active=active,
                            created_by=current_user.email,
                            updated_by=current_user.email,
                        )
                        vendor.set_approved_consortiums(approved)
                        db.session.add(vendor)
                        created += 1
                except Exception as row_err:
                    skipped += 1
                    errors.append(f"Row {idx}: {str(row_err)}")

            db.session.commit()

            summary = (
                "✅ Import complete. Created: "
                f"{created}, Updated: {updated}, Skipped: {skipped}."
            )
            flash(summary, "success")
            if errors:
                flash("\n".join(["⚠️ Issues:"] + errors[:10]), "warning")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Import failed: {str(e)}", "error")

        return redirect(url_for("vendors"))

    @app.route("/consortiums/export")
    @login_required
    def consortiums_export():
        """Export consortiums as JSON or Excel"""
        export_format = request.args.get("format", "xlsx").lower()

        all_consortiums = Consortium.query.order_by(Consortium.id).all()
        rows = []
        for c in all_consortiums:
            rows.append(
                {
                    "consort_id": c.consort_id,
                    "name": c.name,
                    "abbrev": c.abbrev,
                    "require_approved_vendors": bool(c.require_approved_vendors),
                    "non_government_project_id": c.non_government_project_id,
                    "rfpo_viewer_user_ids": c.get_rfpo_viewer_users(),
                    "rfpo_admin_user_ids": c.get_rfpo_admin_users(),
                    "invoicing_address": c.invoicing_address,
                    "doc_fax_name": c.doc_fax_name,
                    "doc_fax_number": c.doc_fax_number,
                    "doc_email_name": c.doc_email_name,
                    "doc_email_address": c.doc_email_address,
                    "doc_post_name": c.doc_post_name,
                    "doc_post_address": c.doc_post_address,
                    "po_email": c.po_email,
                    "active": bool(c.active),
                }
            )

        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")

        if export_format == "json":
            payload = json.dumps(rows, indent=2)
            return Response(
                payload,
                mimetype="application/json",
                headers={
                    "Content-Disposition": (
                        f"attachment; filename=consortiums-{timestamp}.json"
                    )
                },
            )

        if pd is None:
            flash("❌ Excel export requires pandas to be installed.", "error")
            return redirect(url_for("consortiums"))

        excel_rows = []
        for r in rows:
            excel_rows.append(
                {
                    **r,
                    "rfpo_viewer_user_ids": ", ".join(
                        r.get("rfpo_viewer_user_ids") or []
                    ),
                    "rfpo_admin_user_ids": ", ".join(
                        r.get("rfpo_admin_user_ids") or []
                    ),
                }
            )

        df = pd.DataFrame(excel_rows)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Consortiums", index=False)
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name=f"consortiums-{timestamp}.xlsx",
            mimetype=(
                "application/vnd.openxmlformats-" "officedocument.spreadsheetml.sheet"
            ),
        )

    @app.route("/consortiums/export/template")
    @login_required
    def consortiums_export_template():
        """Download an Excel template for consortium import"""
        if pd is None:
            flash("❌ Excel export requires pandas to be installed.", "error")
            return redirect(url_for("consortiums"))

        columns = [
            "consort_id",
            "name",
            "abbrev",
            "require_approved_vendors",
            "non_government_project_id",
            "rfpo_viewer_user_ids",  # comma-separated user record_ids
            "rfpo_admin_user_ids",  # comma-separated user record_ids
            "invoicing_address",
            "doc_fax_name",
            "doc_fax_number",
            "doc_email_name",
            "doc_email_address",
            "doc_post_name",
            "doc_post_address",
            "po_email",
            "active",
        ]
        df = pd.DataFrame(columns=columns)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Consortiums", index=False)
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name="consortiums-template.xlsx",
            mimetype=(
                "application/vnd.openxmlformats-" "officedocument.spreadsheetml.sheet"
            ),
        )

    @app.route("/consortiums/import", methods=["POST"])
    @login_required
    def consortiums_import():
        # Import consortiums from JSON/Excel (upsert by id or abbrev)
        file = request.files.get("import_file")
        if not file or file.filename == "":
            flash("❌ Please choose a file to import.", "error")
            return redirect(url_for("consortiums"))

        filename = secure_filename(file.filename or "upload")
        ext = os.path.splitext(filename)[1].lower()

        created = 0
        updated = 0
        skipped = 0
        errors = []

        def _parse_bool(val, default=True):
            if val is None:
                return default
            if isinstance(val, bool):
                return val
            s = str(val).strip().lower()
            return s in ("1", "true", "yes", "y", "t")

        def _parse_list(val):
            if val is None:
                return []
            if isinstance(val, list):
                return [str(x).strip() for x in val if str(x).strip()]
            if isinstance(val, str):
                return [p.strip() for p in val.split(",") if p.strip()]
            return []

        try:
            records = []
            if ext in (".json",):
                try:
                    payload = json.load(file.stream)
                    records = payload if isinstance(payload, list) else [payload]
                except Exception as e:
                    flash(f"❌ Invalid JSON: {str(e)}", "error")
                    return redirect(url_for("consortiums"))
            elif ext in (".xlsx", ".xls"):
                if pd is None:
                    flash(
                        "❌ Excel import requires pandas to be installed.",
                        "error",
                    )
                    return redirect(url_for("consortiums"))
                try:
                    df = pd.read_excel(file.stream)
                    records = df.to_dict(orient="records")
                except Exception as e:
                    flash(f"❌ Failed to read Excel: {str(e)}", "error")
                    return redirect(url_for("consortiums"))
            else:
                flash("❌ Unsupported file type. Use .json or .xlsx", "error")
                return redirect(url_for("consortiums"))

            for idx, rec in enumerate(records, start=1):
                try:
                    name = (rec.get("name") or "").strip()
                    abbrev = (rec.get("abbrev") or "").strip()
                    if not name or not abbrev:
                        skipped += 1
                        errors.append(f"Row {idx}: missing name or abbrev")
                        continue

                    consort_id = (rec.get("consort_id") or "").strip()
                    existing = None
                    if consort_id:
                        existing = Consortium.query.filter_by(
                            consort_id=consort_id
                        ).first()
                    if not existing and abbrev:
                        existing = Consortium.query.filter_by(abbrev=abbrev).first()

                    viewer_ids = _parse_list(rec.get("rfpo_viewer_user_ids"))
                    admin_ids = _parse_list(rec.get("rfpo_admin_user_ids"))
                    require_approved = _parse_bool(
                        rec.get("require_approved_vendors"), True
                    )
                    active = _parse_bool(rec.get("active"), True)

                    if existing:
                        existing.name = name
                        existing.abbrev = abbrev or existing.abbrev
                        existing.require_approved_vendors = require_approved
                        existing.non_government_project_id = (
                            rec.get("non_government_project_id")
                            or existing.non_government_project_id
                        )
                        existing.invoicing_address = (
                            rec.get("invoicing_address") or existing.invoicing_address
                        )
                        existing.doc_fax_name = (
                            rec.get("doc_fax_name") or existing.doc_fax_name
                        )
                        existing.doc_fax_number = (
                            rec.get("doc_fax_number") or existing.doc_fax_number
                        )
                        existing.doc_email_name = (
                            rec.get("doc_email_name") or existing.doc_email_name
                        )
                        existing.doc_email_address = (
                            rec.get("doc_email_address") or existing.doc_email_address
                        )
                        existing.doc_post_name = (
                            rec.get("doc_post_name") or existing.doc_post_name
                        )
                        existing.doc_post_address = (
                            rec.get("doc_post_address") or existing.doc_post_address
                        )
                        existing.po_email = rec.get("po_email") or existing.po_email
                        existing.active = active
                        existing.set_rfpo_viewer_users(viewer_ids)
                        existing.set_rfpo_admin_users(admin_ids)
                        existing.updated_by = current_user.email
                        updated += 1
                    else:
                        if not consort_id:
                            consort_id = generate_next_id(
                                Consortium, "consort_id", "", 8
                            )
                        consortium = Consortium(
                            consort_id=consort_id,
                            name=name,
                            abbrev=abbrev,
                            require_approved_vendors=require_approved,
                            non_government_project_id=rec.get(
                                "non_government_project_id"
                            )
                            or None,
                            rfpo_viewer_user_ids=None,
                            rfpo_admin_user_ids=None,
                            invoicing_address=rec.get("invoicing_address"),
                            doc_fax_name=rec.get("doc_fax_name"),
                            doc_fax_number=rec.get("doc_fax_number"),
                            doc_email_name=rec.get("doc_email_name"),
                            doc_email_address=rec.get("doc_email_address"),
                            doc_post_name=rec.get("doc_post_name"),
                            doc_post_address=rec.get("doc_post_address"),
                            po_email=rec.get("po_email"),
                            active=active,
                            created_by=current_user.email,
                            updated_by=current_user.email,
                        )
                        consortium.set_rfpo_viewer_users(viewer_ids)
                        consortium.set_rfpo_admin_users(admin_ids)
                        db.session.add(consortium)
                        created += 1
                except Exception as row_err:
                    skipped += 1
                    errors.append(f"Row {idx}: {str(row_err)}")

            db.session.commit()

            summary = (
                "✅ Import complete. Created: "
                f"{created}, Updated: {updated}, Skipped: {skipped}."
            )
            flash(summary, "success")
            if errors:
                flash("\n".join(["⚠️ Issues:"] + errors[:10]), "warning")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Import failed: {str(e)}", "error")

        return redirect(url_for("consortiums"))

    @app.route("/vendor/new", methods=["GET", "POST"])
    @login_required
    def vendor_new():
        """Create new vendor"""
        if request.method == "POST":
            try:
                # Auto-generate vendor ID
                vendor_id = generate_next_id(Vendor, "vendor_id", "", 8)

                vendor = Vendor(
                    vendor_id=vendor_id,
                    company_name=request.form.get("company_name"),
                    status=request.form.get("status", "live"),
                    vendor_type=int(request.form.get("vendor_type", 0)),
                    certs_reps=bool(request.form.get("certs_reps")),
                    cert_date=(
                        datetime.strptime(
                            request.form.get("cert_date"), "%Y-%m-%d"
                        ).date()
                        if request.form.get("cert_date")
                        else None
                    ),
                    cert_expire_date=(
                        datetime.strptime(
                            request.form.get("cert_expire_date"), "%Y-%m-%d"
                        ).date()
                        if request.form.get("cert_expire_date")
                        else None
                    ),
                    is_university=bool(request.form.get("is_university")),
                    onetime_project_id=request.form.get("onetime_project_id") or None,
                    contact_name=request.form.get("contact_name"),
                    contact_dept=request.form.get("contact_dept"),
                    contact_tel=request.form.get("contact_tel"),
                    contact_fax=request.form.get("contact_fax"),
                    contact_address=request.form.get("contact_address"),
                    contact_city=request.form.get("contact_city"),
                    contact_state=request.form.get("contact_state"),
                    contact_zip=request.form.get("contact_zip"),
                    contact_country=request.form.get("contact_country"),
                    active=bool(request.form.get("active", True)),
                    created_by=current_user.get_display_name(),
                )

                # Handle approved consortiums from selection interface
                approved_consortiums = parse_comma_list(
                    request.form.get("approved_consortiums")
                )
                if approved_consortiums:
                    vendor.set_approved_consortiums(approved_consortiums)

                db.session.add(vendor)
                db.session.commit()

                flash("✅ Vendor created successfully!", "success")
                return redirect(url_for("vendors"))

            except Exception as e:
                db.session.rollback()
                flash(f"❌ Error creating vendor: {str(e)}", "error")

        return render_template("admin/vendor_form.html", vendor=None, action="Create")

    @app.route("/vendor/<int:id>/edit", methods=["GET", "POST"])
    @login_required
    def vendor_edit(id):
        """Edit vendor"""
        vendor = Vendor.query.get_or_404(id)

        if request.method == "POST":
            try:
                vendor.company_name = request.form.get("company_name")
                vendor.status = request.form.get("status", "live")
                vendor.vendor_type = int(request.form.get("vendor_type", 0))
                vendor.certs_reps = bool(request.form.get("certs_reps"))
                vendor.cert_date = (
                    datetime.strptime(request.form.get("cert_date"), "%Y-%m-%d").date()
                    if request.form.get("cert_date")
                    else None
                )
                vendor.cert_expire_date = (
                    datetime.strptime(
                        request.form.get("cert_expire_date"), "%Y-%m-%d"
                    ).date()
                    if request.form.get("cert_expire_date")
                    else None
                )
                vendor.onetime_project_id = (
                    request.form.get("onetime_project_id") or None
                )
                vendor.contact_name = request.form.get("contact_name")
                vendor.contact_dept = request.form.get("contact_dept")
                vendor.contact_tel = request.form.get("contact_tel")
                vendor.contact_fax = request.form.get("contact_fax")
                vendor.contact_address = request.form.get("contact_address")
                vendor.contact_city = request.form.get("contact_city")
                vendor.contact_state = request.form.get("contact_state")
                vendor.contact_zip = request.form.get("contact_zip")
                vendor.contact_country = request.form.get("contact_country")
                vendor.active = bool(request.form.get("active"))
                vendor.updated_by = current_user.get_display_name()

                # Handle approved consortiums
                approved_consortiums = parse_comma_list(
                    request.form.get("approved_consortiums")
                )
                vendor.set_approved_consortiums(approved_consortiums)

                db.session.commit()

                flash("✅ Vendor updated successfully!", "success")
                return redirect(url_for("vendors"))

            except Exception as e:
                db.session.rollback()
                flash(f"❌ Error updating vendor: {str(e)}", "error")

        # Pre-populate JSON fields for editing
        vendor.approved_consortiums_display = ", ".join(
            vendor.get_approved_consortiums()
        )

        return render_template("admin/vendor_form.html", vendor=vendor, action="Edit")

    @app.route("/vendor/<int:id>/delete", methods=["POST"])
    @login_required
    def vendor_delete(id):
        """Delete vendor"""
        vendor = Vendor.query.get_or_404(id)
        try:
            db.session.delete(vendor)
            db.session.commit()
            flash("✅ Vendor deleted successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error deleting vendor: {str(e)}", "error")
        return redirect(url_for("vendors"))

    # Vendor Sites (Contacts) routes
    @app.route("/vendor-site/new", methods=["GET", "POST"])
    @login_required
    def vendor_site_new():
        """Create new vendor site/contact"""
        vendor_id = request.args.get("vendor_id")
        vendor = Vendor.query.get_or_404(vendor_id) if vendor_id else None

        if request.method == "POST":
            try:
                # Auto-generate vendor site ID
                vendor_site_id = generate_next_id(VendorSite, "vendor_site_id", "", 8)

                vendor_site = VendorSite(
                    vendor_site_id=vendor_site_id,
                    vendor_id=int(request.form.get("vendor_id")),
                    contact_name=request.form.get("contact_name"),
                    contact_dept=request.form.get("contact_dept"),
                    contact_tel=request.form.get("contact_tel"),
                    contact_fax=request.form.get("contact_fax"),
                    contact_address=request.form.get("contact_address"),
                    contact_city=request.form.get("contact_city"),
                    contact_state=request.form.get("contact_state"),
                    contact_zip=request.form.get("contact_zip"),
                    contact_country=request.form.get("contact_country"),
                    active=bool(request.form.get("active", True)),
                    created_by=current_user.get_display_name(),
                )

                db.session.add(vendor_site)
                db.session.commit()

                flash("✅ Vendor contact created successfully!", "success")
                return redirect(url_for("vendor_edit", id=vendor_site.vendor_id))

            except Exception as e:
                db.session.rollback()
                flash(f"❌ Error creating vendor contact: {str(e)}", "error")

        vendors = Vendor.query.filter_by(active=True).all()
        return render_template(
            "admin/vendor_site_form.html",
            vendor_site=None,
            action="Create",
            vendors=vendors,
            selected_vendor=vendor,
        )

    @app.route("/vendor-site/<int:id>/edit", methods=["GET", "POST"])
    @login_required
    def vendor_site_edit(id):
        """Edit vendor site/contact"""
        vendor_site = VendorSite.query.get_or_404(id)

        if request.method == "POST":
            try:
                vendor_site.contact_name = request.form.get("contact_name")
                vendor_site.contact_dept = request.form.get("contact_dept")
                vendor_site.contact_tel = request.form.get("contact_tel")
                vendor_site.contact_fax = request.form.get("contact_fax")
                vendor_site.contact_address = request.form.get("contact_address")
                vendor_site.contact_city = request.form.get("contact_city")
                vendor_site.contact_state = request.form.get("contact_state")
                vendor_site.contact_zip = request.form.get("contact_zip")
                vendor_site.contact_country = request.form.get("contact_country")
                vendor_site.active = bool(request.form.get("active"))
                vendor_site.updated_by = current_user.get_display_name()

                db.session.commit()

                flash("✅ Vendor contact updated successfully!", "success")
                return redirect(url_for("vendor_edit", id=vendor_site.vendor_id))

            except Exception as e:
                db.session.rollback()
                flash(f"❌ Error updating vendor contact: {str(e)}", "error")

        vendors = Vendor.query.filter_by(active=True).all()
        return render_template(
            "admin/vendor_site_form.html",
            vendor_site=vendor_site,
            action="Edit",
            vendors=vendors,
            selected_vendor=vendor_site.vendor,
        )

    @app.route("/vendor-site/<int:id>/delete", methods=["POST"])
    @login_required
    def vendor_site_delete(id):
        """Delete vendor site/contact"""
        vendor_site = VendorSite.query.get_or_404(id)
        vendor_id = vendor_site.vendor_id
        try:
            db.session.delete(vendor_site)
            db.session.commit()
            flash("✅ Vendor contact deleted successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error deleting vendor contact: {str(e)}", "error")
        return redirect(url_for("vendor_edit", id=vendor_id))

    # Lists routes (Configuration Management)
    @app.route("/lists")
    @login_required
    def lists():
        """List all configuration lists grouped by type"""
        # Group lists by type
        list_types = db.session.query(List.type).distinct().all()
        grouped_lists = {}

        for (list_type,) in list_types:
            grouped_lists[list_type] = (
                List.query.filter_by(type=list_type, active=True)
                .order_by(List.key)
                .all()
            )

        return render_template("admin/lists.html", grouped_lists=grouped_lists)

    @app.route("/list/new", methods=["GET", "POST"])
    @login_required
    def list_new():
        """Create new list item"""
        if request.method == "POST":
            try:
                # Auto-generate list ID
                list_id = generate_next_id(List, "list_id", "", 10)

                list_item = List(
                    list_id=list_id,
                    type=request.form.get("type"),
                    key=request.form.get("key"),
                    value=request.form.get("value"),
                    active=bool(request.form.get("active", True)),
                    created_by=current_user.get_display_name(),
                )

                db.session.add(list_item)
                db.session.commit()

                flash("✅ List item created successfully!", "success")
                return redirect(url_for("lists"))

            except Exception as e:
                db.session.rollback()
                flash(f"❌ Error creating list item: {str(e)}", "error")

        # Get existing types for dropdown
        existing_types = [t[0] for t in db.session.query(List.type).distinct().all()]
        return render_template(
            "admin/list_form.html",
            list_item=None,
            action="Create",
            existing_types=existing_types,
        )

    @app.route("/list/new/<list_type>", methods=["GET", "POST"])
    @login_required
    def list_new_for_type(list_type):
        """Create new list item for a specific list type"""
        if request.method == "POST":
            try:
                # Auto-generate list ID
                list_id = generate_next_id(List, "list_id", "", 10)

                list_item = List(
                    list_id=list_id,
                    type=list_type,  # Pre-filled with the specified type
                    key=request.form.get("key"),
                    value=request.form.get("value"),
                    active=bool(request.form.get("active", True)),
                    created_by=current_user.get_display_name(),
                )

                db.session.add(list_item)
                db.session.commit()

                flash(f"✅ {list_type.title()} item created successfully!", "success")
                return redirect(url_for("lists"))

            except Exception as e:
                db.session.rollback()
                flash(f"❌ Error creating {list_type} item: {str(e)}", "error")

        # Get existing types for dropdown (in case user wants to change)
        existing_types = [t[0] for t in db.session.query(List.type).distinct().all()]

        # Get description for this list type
        list_type_descriptions = {
            "adminlevel": "System permission levels and user roles",
            "meeting_it": "Meeting and IT resource types",
            "rfpo_appro": "RFPO approval workflow levels",
            "rfpo_brack": "RFPO budget brackets and limits",
            "rfpo_statu": "RFPO status values",
            "doc_types": "Document types required for approval stages",
        }

        return render_template(
            "admin/list_form.html",
            list_item=None,
            action="Create",
            existing_types=existing_types,
            preset_type=list_type,
            list_type_description=list_type_descriptions.get(
                list_type, f"Configuration values for {list_type}"
            ),
        )

    @app.route("/list/<int:id>/edit", methods=["GET", "POST"])
    @login_required
    def list_edit(id):
        """Edit list item"""
        list_item = List.query.get_or_404(id)

        if request.method == "POST":
            try:
                list_item.type = request.form.get("type")
                list_item.key = request.form.get("key")
                list_item.value = request.form.get("value")
                list_item.active = bool(request.form.get("active"))
                list_item.updated_by = current_user.get_display_name()

                db.session.commit()

                flash("✅ List item updated successfully!", "success")
                return redirect(url_for("lists"))

            except Exception as e:
                db.session.rollback()
                flash(f"❌ Error updating list item: {str(e)}", "error")

        existing_types = [t[0] for t in db.session.query(List.type).distinct().all()]
        return render_template(
            "admin/list_form.html",
            list_item=list_item,
            action="Edit",
            existing_types=existing_types,
        )

    @app.route("/list/<int:id>/delete", methods=["POST"])
    @login_required
    def list_delete(id):
        """Delete list item"""
        list_item = List.query.get_or_404(id)
        try:
            db.session.delete(list_item)
            db.session.commit()
            flash("✅ List item deleted successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error deleting list item: {str(e)}", "error")
        return redirect(url_for("lists"))

    @app.route("/seed-lists", methods=["POST"])
    @login_required
    def seed_lists():
        """Seed the database with required list configurations"""
        try:
            # Configuration data as specified
            config_data = [
                # Admin levels
                ("adminlevel", "CAL_MEET_USER", "Meeting Calendar User"),
                ("adminlevel", "GOD", "Super Admin"),
                ("adminlevel", "RFPO_ADMIN", "RFPO Full Admin"),
                ("adminlevel", "RFPO_USER", "RFPO User"),
                ("adminlevel", "VROOM_ADMIN", "VROOM Full Admin"),
                ("adminlevel", "VROOM_USER", "VROOM User"),
                # Meeting IT
                ("meeting_it", "AV", "Projector/VCR/TV"),
                ("meeting_it", "PC", "PC/Laptop"),
                ("meeting_it", "ROOM", "Meeting Room"),
                ("meeting_it", "TEL", "Video/Tele Conference"),
                ("meeting_it", "XXX", "Misc"),
                # RFPO Approval levels
                ("rfpo_appro", "5", "Vendor Review"),
                ("rfpo_appro", "8", "Management Review"),
                ("rfpo_appro", "10", "Technical Approval"),
                ("rfpo_appro", "12", "Project Manager Approval"),
                ("rfpo_appro", "20", "Board Approval"),
                ("rfpo_appro", "21", "Executive Director Approval"),
                ("rfpo_appro", "22", "Management Committee Approval"),
                ("rfpo_appro", "23", "Technical Leadership Council"),
                ("rfpo_appro", "25", "Steering Approval"),
                ("rfpo_appro", "26", "Finance Approval"),
                ("rfpo_appro", "28", "USCAR Leadership Group Approval"),
                ("rfpo_appro", "29", "USCAR Internal Approval"),
                ("rfpo_appro", "30", "Treasurer's Review"),
                ("rfpo_appro", "35", "Partnership Chair"),
                ("rfpo_appro", "36", "TLC Oversight"),
                ("rfpo_appro", "40", "Vice President Approval"),
                ("rfpo_appro", "99", "PO Release Approval"),
                # RFPO Brackets
                ("rfpo_brack", "10", "5000"),
                ("rfpo_brack", "20", "15000"),
                ("rfpo_brack", "30", "100000"),
                ("rfpo_brack", "40", "150000"),
                ("rfpo_brack", "50", "999999999"),
                # RFPO Status
                ("rfpo_statu", "10", "draft"),
                ("rfpo_statu", "15", "waiting"),
                ("rfpo_statu", "20", "conditional"),
                ("rfpo_statu", "30", "approved"),
                ("rfpo_statu", "40", "refused"),
                # Document Types for Approval Stages
                ("doc_types", "00000039", "Statement of Work"),
                ("doc_types", "00000038", "Quote or proposal"),
                ("doc_types", "00000073", "Cost Justification"),
                ("doc_types", "00000070", "Basis for selecting contractor"),
                ("doc_types", "00000079", "Signed Cross License Agreement"),
                ("doc_types", "00000160", ""),  # Empty value as in original
                ("doc_types", "00000221", "EERE Pre-Award Information Sheet"),
                (
                    "doc_types",
                    "00000222",
                    "Basis for Selecting Contractor (Waiver of Competition)",
                ),
                ("doc_types", "00000223", "Financial Due Diligence Letter (signed)"),
                ("doc_types", "00000224", "Budget Justification"),
                ("doc_types", "00000230", "post RFPO upload"),
            ]

            created_count = 0
            for list_type, key, value in config_data:
                # Check if already exists
                existing = List.query.filter_by(type=list_type, key=key).first()
                if not existing:
                    list_id = generate_next_id(List, "list_id", "", 10)
                    list_item = List(
                        list_id=list_id,
                        type=list_type,
                        key=key,
                        value=value,
                        active=True,
                        created_by=current_user.get_display_name(),
                    )
                    db.session.add(list_item)
                    created_count += 1

            db.session.commit()
            flash(f"✅ Seeded {created_count} list configuration items!", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error seeding lists: {str(e)}", "error")

        return redirect(url_for("lists"))

    @app.route("/seed-consortiums", methods=["POST"])
    @login_required
    def seed_consortiums():
        """Seed the database with standard consortium data"""
        try:
            # Standard consortium data as specified
            consortium_data = [
                ("APT", "Advanced Powertrain"),
                ("EETLC", "EETLC"),
                ("MAT", "Materials TLC"),
                ("Non-USCAR", "Non-USCAR"),
                ("OSRP", "Occupant Safety Research Partnership"),
                ("USABC", "United States Advanced Battery Consortium"),
                ("USAMP", "United States Automotive Materials Partnership"),
                ("USCAR", "United States Council for Automotive Research LLC"),
                ("HFC", "USCAR Hydrogen & Fuel Cell TLC"),
                ("MFG", "USCAR LLC Manufacturing Technical Leadership Council"),
            ]

            created_count = 0
            for abbrev, name in consortium_data:
                # Check if already exists by abbreviation
                existing = Consortium.query.filter_by(abbrev=abbrev).first()
                if not existing:
                    # Auto-generate consortium ID
                    consort_id = generate_next_id(Consortium, "consort_id", "", 8)

                    consortium = Consortium(
                        consort_id=consort_id,
                        name=name,
                        abbrev=abbrev,
                        require_approved_vendors=True,  # Default to requiring approved vendors
                        active=True,
                        created_by=current_user.get_display_name(),
                    )
                    db.session.add(consortium)
                    created_count += 1
                else:
                    # Update existing consortium to ensure it's active and has correct name
                    existing.name = name
                    existing.active = True
                    existing.updated_by = current_user.get_display_name()

            db.session.commit()

            if created_count > 0:
                flash(f"✅ Seeded {created_count} new consortiums!", "success")
            else:
                flash(
                    "ℹ️  All standard consortiums already exist and have been updated.",
                    "info",
                )

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error seeding consortiums: {str(e)}", "error")

        return redirect(url_for("consortiums"))

    # RFPO Approval Workflow routes
    @app.route("/approval-workflows")
    @app.route("/approval-workflows/<workflow_type>")
    @login_required
    def approval_workflows(workflow_type="consortium"):
        """List RFPO approval workflows by type (consortium, team, project)"""
        # Validate workflow type
        if workflow_type not in ["consortium", "team", "project"]:
            workflow_type = "consortium"

        workflows = (
            RFPOApprovalWorkflow.query.filter_by(
                workflow_type=workflow_type, is_template=True
            )
            .order_by(RFPOApprovalWorkflow.is_active.desc(), RFPOApprovalWorkflow.name)
            .all()
        )

        # Add entity info and statistics
        for workflow in workflows:
            if workflow_type == "consortium":
                consortium = Consortium.query.filter_by(
                    consort_id=workflow.consortium_id
                ).first()
                workflow.entity_name = (
                    consortium.name if consortium else workflow.consortium_id
                )
                workflow.entity_abbrev = (
                    consortium.abbrev if consortium else workflow.consortium_id
                )
            elif workflow_type == "team":
                team = Team.query.get(workflow.team_id) if workflow.team_id else None
                workflow.entity_name = team.name if team else f"Team {workflow.team_id}"
                workflow.entity_abbrev = team.abbrev if team else f"T{workflow.team_id}"
                # Add consortium info for teams
                if team and team.consortium_consort_id:
                    consortium = Consortium.query.filter_by(
                        consort_id=team.consortium_consort_id
                    ).first()
                    workflow.consortium_name = (
                        consortium.name if consortium else team.consortium_consort_id
                    )
            elif workflow_type == "project":
                project = Project.query.filter_by(
                    project_id=workflow.project_id
                ).first()
                workflow.entity_name = project.name if project else workflow.project_id
                workflow.entity_abbrev = project.ref if project else workflow.project_id
                # Add consortium info for projects
                if project:
                    consortium_ids = project.get_consortium_ids()
                    if consortium_ids:
                        consortium = Consortium.query.filter_by(
                            consort_id=consortium_ids[0]
                        ).first()
                        workflow.consortium_name = (
                            consortium.name if consortium else consortium_ids[0]
                        )

            # Count usage statistics
            all_instances = RFPOApprovalInstance.query.filter_by(
                template_workflow_id=workflow.id
            ).all()
            workflow.instance_count = len(all_instances)

            # Check if workflow can be deleted (inactive + all instances completed)
            workflow.can_delete = True
            if workflow.is_active:
                workflow.can_delete = False
                workflow.delete_reason = "Workflow is currently active"
            elif all_instances:
                # Check if all instances are completed
                incomplete_instances = [
                    inst for inst in all_instances if not inst.is_complete()
                ]
                if incomplete_instances:
                    workflow.can_delete = False
                    workflow.delete_reason = (
                        f"Has {len(incomplete_instances)} incomplete approval instances"
                    )
                else:
                    workflow.can_delete = True
                    workflow.delete_reason = (
                        f"All {len(all_instances)} instances are completed"
                    )
            else:
                workflow.can_delete = True
                workflow.delete_reason = "No instances using this workflow"

        # Get counts for each workflow type for tabs
        workflow_counts = {
            "consortium": RFPOApprovalWorkflow.query.filter_by(
                workflow_type="consortium", is_template=True
            ).count(),
            "team": RFPOApprovalWorkflow.query.filter_by(
                workflow_type="team", is_template=True
            ).count(),
            "project": RFPOApprovalWorkflow.query.filter_by(
                workflow_type="project", is_template=True
            ).count(),
        }

        return render_template(
            "admin/approval_workflows.html",
            workflows=workflows,
            current_workflow_type=workflow_type,
            workflow_counts=workflow_counts,
        )

    @app.route("/approval-workflow/new")
    @app.route("/approval-workflow/new/<workflow_type>")
    @login_required
    def approval_workflow_new_form(workflow_type="consortium"):
        """Show form for creating new approval workflow"""
        # Validate workflow type
        if workflow_type not in ["consortium", "team", "project"]:
            workflow_type = "consortium"

        # Get entities based on workflow type
        if workflow_type == "consortium":
            entities = Consortium.query.filter_by(active=True).all()
        elif workflow_type == "team":
            entities = Team.query.filter_by(active=True).all()
        elif workflow_type == "project":
            entities = Project.query.filter_by(active=True).all()

        return render_template(
            "admin/approval_workflow_form.html",
            workflow=None,
            action="Create",
            workflow_type=workflow_type,
            entities=entities,
        )

    # Backward compatibility route
    @app.route("/approval-workflow-new")
    @login_required
    def approval_workflow_new():
        """Backward compatibility route"""
        return approval_workflow_new_form("consortium")

    @app.route("/approval-workflow/create", methods=["POST"])
    @login_required
    def approval_workflow_create():
        """Create new approval workflow"""
        try:
            workflow_type = request.form.get("workflow_type", "consortium")

            # Validate workflow type
            if workflow_type not in ["consortium", "team", "project"]:
                flash("❌ Invalid workflow type.", "error")
                return redirect(url_for("approval_workflows"))

            # Auto-generate workflow ID
            workflow_id = generate_next_id(
                RFPOApprovalWorkflow, "workflow_id", "WF-", 8
            )

            workflow = RFPOApprovalWorkflow(
                workflow_id=workflow_id,
                name=request.form.get("name"),
                description=request.form.get("description"),
                version=request.form.get("version", "1.0"),
                workflow_type=workflow_type,
                is_active=bool(request.form.get("is_active")),
                created_by=current_user.get_display_name(),
            )

            # Set the appropriate entity association
            if workflow_type == "consortium":
                workflow.consortium_id = request.form.get("entity_id")
            elif workflow_type == "team":
                workflow.team_id = int(request.form.get("entity_id"))
            elif workflow_type == "project":
                workflow.project_id = request.form.get("entity_id")

            # If marking as active, deactivate others for this entity
            if workflow.is_active:
                workflow.activate()

            db.session.add(workflow)
            db.session.commit()

            # Sync approver status for affected users
            try:
                sync_user_approver_status_for_workflow(
                    workflow.id, updated_by=current_user.get_display_name()
                )
            except Exception as e:
                print(
                    f"Warning: Could not sync approver status after workflow creation: {e}"
                )

            flash("✅ Approval workflow created successfully!", "success")
            return redirect(url_for("approval_workflow_edit", id=workflow.id))

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error creating approval workflow: {str(e)}", "error")
            return redirect(url_for("approval_workflows", workflow_type=workflow_type))

    @app.route("/approval-workflow/<int:id>/edit", methods=["GET", "POST"])
    @login_required
    def approval_workflow_edit(id):
        """Edit approval workflow with stages and steps"""
        workflow = RFPOApprovalWorkflow.query.get_or_404(id)

        if request.method == "POST":
            try:
                workflow.name = request.form.get("name")
                workflow.description = request.form.get("description")
                workflow.version = request.form.get("version", "1.0")
                workflow.consortium_id = request.form.get("consortium_id")

                # Handle activation
                new_active_status = bool(request.form.get("is_active"))
                if new_active_status and not workflow.is_active:
                    workflow.activate()
                elif not new_active_status:
                    workflow.is_active = False

                workflow.updated_by = current_user.get_display_name()

                db.session.commit()

                # Sync approver status for affected users
                try:
                    sync_user_approver_status_for_workflow(
                        workflow.id, updated_by=current_user.get_display_name()
                    )
                except Exception as e:
                    print(
                        f"Warning: Could not sync approver status after workflow edit: {e}"
                    )

                flash("✅ Approval workflow updated successfully!", "success")
                return redirect(url_for("approval_workflow_edit", id=workflow.id))

            except Exception as e:
                db.session.rollback()
                flash(f"❌ Error updating approval workflow: {str(e)}", "error")

        consortiums = Consortium.query.filter_by(active=True).all()
        # Case-insensitive lookups to support RFPO_BRACK / RFPO_APPRO
        budget_brackets = List.get_by_type_ci("RFPO_BRACK")
        approval_types = List.get_by_type_ci("RFPO_APPRO")
        document_types = List.get_by_type("doc_types")
        users = User.query.filter_by(active=True).all()

        return render_template(
            "admin/approval_workflow_edit.html",
            workflow=workflow,
            consortiums=consortiums,
            budget_brackets=budget_brackets,
            approval_types=approval_types,
            document_types=document_types,
            users=users,
        )

    @app.route("/approval-workflow/<int:workflow_id>/stage/add", methods=["POST"])
    @login_required
    def approval_workflow_add_stage(workflow_id):
        """Add stage to approval workflow"""
        workflow = RFPOApprovalWorkflow.query.get_or_404(workflow_id)

        try:
            # Get next stage order
            max_order = (
                db.session.query(db.func.max(RFPOApprovalStage.stage_order))
                .filter_by(workflow_id=workflow.id)
                .scalar()
            )
            next_order = (max_order or 0) + 1

            # Auto-generate stage ID
            stage_id = generate_next_id(RFPOApprovalStage, "stage_id", "STG-", 8)

            # Get budget bracket info (case-insensitive type + robust parsing)
            bracket_key = request.form.get("budget_bracket_key")
            bracket_item = List.get_item_ci("RFPO_BRACK", bracket_key)
            bracket_amount = (
                _parse_budget_amount(bracket_item.value) if bracket_item else 0.00
            )

            # Generate stage name from budget bracket
            stage_name = (
                f"Up to ${bracket_amount:,.0f}"
                if bracket_amount > 0
                else f"Budget Bracket {bracket_key}"
            )

            stage = RFPOApprovalStage(
                stage_id=stage_id,
                stage_name=stage_name,
                stage_order=next_order,
                description=request.form.get("description"),
                budget_bracket_key=bracket_key,
                budget_bracket_amount=bracket_amount,
                workflow_id=workflow.id,
                requires_all_steps=True,  # Always require all steps
                is_parallel=False,  # Never parallel
            )

            # Handle required document types from dual-list picker
            doc_types_str = request.form.get("required_document_types", "")
            if doc_types_str:
                doc_types = [
                    dt.strip() for dt in doc_types_str.split(",") if dt.strip()
                ]
                stage.set_required_document_types(doc_types)

            db.session.add(stage)
            db.session.commit()

            # Verify no steps were auto-created
            step_count = RFPOApprovalStep.query.filter_by(stage_id=stage.id).count()
            if step_count > 0:
                flash(
                    f"⚠️ Warning: {step_count} steps were unexpectedly created for this stage!",
                    "warning",
                )

            flash(
                f'✅ Stage "{stage.stage_name}" added successfully! (0 steps)',
                "success",
            )

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error adding stage: {str(e)}", "error")

        return redirect(url_for("approval_workflow_edit", id=workflow_id))

    @app.route(
        "/approval-workflow/<int:workflow_id>/stage/<int:stage_id>/step/add",
        methods=["POST"],
    )
    @login_required
    def approval_workflow_add_step(workflow_id, stage_id):
        """Add step to approval stage"""
        workflow = RFPOApprovalWorkflow.query.get_or_404(workflow_id)
        stage = RFPOApprovalStage.query.get_or_404(stage_id)

        if stage.workflow_id != workflow.id:
            flash("❌ Stage does not belong to this workflow.", "error")
            return redirect(url_for("approval_workflow_edit", id=workflow_id))

        try:
            # Get next step order
            max_order = (
                db.session.query(db.func.max(RFPOApprovalStep.step_order))
                .filter_by(stage_id=stage.id)
                .scalar()
            )
            next_order = (max_order or 0) + 1

            # Auto-generate step ID
            step_id = generate_next_id(RFPOApprovalStep, "step_id", "STP-", 8)

            # Get approval type info
            approval_key = request.form.get("approval_type_key")
            approval_item = List.get_item_ci("RFPO_APPRO", approval_key)
            approval_name = approval_item.value if approval_item else approval_key

            # Use approval type name as step name
            step_name = approval_name

            step = RFPOApprovalStep(
                step_id=step_id,
                step_name=step_name,
                step_order=next_order,
                description=request.form.get("description"),
                approval_type_key=approval_key,
                approval_type_name=approval_name,
                stage_id=stage.id,
                primary_approver_id=request.form.get("primary_approver_id"),
                backup_approver_id=request.form.get("backup_approver_id") or None,
                is_required=True,  # Always required
                timeout_days=0,  # No timeout
                auto_escalate=False,  # Never auto-escalate
            )

            db.session.add(step)
            db.session.commit()

            # Sync approver status for affected users
            try:
                sync_user_approver_status_for_workflow(
                    workflow_id, updated_by=current_user.get_display_name()
                )
            except Exception as e:
                print(
                    f"Warning: Could not sync approver status after step addition: {e}"
                )

            flash(f'✅ Step "{step.step_name}" added successfully!', "success")

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error adding step: {str(e)}", "error")

        return redirect(url_for("approval_workflow_edit", id=workflow_id))

    @app.route(
        "/approval-workflow/<int:workflow_id>/stage/<int:stage_id>/delete",
        methods=["POST"],
    )
    @login_required
    def approval_workflow_delete_stage(workflow_id, stage_id):
        """Delete stage from approval workflow"""
        workflow = RFPOApprovalWorkflow.query.get_or_404(workflow_id)
        stage = RFPOApprovalStage.query.get_or_404(stage_id)

        if stage.workflow_id != workflow.id:
            flash("❌ Stage does not belong to this workflow.", "error")
            return redirect(url_for("approval_workflow_edit", id=workflow_id))

        try:
            stage_name = stage.stage_name
            db.session.delete(stage)
            db.session.commit()

            flash(f'✅ Stage "{stage_name}" deleted successfully!', "success")

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error deleting stage: {str(e)}", "error")

        return redirect(url_for("approval_workflow_edit", id=workflow_id))

    @app.route(
        "/approval-workflow/<int:workflow_id>/stage/<int:stage_id>/step/<int:step_id>/delete",
        methods=["POST"],
    )
    @login_required
    def approval_workflow_delete_step(workflow_id, stage_id, step_id):
        """Delete step from approval stage"""
        workflow = RFPOApprovalWorkflow.query.get_or_404(workflow_id)
        stage = RFPOApprovalStage.query.get_or_404(stage_id)
        step = RFPOApprovalStep.query.get_or_404(step_id)

        if stage.workflow_id != workflow.id or step.stage_id != stage.id:
            flash("❌ Step does not belong to this workflow/stage.", "error")
            return redirect(url_for("approval_workflow_edit", id=workflow_id))

        try:
            step_name = step.step_name
            db.session.delete(step)
            db.session.commit()

            # Sync approver status for affected users
            try:
                sync_user_approver_status_for_workflow(
                    workflow_id, updated_by=current_user.get_display_name()
                )
            except Exception as e:
                print(
                    f"Warning: Could not sync approver status after step deletion: {e}"
                )

            flash(f'✅ Step "{step_name}" deleted successfully!', "success")

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error deleting step: {str(e)}", "error")

        return redirect(url_for("approval_workflow_edit", id=workflow_id))

    @app.route("/approval-workflow/<int:id>/delete", methods=["POST"])
    @login_required
    def approval_workflow_delete(id):
        """Delete approval workflow"""
        workflow = RFPOApprovalWorkflow.query.get_or_404(id)

        # Check if workflow has been used
        instance_count = RFPOApprovalInstance.query.filter_by(
            template_workflow_id=workflow.id
        ).count()
        if instance_count > 0:
            flash(
                f"❌ Cannot delete workflow: it has been used by {instance_count} RFPOs. Deactivate instead.",
                "error",
            )
            return redirect(url_for("approval_workflows"))

        try:
            workflow_name = workflow.name
            db.session.delete(workflow)
            db.session.commit()

            flash(
                f'✅ Approval workflow "{workflow_name}" deleted successfully!',
                "success",
            )

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error deleting workflow: {str(e)}", "error")

        return redirect(url_for("approval_workflows"))

    @app.route("/approval-workflow/<int:id>/activate", methods=["POST"])
    @login_required
    def approval_workflow_activate(id):
        """Activate approval workflow for its consortium"""
        workflow = RFPOApprovalWorkflow.query.get_or_404(id)

        try:
            workflow.activate()
            db.session.commit()

            # Sync approver status for affected users
            try:
                sync_user_approver_status_for_workflow(
                    workflow.id, updated_by=current_user.get_display_name()
                )
            except Exception as e:
                print(
                    f"Warning: Could not sync approver status after workflow activation: {e}"
                )

            flash(
                f'✅ Workflow "{workflow.name}" activated for {workflow.consortium_id}!',
                "success",
            )

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error activating workflow: {str(e)}", "error")

        return redirect(url_for("approval_workflows"))

    @app.route("/api/check-active-workflow/<workflow_type>/<entity_id>")
    @login_required
    def api_check_active_workflow(workflow_type, entity_id):
        """API endpoint to check if an entity already has an active workflow"""
        try:
            # Validate workflow type
            if workflow_type not in ["consortium", "team", "project"]:
                return jsonify({"error": "Invalid workflow type"}), 400

            # Find existing active workflow for this entity
            if workflow_type == "consortium":
                active_workflow = RFPOApprovalWorkflow.query.filter_by(
                    consortium_id=entity_id,
                    workflow_type="consortium",
                    is_template=True,
                    is_active=True,
                ).first()
                # Get entity info
                entity = Consortium.query.filter_by(consort_id=entity_id).first()
                entity_name = entity.name if entity else entity_id
            elif workflow_type == "team":
                active_workflow = RFPOApprovalWorkflow.query.filter_by(
                    team_id=int(entity_id),
                    workflow_type="team",
                    is_template=True,
                    is_active=True,
                ).first()
                # Get entity info
                entity = Team.query.get(int(entity_id))
                entity_name = entity.name if entity else f"Team {entity_id}"
            elif workflow_type == "project":
                active_workflow = RFPOApprovalWorkflow.query.filter_by(
                    project_id=entity_id,
                    workflow_type="project",
                    is_template=True,
                    is_active=True,
                ).first()
                # Get entity info
                entity = Project.query.filter_by(project_id=entity_id).first()
                entity_name = entity.name if entity else entity_id

            if active_workflow:
                return jsonify(
                    {
                        "has_active_workflow": True,
                        "entity_name": entity_name,
                        "workflow_type": workflow_type,
                        "active_workflow_id": active_workflow.workflow_id,
                        "active_workflow_name": active_workflow.name,
                    }
                )
            else:
                return jsonify(
                    {
                        "has_active_workflow": False,
                        "entity_name": entity_name,
                        "workflow_type": workflow_type,
                    }
                )

        except Exception as e:
            return jsonify({"error": str(e), "has_active_workflow": False}), 500

    @app.route("/api/approval-stage/<int:stage_id>")
    @login_required
    def api_get_approval_stage(stage_id):
        """API endpoint to get approval stage data for editing"""
        stage = RFPOApprovalStage.query.get_or_404(stage_id)
        return jsonify(stage.to_dict())

    @app.route(
        "/approval-workflow/<int:workflow_id>/stage/<int:stage_id>/edit",
        methods=["POST"],
    )
    @login_required
    def approval_workflow_edit_stage(workflow_id, stage_id):
        """Edit approval stage"""
        workflow = RFPOApprovalWorkflow.query.get_or_404(workflow_id)
        stage = RFPOApprovalStage.query.get_or_404(stage_id)

        if stage.workflow_id != workflow.id:
            flash("❌ Stage does not belong to this workflow.", "error")
            return redirect(url_for("approval_workflow_edit", id=workflow_id))

        try:
            # Get budget bracket info (case-insensitive type + robust parsing)
            bracket_key = request.form.get("budget_bracket_key")
            bracket_item = List.get_item_ci("RFPO_BRACK", bracket_key)
            bracket_amount = (
                _parse_budget_amount(bracket_item.value) if bracket_item else 0.00
            )

            # Generate stage name from budget bracket
            stage_name = (
                f"Up to ${bracket_amount:,.0f}"
                if bracket_amount > 0
                else f"Budget Bracket {bracket_key}"
            )

            # Update stage with new values
            stage.budget_bracket_key = bracket_key
            stage.budget_bracket_amount = bracket_amount
            stage.stage_name = stage_name
            stage.description = request.form.get("description")

            # Handle required document types from dual-list picker
            doc_types_str = request.form.get("required_document_types", "")
            if doc_types_str:
                doc_types = [
                    dt.strip() for dt in doc_types_str.split(",") if dt.strip()
                ]
                stage.set_required_document_types(doc_types)
            else:
                stage.set_required_document_types([])

            # Keep defaults for hidden fields
            stage.requires_all_steps = True
            stage.is_parallel = False

            db.session.commit()

            flash(f'✅ Stage "{stage.stage_name}" updated successfully!', "success")

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error updating stage: {str(e)}", "error")

        return redirect(url_for("approval_workflow_edit", id=workflow_id))

    @app.route("/api/approval-workflow/<int:workflow_id>/available-budget-brackets")
    @login_required
    def api_get_available_budget_brackets(workflow_id):
        """API endpoint to get budget brackets not yet used in this workflow"""
        workflow = RFPOApprovalWorkflow.query.get_or_404(workflow_id)

        try:
            # Get all budget brackets (case-insensitive)
            all_brackets = List.get_by_type_ci("RFPO_BRACK")

            # Get used budget bracket keys in this workflow
            used_bracket_keys = [stage.budget_bracket_key for stage in workflow.stages]

            # Filter out used brackets
            available_brackets = []
            for bracket in all_brackets:
                if bracket.key in used_bracket_keys:
                    continue
                amount = _parse_budget_amount(bracket.value)
                available_brackets.append(
                    {
                        "key": bracket.key,
                        "value": bracket.value,
                        "amount": amount,
                    }
                )

            return jsonify({"success": True, "brackets": available_brackets})

        except Exception as e:
            return jsonify({"success": False, "error": str(e), "brackets": []}), 500

    @app.route(
        "/api/approval-workflow/<int:workflow_id>/available-budget-brackets/<exclude_stage_id>"
    )
    @login_required
    def api_get_available_budget_brackets_for_edit(workflow_id, exclude_stage_id):
        """API endpoint to get budget brackets available for editing (excluding current stage)"""
        workflow = RFPOApprovalWorkflow.query.get_or_404(workflow_id)

        try:
            # Get all budget brackets (case-insensitive)
            all_brackets = List.get_by_type_ci("RFPO_BRACK")

            # Get used budget bracket keys in this workflow, excluding the stage being edited
            used_bracket_keys = [
                stage.budget_bracket_key
                for stage in workflow.stages
                if str(stage.id) != str(exclude_stage_id)
            ]

            # Filter out used brackets (but allow current stage's bracket)
            available_brackets = []
            for bracket in all_brackets:
                if bracket.key in used_bracket_keys:
                    continue
                amount = _parse_budget_amount(bracket.value)
                available_brackets.append(
                    {
                        "key": bracket.key,
                        "value": bracket.value,
                        "amount": amount,
                    }
                )

            return jsonify({"success": True, "brackets": available_brackets})

        except Exception as e:
            return jsonify({"success": False, "error": str(e), "brackets": []}), 500

    @app.route(
        "/api/approval-workflow/<int:workflow_id>/stage/<int:stage_id>/reorder-steps",
        methods=["POST"],
    )
    @login_required
    def api_reorder_approval_steps(workflow_id, stage_id):
        """API endpoint to reorder approval steps within a stage"""
        workflow = RFPOApprovalWorkflow.query.get_or_404(workflow_id)
        stage = RFPOApprovalStage.query.get_or_404(stage_id)

        if stage.workflow_id != workflow.id:
            return (
                jsonify(
                    {"success": False, "error": "Stage does not belong to workflow"}
                ),
                400,
            )

        try:
            data = request.get_json()
            step_ids = data.get("step_ids", [])

            if not step_ids:
                return jsonify({"success": False, "error": "No step IDs provided"}), 400

            # First, set all step orders to negative values to avoid constraint conflicts
            # This is a common technique to handle unique constraint reordering
            steps_to_reorder = []
            for step_id in step_ids:
                step = RFPOApprovalStep.query.filter_by(
                    id=step_id, stage_id=stage.id
                ).first()
                if step:
                    step.step_order = -int(
                        step_id
                    )  # Temporarily set to negative unique value
                    steps_to_reorder.append(step)

            # Flush to apply the negative values
            db.session.flush()

            # Now update with the correct positive order values
            for new_order, step in enumerate(steps_to_reorder, 1):
                step.step_order = new_order

            db.session.commit()

            return jsonify(
                {
                    "success": True,
                    "message": f"Reordered {len(step_ids)} steps successfully",
                }
            )

        except Exception as e:
            db.session.rollback()
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/approval-step/<int:step_id>")
    @login_required
    def api_get_approval_step(step_id):
        """API endpoint to get approval step data for editing"""
        step = RFPOApprovalStep.query.get_or_404(step_id)
        return jsonify(step.to_dict())

    @app.route(
        "/approval-workflow/<int:workflow_id>/stage/<int:stage_id>/step/<int:step_id>/edit",
        methods=["POST"],
    )
    @login_required
    def approval_workflow_edit_step(workflow_id, stage_id, step_id):
        """Edit approval step"""
        workflow = RFPOApprovalWorkflow.query.get_or_404(workflow_id)
        stage = RFPOApprovalStage.query.get_or_404(stage_id)
        step = RFPOApprovalStep.query.get_or_404(step_id)

        if stage.workflow_id != workflow.id or step.stage_id != stage.id:
            flash("❌ Step does not belong to this workflow/stage.", "error")
            return redirect(url_for("approval_workflow_edit", id=workflow_id))

        try:
            # Get approval type info
            approval_key = request.form.get("approval_type_key")
            approval_item = List.get_item_ci("RFPO_APPRO", approval_key)
            approval_name = approval_item.value if approval_item else approval_key

            # Update step with new values
            step.approval_type_key = approval_key
            step.approval_type_name = approval_name
            step.step_name = approval_name  # Use approval type name as step name
            step.description = request.form.get("description")
            step.primary_approver_id = request.form.get("primary_approver_id")
            step.backup_approver_id = request.form.get("backup_approver_id") or None

            # Keep defaults for hidden fields
            step.is_required = True
            step.timeout_days = 0
            step.auto_escalate = False

            db.session.commit()

            # Sync approver status for affected users
            try:
                sync_user_approver_status_for_workflow(
                    workflow_id, updated_by=current_user.get_display_name()
                )
            except Exception as e:
                print(f"Warning: Could not sync approver status after step edit: {e}")

            flash(f'✅ Step "{step.step_name}" updated successfully!', "success")

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error updating step: {str(e)}", "error")

        return redirect(url_for("approval_workflow_edit", id=workflow_id))

    @app.route("/api/fix-approval-instance-status/<int:instance_id>", methods=["POST"])
    @login_required
    def api_fix_approval_instance_status(instance_id):
        """Fix approval instance status based on completed actions"""
        try:
            instance = RFPOApprovalInstance.query.get_or_404(instance_id)

            # Check current completion status
            completion_status = instance.check_completion_status()

            if completion_status:
                old_status = instance.overall_status
                instance.overall_status = completion_status
                if not instance.completed_at:
                    instance.completed_at = datetime.utcnow()
                instance.updated_at = datetime.utcnow()

                db.session.commit()

                return jsonify(
                    {
                        "success": True,
                        "message": f'Instance status updated from "{old_status}" to "{completion_status}"',
                        "old_status": old_status,
                        "new_status": completion_status,
                        "completed_at": (
                            instance.completed_at.isoformat()
                            if instance.completed_at
                            else None
                        ),
                    }
                )
            else:
                return jsonify(
                    {
                        "success": True,
                        "message": "Instance status is correct - workflow still in progress",
                        "current_status": instance.overall_status,
                    }
                )

        except Exception as e:
            db.session.rollback()
            return jsonify({"success": False, "message": str(e)}), 500

    @app.route("/api/sync-all-approver-status", methods=["POST"])
    @login_required
    def api_sync_all_approver_status():
        """Sync approver status for all users (admin panel utility)"""
        try:
            updated_count = sync_all_users_approver_status(
                updated_by=current_user.get_display_name()
            )

            return jsonify(
                {
                    "success": True,
                    "message": f"Synced approver status for {updated_count} users",
                    "updated_count": updated_count,
                }
            )

        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

    # RFPO Approval Instance Management routes
    @app.route("/approval-instances")
    @login_required
    def approval_instances():
        """List all RFPO approval instances and draft RFPOs ready for approval"""
        # Get existing approval instances
        instances = RFPOApprovalInstance.query.order_by(
            desc(RFPOApprovalInstance.created_at)
        ).all()

        # Get draft RFPOs that don't have approval instances yet
        draft_rfpos = (
            RFPO.query.filter(
                RFPO.status == "Draft",
                ~RFPO.id.in_(db.session.query(RFPOApprovalInstance.rfpo_id)),
            )
            .order_by(desc(RFPO.created_at))
            .all()
        )

        # Create virtual instances for draft RFPOs
        virtual_instances = []
        for rfpo in draft_rfpos:
            # Find applicable workflow (hierarchy: Project -> Team -> Consortium)
            applicable_workflow = get_applicable_workflow(rfpo)

            if applicable_workflow:
                # Get all applicable workflows for comprehensive display
                all_workflows = get_applicable_workflows(rfpo)
                workflow_summary = (
                    f"Multi-Phase ({len(all_workflows)} phases)"
                    if len(all_workflows) > 1
                    else applicable_workflow.name
                )

                virtual_instance = type(
                    "VirtualInstance",
                    (),
                    {
                        "id": f"draft_{rfpo.id}",
                        "instance_id": f"DRAFT-{rfpo.id}",
                        "rfpo": rfpo,
                        "rfpo_title": rfpo.title,
                        "rfpo_total": rfpo.total_amount or 0.00,
                        "workflow_name": workflow_summary,
                        "workflow_version": applicable_workflow.version,
                        "current_stage_order": None,
                        "current_step_order": None,
                        "overall_status": "draft",
                        "submitted_at": None,
                        "completed_at": None,
                        "created_at": rfpo.created_at,
                        "is_virtual": True,
                        "applicable_workflow": applicable_workflow,
                        "pending_actions_count": 0,
                        "completed_actions_count": 0,
                    },
                )()
                virtual_instances.append(virtual_instance)

        # Add RFPO info to real instances
        for instance in instances:
            if instance.rfpo:
                instance.rfpo_title = instance.rfpo.title
                instance.rfpo_total = instance.rfpo.total_amount
            else:
                instance.rfpo_title = f"RFPO #{instance.rfpo_id}"
                instance.rfpo_total = 0.00
            instance.is_virtual = False

            # Add action counts using the model methods
            instance.pending_actions_count = len(instance.get_pending_actions())
            instance.completed_actions_count = len(instance.get_completed_actions())

        # Combine and sort all instances
        all_instances = list(instances) + virtual_instances
        all_instances.sort(key=lambda x: x.created_at, reverse=True)

        return render_template("admin/approval_instances.html", instances=all_instances)

    @app.route("/approval-instance/<int:id>/view")
    @login_required
    def approval_instance_view(id):
        """View detailed approval instance with actions"""
        instance = RFPOApprovalInstance.query.get_or_404(id)

        # Get RFPO and related data
        rfpo = instance.rfpo
        if rfpo:
            project = Project.query.filter_by(project_id=rfpo.project_id).first()
            consortium = Consortium.query.filter_by(
                consort_id=rfpo.consortium_id
            ).first()
        else:
            project = None
            consortium = None

        return render_template(
            "admin/approval_instance_view.html",
            instance=instance,
            rfpo=rfpo,
            project=project,
            consortium=consortium,
        )

    @app.route(
        "/approval-instance/<int:instance_id>/action/<int:action_id>/approve",
        methods=["POST"],
    )
    @login_required
    def approval_action_approve(instance_id, action_id):
        """Complete an approval action (approve/conditional/refuse)"""
        instance = RFPOApprovalInstance.query.get_or_404(instance_id)
        action = RFPOApprovalAction.query.get_or_404(action_id)

        if action.instance_id != instance.id:
            flash("❌ Action does not belong to this instance.", "error")
            return redirect(url_for("approval_instance_view", id=instance_id))

        # Check if current user can take this action
        if (
            action.approver_id != current_user.record_id
            and not current_user.is_super_admin()
        ):
            flash("❌ You are not authorized to take this action.", "error")
            return redirect(url_for("approval_instance_view", id=instance_id))

        try:
            status = request.form.get("status")  # approved or refused
            comments = request.form.get("comments")

            # Validate status
            if status not in ["approved", "refused"]:
                flash("❌ Invalid action status.", "error")
                return redirect(url_for("approval_instance_view", id=instance_id))

            # Complete the action
            action.complete_action(status, comments, None, current_user.record_id)

            # Update instance status based on action result
            if status == "refused":
                # Any rejection immediately completes the workflow as refused
                instance.overall_status = "refused"
                instance.completed_at = datetime.utcnow()

                # Update RFPO status to refused
                if instance.rfpo:
                    instance.rfpo.status = "Refused"
                    instance.rfpo.updated_by = current_user.get_display_name()
            else:
                # For approvals, advance workflow and check for completion
                instance.advance_to_next_step()

                # If workflow is now complete and approved, update RFPO status
                if instance.overall_status == "approved" and instance.rfpo:
                    instance.rfpo.status = "Approved"
                    instance.rfpo.updated_by = current_user.get_display_name()

            instance.updated_at = datetime.utcnow()

            db.session.commit()

            flash(f"✅ Action {status} successfully!", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error processing action: {str(e)}", "error")

        return redirect(url_for("approval_instance_view", id=instance_id))

    @app.route("/approval-instance/<int:id>/delete", methods=["POST"])
    @login_required
    def approval_instance_delete(id):
        """Delete approval instance (admin only)"""
        instance = RFPOApprovalInstance.query.get_or_404(id)

        try:
            instance_id = instance.instance_id

            # Reset RFPO status if it was set by this approval workflow
            if instance.rfpo and instance.rfpo.status in ["Approved", "Refused"]:
                instance.rfpo.status = "Draft"
                instance.rfpo.updated_by = current_user.get_display_name()

            # Delete the approval instance (actions will be cascade deleted)
            db.session.delete(instance)
            db.session.commit()

            msg = f'✅ Approval instance "{instance_id}" deleted successfully!'
            flash(msg + " RFPO reset to Draft status.", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error deleting approval instance: {str(e)}", "error")

        return redirect(url_for("approval_instances"))

    @app.route("/api/rfpo/<int:rfpo_id>/test-approval")
    @login_required
    def api_test_approval(rfpo_id):
        """Test RFPO against approval workflow requirements"""
        rfpo = RFPO.query.get_or_404(rfpo_id)

        try:
            validation_result = validate_rfpo_for_approval(rfpo)
            return jsonify({"success": True, "validation": validation_result})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/rfpo/<int:rfpo_id>/submit-approval", methods=["POST"])
    @login_required
    def api_submit_approval(rfpo_id):
        """Submit RFPO for approval workflow"""
        rfpo = RFPO.query.get_or_404(rfpo_id)

        try:
            # Validate RFPO first
            validation_result = validate_rfpo_for_approval(rfpo)
            if not validation_result["is_valid"]:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "RFPO validation failed",
                            "validation": validation_result,
                        }
                    ),
                    400,
                )

            # Check if RFPO already has an approval instance
            existing_instance = RFPOApprovalInstance.query.filter_by(
                rfpo_id=rfpo.id
            ).first()
            if existing_instance:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "RFPO already has an active approval workflow",
                        }
                    ),
                    400,
                )

            # Find all applicable workflows (sequential phases)
            applicable_workflows = get_applicable_workflows(rfpo)
            if not applicable_workflows:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "No active approval workflows found for this RFPO",
                        }
                    ),
                    400,
                )

            # Create approval instance for multi-phase workflow
            instance_id = generate_next_id(
                RFPOApprovalInstance, "instance_id", "INST-", 8
            )

            # Create comprehensive workflow snapshot for all phases
            workflow_snapshot = {
                "total_phases": len(applicable_workflows),
                "current_phase": 1,
                "phases": [],
            }

            # Process each workflow phase
            first_workflow = None
            first_stage = None
            all_actions = []

            # Use timestamp-based action ID generation to ensure uniqueness
            # Removed unused 'time' import; using datetime-based timestamps

            action_id_counter = 0

            for workflow_type, workflow, phase_number in applicable_workflows:
                if phase_number == 1:
                    first_workflow = workflow

                # Determine stage for this workflow
                stage = determine_rfpo_stage(rfpo, workflow)
                if not stage:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": (
                                    "No appropriate approval stage found for "
                                    f"Phase {phase_number} ({workflow_type}) workflow"
                                ),
                            }
                        ),
                        400,
                    )

                if phase_number == 1:
                    first_stage = stage

                # Create phase snapshot
                phase_snapshot = {
                    "phase_number": phase_number,
                    "workflow_type": workflow_type,
                    "workflow_id": workflow.workflow_id,
                    "workflow_name": workflow.name,
                    "workflow_version": workflow.version,
                    "entity_name": workflow.get_entity_name(),
                    "stage": {
                        "stage_id": stage.stage_id,
                        "stage_name": stage.stage_name,
                        "stage_order": stage.stage_order,
                        "budget_bracket_amount": float(stage.budget_bracket_amount),
                        "required_document_types": stage.get_required_document_types(),
                        "steps": [],
                    },
                }

                # Add steps for this phase
                for step in stage.steps:
                    step_snapshot = {
                        "step_id": step.step_id,
                        "step_name": step.step_name,
                        "step_order": step.step_order,
                        "approval_type_key": step.approval_type_key,
                        "approval_type_name": step.approval_type_name,
                        "primary_approver_id": step.primary_approver_id,
                        "backup_approver_id": step.backup_approver_id,
                        "is_required": step.is_required,
                    }
                    phase_snapshot["stage"]["steps"].append(step_snapshot)

                    # Create actions for Phase 1 only (others will be created when phases advance)
                    if phase_number == 1:
                        # Generate unique action ID using timestamp + counter
                        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                        action_id_counter += 1
                        action_id = f"ACT-{timestamp}-{action_id_counter:03d}"

                        primary_approver = User.query.filter_by(
                            record_id=step.primary_approver_id, active=True
                        ).first()

                        action = RFPOApprovalAction(
                            action_id=action_id,
                            stage_order=stage.stage_order,
                            step_order=step.step_order,
                            stage_name=stage.stage_name,
                            step_name=step.step_name,
                            approval_type_key=step.approval_type_key,
                            approver_id=step.primary_approver_id,
                            approver_name=(
                                primary_approver.get_display_name()
                                if primary_approver
                                else "Unknown User"
                            ),
                            status="pending",
                        )
                        all_actions.append(action)

                workflow_snapshot["phases"].append(phase_snapshot)

            # Create approval instance starting with Phase 1
            approval_instance = RFPOApprovalInstance(
                instance_id=instance_id,
                rfpo_id=rfpo.id,
                template_workflow_id=first_workflow.id,
                workflow_name=f"Multi-Phase Approval ({len(applicable_workflows)} phases)",
                workflow_version=first_workflow.version,
                consortium_id=rfpo.consortium_id,
                current_stage_order=first_stage.stage_order,
                current_step_order=1,
                overall_status="waiting",
                submitted_at=datetime.utcnow(),
                created_by=current_user.get_display_name(),
            )

            approval_instance.set_instance_data(workflow_snapshot)

            # Save everything
            db.session.add(approval_instance)
            db.session.flush()  # Get the instance ID

            for action in all_actions:
                action.instance_id = approval_instance.id
                db.session.add(action)

            # Update RFPO status
            rfpo.status = "Submitted"
            rfpo.updated_by = current_user.get_display_name()

            db.session.commit()

            return jsonify(
                {
                    "success": True,
                    "message": f"RFPO submitted for {len(applicable_workflows)}-phase approval process",
                    "instance_id": approval_instance.instance_id,
                    "total_phases": len(applicable_workflows),
                    "first_stage_name": first_stage.stage_name,
                    "first_phase_steps": len(all_actions),
                }
            )

        except Exception as e:
            db.session.rollback()
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"Error submitting RFPO for approval: {str(e)}",
                    }
                ),
                500,
            )

    # API endpoints for quick data
    @app.route("/api/stats")
    @login_required
    def api_stats():
        """Get dashboard statistics"""
        stats = {
            "consortiums": Consortium.query.filter_by(active=True).count(),
            "teams": Team.query.filter_by(active=True).count(),
            "rfpos": RFPO.query.count(),
            "users": User.query.filter_by(active=True).count(),
            "vendors": Vendor.query.filter_by(active=True).count(),
            "projects": Project.query.filter_by(active=True).count(),
            "uploaded_files": UploadedFile.query.count(),
            "approval_workflows": RFPOApprovalWorkflow.query.filter_by(
                is_template=True, is_active=True
            ).count(),
            "approval_instances": RFPOApprovalInstance.query.count(),
            "pending_approvals": RFPOApprovalAction.query.filter_by(
                status="pending"
            ).count(),
        }
        return jsonify(stats)

    @app.route("/api/users")
    @login_required
    def api_users():
        """Get all active users for dropdowns and selection"""
        users = User.query.filter_by(active=True).all()
        user_data = []
        for user in users:
            user_data.append(
                {
                    "id": user.record_id,
                    "name": user.get_display_name(),
                    "email": user.email,
                    "company": user.company or "N/A",
                }
            )
        return jsonify(user_data)

    @app.route("/api/consortiums")
    @login_required
    def api_consortiums():
        """Get all active consortiums for dropdowns"""
        consortiums = Consortium.query.filter_by(active=True).all()
        consortium_data = []
        for consortium in consortiums:
            consortium_data.append(
                {
                    "id": consortium.consort_id,
                    "name": consortium.name,
                    "abbrev": consortium.abbrev,
                }
            )
        return jsonify(consortium_data)

    @app.route("/api/projects/<consortium_id>")
    @login_required
    def api_projects_for_consortium(consortium_id):
        """Get projects for a specific consortium"""
        projects = Project.query.filter(
            Project.consortium_ids.like(f"%{consortium_id}%"), Project.active.is_(True)
        ).all()

        project_data = []
        for project in projects:
            project_data.append(
                {
                    "id": project.project_id,
                    "ref": project.ref,
                    "name": project.name,
                    "description": project.description,
                    "gov_funded": project.gov_funded,
                    "uni_project": project.uni_project,
                }
            )
        return jsonify(project_data)

    @app.route("/api/teams")
    @login_required
    def api_teams():
        """Get all active teams for workflows"""
        teams = Team.query.filter_by(active=True).all()
        team_data = []
        for team in teams:
            # Get consortium info if available
            consortium_name = None
            if team.consortium_consort_id:
                consortium = Consortium.query.filter_by(
                    consort_id=team.consortium_consort_id
                ).first()
                consortium_name = (
                    consortium.name if consortium else team.consortium_consort_id
                )

            team_data.append(
                {
                    "id": team.id,
                    "record_id": team.record_id,
                    "name": team.name,
                    "abbrev": team.abbrev,
                    "description": team.description,
                    "consortium_name": consortium_name,
                }
            )
        return jsonify(team_data)

    @app.route("/api/projects")
    @login_required
    def api_projects():
        """Get all active projects for workflows"""
        projects = Project.query.filter_by(active=True).all()
        project_data = []
        for project in projects:
            # Get consortium info
            consortium_names = []
            consortium_ids = project.get_consortium_ids()
            for consortium_id in consortium_ids:
                consortium = Consortium.query.filter_by(
                    consort_id=consortium_id
                ).first()
                if consortium:
                    consortium_names.append(consortium.name)

            project_data.append(
                {
                    "id": project.project_id,
                    "ref": project.ref,
                    "name": project.name,
                    "description": project.description,
                    "gov_funded": project.gov_funded,
                    "uni_project": project.uni_project,
                    "consortium_names": consortium_names,
                }
            )
        return jsonify(project_data)

    @app.route("/api/vendor-sites/<int:vendor_id>")
    @login_required
    def api_vendor_sites(vendor_id):
        """Get sites for a specific vendor, including vendor's primary contact"""
        vendor = Vendor.query.get_or_404(vendor_id)
        site_data = []

        # Add vendor's primary contact as first option if it has contact info
        if vendor.contact_name:
            site_data.append(
                {
                    "id": f"vendor_{vendor.id}",  # Special ID to indicate this is the vendor's primary contact
                    "contact_name": vendor.contact_name,
                    "contact_dept": vendor.contact_dept,
                    "contact_tel": vendor.contact_tel,
                    "contact_city": vendor.contact_city,
                    "contact_state": vendor.contact_state,
                    "full_address": vendor.get_full_contact_address(),
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
                    "full_address": site.get_full_contact_address(),
                    "is_primary": False,
                }
            )
        return jsonify(site_data)

    @app.route("/api/list-items/<list_type>")
    @login_required
    def api_list_items_by_type(list_type):
        """Get all items for a specific list type"""
        try:
            items = (
                List.query.filter_by(type=list_type, active=True)
                .order_by(List.key)
                .all()
            )
            item_data = []
            for item in items:
                item_data.append(
                    {
                        "id": item.id,
                        "list_id": item.list_id,
                        "key": item.key,
                        "value": item.value,
                        "created_at": (
                            item.created_at.isoformat() if item.created_at else None
                        ),
                    }
                )
            return jsonify(
                {
                    "success": True,
                    "items": item_data,
                    "count": len(item_data),
                    "type": list_type,
                }
            )
        except Exception as e:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": str(e),
                        "items": [],
                        "count": 0,
                        "type": list_type,
                    }
                ),
                400,
            )

    @app.route("/api/sync-approver-status/<int:user_id>", methods=["POST"])
    @login_required
    def api_sync_user_approver_status(user_id):
        """Sync approver status for a specific user (admin panel)"""
        try:
            user = User.query.get_or_404(user_id)
            status_changed = user.update_approver_status(
                updated_by=current_user.get_display_name()
            )

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
            return jsonify({"success": False, "message": str(e)}), 500

    @app.route("/api/user/<int:user_id>/permissions-mindmap")
    @login_required
    def api_user_permissions_mindmap(user_id):
        """Get comprehensive permissions mindmap for a specific user"""
        try:
            user = User.query.get_or_404(user_id)

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
                    "rfpo_count": RFPO.query.filter_by(team_id=team.id).count(),
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
                    # Count RFPOs in this consortium (through teams)
                    consortium_teams = Team.query.filter_by(
                        consortium_consort_id=consortium.consort_id
                    ).all()
                    consortium_rfpo_count = sum(
                        RFPO.query.filter_by(team_id=team.id).count()
                        for team in consortium_teams
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

            # Project access
            project_access = []
            all_projects = Project.query.all()
            accessible_project_ids = []

            for project in all_projects:
                viewer_users = project.get_rfpo_viewer_users()
                if user.record_id in viewer_users:
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
                        }
                    )
                    accessible_project_ids.append(project.project_id)

            # Calculate accessible RFPOs
            accessible_rfpos = []

            # 1. RFPOs from user's teams
            team_ids = [team["id"] for team in team_data]
            if team_ids:
                team_rfpos = RFPO.query.filter(RFPO.team_id.in_(team_ids)).all()
                accessible_rfpos.extend(team_rfpos)

            # 2. RFPOs from projects user has access to
            if accessible_project_ids:
                project_rfpos = RFPO.query.filter(
                    RFPO.project_id.in_(accessible_project_ids)
                ).all()
                accessible_rfpos.extend(project_rfpos)

            # Remove duplicates
            accessible_rfpos = list(
                {rfpo.id: rfpo for rfpo in accessible_rfpos}.values()
            )

            # Approval workflow access
            approval_access = []
            if user.is_rfpo_admin() or user.is_super_admin():
                approval_workflows = RFPOApprovalWorkflow.query.filter_by(
                    is_template=True, is_active=True
                ).count()
                approval_access.append(
                    {
                        "type": "admin_access",
                        "description": "All approval workflows (Admin access)",
                        "count": approval_workflows,
                    }
                )

            # Build mindmap structure
            mindmap = {
                "user": {
                    "id": user.id,
                    "record_id": user.record_id,
                    "email": user.email,
                    "display_name": user.get_display_name(),
                },
                "system_permissions": {
                    "permissions": system_permissions,
                    "is_super_admin": user.is_super_admin(),
                    "is_rfpo_admin": user.is_rfpo_admin(),
                    "is_rfpo_user": user.is_rfpo_user(),
                },
                "associations": {
                    "teams": {"count": len(team_data), "items": team_data},
                    "consortiums": {
                        "count": len(direct_consortium_access),
                        "items": direct_consortium_access,
                    },
                    "projects": {"count": len(project_access), "items": project_access},
                },
                "access_summary": {
                    "total_rfpos": len(accessible_rfpos),
                    "total_consortiums": len(accessible_consortium_ids),
                    "total_teams": len(team_data),
                    "total_projects": len(project_access),
                    "has_admin_access": user.is_rfpo_admin() or user.is_super_admin(),
                    "approval_workflows": approval_access,
                },
                "capabilities": {
                    "can_access_admin_panel": user.is_rfpo_admin()
                    or user.is_super_admin(),
                    "can_create_rfpos": len(team_data) > 0
                    or len(project_access) > 0
                    or user.is_super_admin(),
                    "can_approve_rfpos": user.is_rfpo_admin() or user.is_super_admin(),
                    "can_manage_users": user.is_super_admin(),
                    "can_manage_workflows": user.is_rfpo_admin()
                    or user.is_super_admin(),
                },
            }

            return jsonify({"success": True, "mindmap": mindmap})

        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    # PDF to Image conversion for positioning editor background
    @app.route("/api/pdf-template-image/<template_name>")
    def pdf_template_image(template_name):
        """Convert PDF template to image for background display"""
        print("🖼️ PDF Template Image Route Called:")
        print(f"  - template_name: {template_name}")

        try:
            import io
            import os

            from flask import Response

            # Try to import pdf2image, fall back to placeholder if not available
            try:
                from pdf2image import convert_from_path

                # Map template names to PDF files
                template_files = {"po_template": "po.pdf", "po_page2": "po_page2.pdf"}

                print(f"  - Available templates: {list(template_files.keys())}")

                if template_name not in template_files:
                    print(
                        f"❌ Template '{template_name}' not found in available templates"
                    )
                    return Response("Template not found", status=404)

                pdf_path = os.path.join(
                    app.root_path, "static", "po_files", template_files[template_name]
                )
                print(f"  - PDF path: {pdf_path}")
                print(f"  - PDF exists: {os.path.exists(pdf_path)}")

                if not os.path.exists(pdf_path):
                    return Response("PDF file not found", status=404)

                # Convert first page to image
                images = convert_from_path(pdf_path, first_page=1, last_page=1, dpi=150)

                if not images:
                    return Response("Failed to convert PDF", status=500)

                # Convert PIL Image to PNG bytes
                img_buffer = io.BytesIO()
                images[0].save(img_buffer, format="PNG")
                img_buffer.seek(0)

                return Response(
                    img_buffer.getvalue(),
                    mimetype="image/png",
                    headers={
                        "Cache-Control": "public, max-age=3600"
                    },  # Cache for 1 hour
                )

            except ImportError:
                # pdf2image not available, create a placeholder image
                from PIL import Image, ImageDraw, ImageFont

                # Create a white background with guidelines
                width, height = 612, 792  # Standard letter size in points
                img = Image.new("RGB", (width, height), "white")
                draw = ImageDraw.Draw(img)

                # Draw border
                draw.rectangle(
                    [0, 0, width - 1, height - 1], outline="#cccccc", width=2
                )

                # Draw grid lines every 50 points
                for x in range(0, width, 50):
                    draw.line([x, 0, x, height], fill="#eeeeee", width=1)
                for y in range(0, height, 50):
                    draw.line([0, y, width, y], fill="#eeeeee", width=1)

                # Add title
                try:
                    font = ImageFont.load_default()
                    draw.text(
                        (width // 2, height // 2),
                        f"PDF Template: {template_name}",
                        fill="#999999",
                        anchor="mm",
                        font=font,
                    )
                    draw.text(
                        (width // 2, height // 2 + 20),
                        "Install poppler-utils for PDF preview",
                        fill="#666666",
                        anchor="mm",
                        font=font,
                    )
                except Exception:
                    pass

                # Convert to PNG bytes
                img_buffer = io.BytesIO()
                img.save(img_buffer, format="PNG")
                img_buffer.seek(0)

                return Response(
                    img_buffer.getvalue(),
                    mimetype="image/png",
                    headers={
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Pragma": "no-cache",
                        "Expires": "0",
                    },
                )

        except Exception as e:
            print(f"Error generating template image: {e}")
            import traceback

            traceback.print_exc()
            return Response(f"Error generating template image: {str(e)}", status=500)

    # PDF Positioning Editor routes
    @app.route("/pdf-positioning")
    @login_required
    def pdf_positioning_list():
        """List PDF positioning configurations"""
        configs = PDFPositioning.query.order_by(
            PDFPositioning.consortium_id, PDFPositioning.template_name
        ).all()
        consortiums = Consortium.query.filter_by(active=True).all()

        # Add consortium info to each config
        for config in configs:
            config.consortium = Consortium.query.filter_by(
                consort_id=config.consortium_id
            ).first()

        return render_template(
            "admin/pdf_positioning_list.html", configs=configs, consortiums=consortiums
        )

    @app.route("/pdf-positioning/editor/<consortium_id>/<template_name>")
    @login_required
    def pdf_positioning_editor(consortium_id, template_name):
        """Visual PDF positioning editor"""
        print("🔍 PDF Editor Route Called:")
        print(f"  - consortium_id: {consortium_id}")
        print(f"  - template_name: {template_name}")

        # Debug: List all consortiums
        all_consortiums = Consortium.query.all()
        print("  - Available consortiums:")
        for c in all_consortiums:
            print(f"    * ID: {c.id}, consort_id: {c.consort_id}, name: {c.name}")

        consortium = Consortium.query.filter_by(consort_id=consortium_id).first()
        if not consortium:
            print(f"❌ No consortium found with consort_id='{consortium_id}'")
            return (
                (
                    f"No consortium found with consort_id='{consortium_id}'. "
                    f"Available: {[c.consort_id for c in all_consortiums]}"
                ),
                404,
            )

        print(f"✅ Found consortium: {consortium.name}")

        # Get existing positioning config or create default
        config = PDFPositioning.query.filter_by(
            consortium_id=consortium_id, template_name=template_name, active=True
        ).first()

        if not config:
            # Create default configuration with standard PDF fields
            config = PDFPositioning(
                consortium_id=consortium_id,
                template_name=template_name,
                created_by=current_user.get_display_name(),
            )

            # Set default positions for common PDF fields
            default_fields = {
                "consortium_logo": {
                    "x": 50,
                    "y": 750,
                    "width": 80,
                    "height": 40,
                    "visible": True,
                },
                "po_number": {
                    "x": 470,
                    "y": 710,
                    "font_size": 10,
                    "font_weight": "bold",
                    "visible": True,
                },
                "po_date": {
                    "x": 470,
                    "y": 695,
                    "font_size": 9,
                    "font_weight": "normal",
                    "visible": True,
                },
                "vendor_company": {
                    "x": 60,
                    "y": 600,
                    "font_size": 9,
                    "font_weight": "normal",
                    "visible": True,
                },
                "vendor_contact": {
                    "x": 60,
                    "y": 585,
                    "font_size": 9,
                    "font_weight": "normal",
                    "visible": True,
                },
                "vendor_address": {
                    "x": 60,
                    "y": 570,
                    "font_size": 9,
                    "font_weight": "normal",
                    "visible": True,
                },
                "vendor_phone": {
                    "x": 60,
                    "y": 555,
                    "font_size": 9,
                    "font_weight": "normal",
                    "visible": True,
                },
                "ship_to_name": {
                    "x": 240,
                    "y": 600,
                    "font_size": 9,
                    "font_weight": "normal",
                    "visible": True,
                },
                "ship_to_address": {
                    "x": 240,
                    "y": 585,
                    "font_size": 9,
                    "font_weight": "normal",
                    "visible": True,
                },
                "delivery_type": {
                    "x": 410,
                    "y": 570,
                    "font_size": 9,
                    "font_weight": "normal",
                    "visible": True,
                },
                "delivery_payment": {
                    "x": 410,
                    "y": 545,
                    "font_size": 9,
                    "font_weight": "normal",
                    "visible": True,
                },
                "delivery_routing": {
                    "x": 410,
                    "y": 520,
                    "font_size": 9,
                    "font_weight": "normal",
                    "visible": True,
                },
                "payment_terms": {
                    "x": 60,
                    "y": 470,
                    "font_size": 9,
                    "font_weight": "normal",
                    "visible": True,
                },
                "project_info": {
                    "x": 240,
                    "y": 470,
                    "font_size": 9,
                    "font_weight": "normal",
                    "visible": True,
                },
                "delivery_date": {
                    "x": 410,
                    "y": 470,
                    "font_size": 9,
                    "font_weight": "normal",
                    "visible": True,
                },
                "government_agreement": {
                    "x": 240,
                    "y": 455,
                    "font_size": 8,
                    "font_weight": "normal",
                    "visible": True,
                },
                "requestor_info": {
                    "x": 60,
                    "y": 380,
                    "font_size": 9,
                    "font_weight": "normal",
                    "visible": True,
                },
                "invoice_address": {
                    "x": 410,
                    "y": 380,
                    "font_size": 9,
                    "font_weight": "normal",
                    "visible": True,
                },
                "line_items_header": {
                    "x": 60,
                    "y": 320,
                    "font_size": 8,
                    "font_weight": "bold",
                    "visible": True,
                },
                "subtotal": {
                    "x": 400,
                    "y": 200,
                    "font_size": 9,
                    "font_weight": "bold",
                    "visible": True,
                },
                "total": {
                    "x": 400,
                    "y": 180,
                    "font_size": 11,
                    "font_weight": "bold",
                    "visible": True,
                },
            }
            config.set_positioning_data(default_fields)
            db.session.add(config)
            db.session.commit()

        return render_template(
            "admin/pdf_positioning_editor.html",
            config=config,
            consortium=consortium,
            template_name=template_name,
        )

    @app.route(
        "/api/pdf-positioning/<int:config_id>", methods=["GET", "POST", "DELETE"]
    )
    @login_required
    def api_pdf_positioning(config_id):
        """API for saving/loading/deleting PDF positioning data"""
        config = PDFPositioning.query.get_or_404(config_id)

        if request.method == "GET":
            return jsonify(config.to_dict())

        elif request.method == "POST":
            try:
                data = request.get_json()
                if "positioning_data" in data:
                    config.set_positioning_data(data["positioning_data"])
                    config.updated_by = current_user.get_display_name()
                    db.session.commit()
                    return jsonify(
                        {"success": True, "message": "Positioning saved successfully"}
                    )
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 400

        elif request.method == "DELETE":
            try:
                db.session.delete(config)
                db.session.commit()
                return jsonify(
                    {"success": True, "message": "Configuration deleted successfully"}
                )
            except Exception as e:
                db.session.rollback()
                return jsonify({"success": False, "error": str(e)}), 400

        return jsonify({"success": False, "error": "Invalid request"}), 400

    @app.route("/api/pdf-positioning/preview/<int:config_id>")
    @login_required
    def api_pdf_positioning_preview(config_id):
        """Generate preview PDF with current positioning"""
        config = PDFPositioning.query.get_or_404(config_id)

        # Create a sample RFPO for preview
        try:
            # Get a sample RFPO or create dummy data
            sample_rfpo = RFPO.query.first()
            project = None
            consortium = None
            vendor = None
            vendor_site = None

            if sample_rfpo:
                # Get related data for real RFPO
                project = Project.query.filter_by(
                    project_id=sample_rfpo.project_id
                ).first()
                consortium = Consortium.query.filter_by(
                    consort_id=sample_rfpo.consortium_id
                ).first()
                vendor = (
                    Vendor.query.get(sample_rfpo.vendor_id)
                    if sample_rfpo.vendor_id
                    else None
                )
                vendor_site = (
                    VendorSite.query.get(sample_rfpo.vendor_site_id)
                    if sample_rfpo.vendor_site_id
                    else None
                )

            # Create dummy data if needed
            if not sample_rfpo or not project or not consortium:
                # Create dummy RFPO for preview
                from types import SimpleNamespace

                sample_rfpo = SimpleNamespace()
                sample_rfpo.rfpo_id = "PREVIEW-001"
                sample_rfpo.po_number = "PO-PREVIEW-001"
                sample_rfpo.po_date = datetime.now().strftime("%Y-%m-%d")
                sample_rfpo.vendor_id = 1
                sample_rfpo.vendor_site_id = None
                sample_rfpo.project_id = "PROJ-001"
                sample_rfpo.consortium_id = "CONSORT-001"
                sample_rfpo.ship_to_address = (
                    "123 Preview Street\nPreview City, ST 12345"
                )
                sample_rfpo.bill_to_address = "456 Billing Ave\nBilling City, ST 54321"
                sample_rfpo.total_amount = 15000.00
                sample_rfpo.status = "Draft"
                sample_rfpo.created_at = datetime.now()
                sample_rfpo.shipto_name = "Preview Shipping Contact"
                sample_rfpo.shipto_address = (
                    "123 Shipping Street\nShipping City, ST 12345"
                )
                sample_rfpo.delivery_type = "Standard Delivery"
                sample_rfpo.delivery_payment = "Prepaid"
                sample_rfpo.delivery_routing = "Direct"
                sample_rfpo.payment_terms = "Net 30"
                sample_rfpo.delivery_date = datetime.now()
                sample_rfpo.government_agreement_number = "USA-GOV-2024-001"
                sample_rfpo.line_items = []
                sample_rfpo.subtotal = 14000.00
                sample_rfpo.cost_share_amount = 1000.00
                sample_rfpo.requestor_id = "REQ001"
                sample_rfpo.requestor_tel = "(555) 987-6543"
                sample_rfpo.requestor_location = "Building A, Room 101"
                sample_rfpo.invoice_address = "456 Invoice Ave\nInvoice City, ST 54321"

                # Create dummy project
                project = SimpleNamespace()
                project.project_id = "PROJ-001"
                project.project_name = "Sample Preview Project"
                project.project_description = (
                    "This is a preview project for PDF positioning testing"
                )
                project.ref = "PROJ-REF-001"
                project.name = "Sample Preview Project"

                # Create dummy consortium
                consortium = SimpleNamespace()
                consortium.consort_id = "CONSORT-001"
                consortium.consort_name = "Preview Consortium"
                consortium.consort_description = "Sample consortium for preview"
                consortium.abbrev = "PREVIEW"
                # Try to use an actual consortium logo for preview if available
                real_consortium = Consortium.query.filter_by(
                    consort_id=config.consortium_id
                ).first()
                consortium.logo = (
                    real_consortium.logo
                    if real_consortium and real_consortium.logo
                    else None
                )

                # Create dummy vendor
                vendor = SimpleNamespace()
                vendor.vendor_id = 1
                vendor.vendor_name = "Preview Vendor Inc."
                vendor.company_name = "Preview Vendor Inc."
                vendor.vendor_address = "789 Vendor Blvd\nVendor City, ST 98765"
                vendor.contact_email = "contact@previewvendor.com"
                vendor.contact_phone = "(555) 123-4567"
                vendor.contact_name = "John Smith"
                vendor.contact_dept = "Sales Department"
                vendor.contact_tel = "(555) 123-4567"
                vendor.contact_fax = "(555) 123-4568"
                vendor.contact_address = "789 Vendor Blvd\nVendor City, ST 98765"
                vendor.contact_city = "Vendor City"
                vendor.contact_state = "ST"
                vendor.contact_zip = "98765"
                vendor.contact_country = "USA"

                # Create dummy vendor_site
                vendor_site = SimpleNamespace()
                vendor_site.vendor_site_id = 1
                vendor_site.vendor_id = 1
                vendor_site.site_name = "Main Office"
                vendor_site.site_address = "789 Vendor Blvd\nVendor City, ST 98765"
                vendor_site.contact_name = "Jane Doe"
                vendor_site.contact_dept = "Operations Department"
                vendor_site.contact_tel = "(555) 123-4569"
                vendor_site.contact_fax = "(555) 123-4570"
                vendor_site.contact_address = "789 Vendor Blvd\nVendor City, ST 98765"
                vendor_site.contact_city = "Vendor City"
                vendor_site.contact_state = "ST"
                vendor_site.contact_zip = "98765"
                vendor_site.contact_country = "USA"

            # Generate PDF with custom positioning
            pdf_generator = RFPOPDFGenerator(positioning_config=config)
            pdf_buffer = pdf_generator.generate_po_pdf(
                sample_rfpo, consortium, project, vendor, vendor_site
            )

            return Response(
                pdf_buffer.getvalue(),
                mimetype="application/pdf",
                headers={"Content-Disposition": 'inline; filename="preview.pdf"'},
            )

        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    return app


if __name__ == "__main__":
    app = create_app()

    with app.app_context():
        # Create tables if they don't exist
        db.create_all()

    print("🚀 Custom RFPO Admin Panel Starting...")
    print("=" * 60)
    print("📧 Default Login: admin@rfpo.com")
    print("🔑 Default Password: admin123")
    print("🌐 Admin Panel: http://localhost:5111/")
    print("=" * 60)
    print("✨ NO Flask-Admin - Custom built from scratch!")
    print("🎯 Direct database operations - no compatibility issues!")
    print("📝 JSON fields handled properly with transformations")
    print("⚠️  Running on port 5111 (main app uses 5000)")
    print("")

    app.run(debug=True, host="0.0.0.0", port=5111)
