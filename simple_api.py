#!/usr/bin/env python3
"""
Simple RFPO API Server
Just Flask + Database connection - nothing fancy
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import check_password_hash
import jwt
from datetime import datetime, timedelta
import os

# Import our models
from models import (
    db,
    User,
    Team,
    RFPO,
    RFPOLineItem,
    Consortium,
    Project,
    Vendor,
    VendorSite,
)

# Import admin routes
import sys

sys.path.append("api")
try:
    from admin_routes import admin_api

    ADMIN_ROUTES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Admin routes not available: {e}")
    ADMIN_ROUTES_AVAILABLE = False

# User routes are handled directly in this file
USER_ROUTES_AVAILABLE = False

# Create Flask app with template folder
app = Flask(__name__, template_folder="templates")

# Configuration
app.config["SECRET_KEY"] = os.environ.get("API_SECRET_KEY", "simple-api-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", f'sqlite:///{os.path.abspath("instance/rfpo_admin.db")}'
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize database
db.init_app(app)

# Enable CORS
CORS(app)

# Register admin routes if available
if ADMIN_ROUTES_AVAILABLE:
    app.register_blueprint(admin_api)
    print("✅ Admin API routes registered")

# User routes are handled directly in this file (not as blueprint)

# JWT Secret
JWT_SECRET = "simple-jwt-secret"


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
        except:
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
    return jsonify({"status": "healthy", "service": "Simple RFPO API"})


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("username")  # Frontend sends as 'username' but it's email
    password = data.get("password")

    print(f"Login attempt: {email}")

    if not email or not password:
        return (
            jsonify({"success": False, "message": "Email and password required"}),
            400,
        )

    # Find user
    user = User.query.filter_by(email=email).first()

    print(f"User found: {user is not None}")
    if user:
        print(f"User active: {user.active}")

    if not user or not user.active:
        return jsonify({"success": False, "message": "User not found or inactive"}), 401

    # Check password
    if not check_password_hash(user.password_hash, password):
        print("Password check failed")
        return jsonify({"success": False, "message": "Invalid password"}), 401

    print("Login successful!")

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
    teams = Team.query.filter_by(active=True).all()
    return jsonify(
        {
            "success": True,
            "teams": [
                {
                    "id": t.id,
                    "name": t.name,
                    "abbrev": t.abbrev,
                    "description": t.description,
                }
                for t in teams
            ],
        }
    )


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
                    print(f"✅ Password change notification sent to {user.email}")
                else:
                    print(f"⚠️ Password change notification failed for {user.email}")
            except ImportError:
                print(
                    "⚠️ Email service not available - password change notification not sent"
                )
            except Exception as email_error:
                print(f"⚠️ Email notification error: {email_error}")
        except Exception as e:
            print(f"⚠️ Error sending password change notification: {e}")

        return jsonify({"success": True, "message": "Password changed successfully"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/users/approver-rfpos", methods=["GET"])
@require_auth
def get_approver_rfpos():
    """Get RFPOs where current user is an approver"""
    try:
        from models import (
            RFPOApprovalInstance,
            RFPOApprovalAction,
            Project,
            Consortium,
            Vendor,
        )

        user = request.current_user

        # Find RFPOs where user is an approver through approval actions
        user_actions = RFPOApprovalAction.query.filter_by(
            approver_id=user.record_id
        ).all()

        rfpo_data = []
        seen_rfpo_ids = set()

        for action in user_actions:
            if (
                action.instance
                and action.instance.rfpo
                and action.instance.rfpo.id not in seen_rfpo_ids
            ):
                rfpo = action.instance.rfpo
                instance = action.instance

                # Get related data
                project = Project.query.filter_by(project_id=rfpo.project_id).first()
                consortium = Consortium.query.filter_by(
                    consort_id=rfpo.consortium_id
                ).first()
                vendor = Vendor.query.get(rfpo.vendor_id) if rfpo.vendor_id else None

                # Get user's specific action for this RFPO
                user_action = action

                rfpo_info = {
                    "id": rfpo.id,
                    "rfpo_id": rfpo.rfpo_id,
                    "title": rfpo.title,
                    "description": rfpo.description,
                    "total_amount": float(rfpo.total_amount or 0),
                    "status": rfpo.status,
                    "created_at": (
                        rfpo.created_at.isoformat() if rfpo.created_at else None
                    ),
                    "created_by": rfpo.created_by,
                    # Project info
                    "project": (
                        {
                            "id": project.project_id if project else None,
                            "name": project.name if project else None,
                            "ref": project.ref if project else None,
                        }
                        if project
                        else None
                    ),
                    # Consortium info
                    "consortium": (
                        {
                            "id": consortium.consort_id if consortium else None,
                            "name": consortium.name if consortium else None,
                            "abbrev": consortium.abbrev if consortium else None,
                        }
                        if consortium
                        else None
                    ),
                    # Vendor info
                    "vendor": (
                        {
                            "id": vendor.id if vendor else None,
                            "company_name": vendor.company_name if vendor else None,
                        }
                        if vendor
                        else None
                    ),
                    # Approval info
                    "approval_instance": {
                        "instance_id": instance.instance_id,
                        "workflow_name": instance.workflow_name,
                        "overall_status": instance.overall_status,
                        "current_stage_order": instance.current_stage_order,
                        "current_step_order": instance.current_step_order,
                        "submitted_at": (
                            instance.submitted_at.isoformat()
                            if instance.submitted_at
                            else None
                        ),
                        "completed_at": (
                            instance.completed_at.isoformat()
                            if instance.completed_at
                            else None
                        ),
                    },
                    # User's specific action
                    "user_action": {
                        "action_id": user_action.action_id,
                        "step_name": user_action.step_name,
                        "stage_name": user_action.stage_name,
                        "status": user_action.status,
                        "assigned_at": (
                            user_action.assigned_at.isoformat()
                            if user_action.assigned_at
                            else None
                        ),
                        "completed_at": (
                            user_action.completed_at.isoformat()
                            if user_action.completed_at
                            else None
                        ),
                        "comments": user_action.comments,
                        "approval_type": user_action.approval_type_key,
                    },
                }

                rfpo_data.append(rfpo_info)
                seen_rfpo_ids.add(rfpo.id)

        # Categorize RFPOs by status for dashboard
        categorized_rfpos = {
            "pending": [
                r for r in rfpo_data if r["user_action"]["status"] == "pending"
            ],
            "approved": [
                r for r in rfpo_data if r["user_action"]["status"] == "approved"
            ],
            "rejected": [
                r for r in rfpo_data if r["user_action"]["status"] == "refused"
            ],
            "waiting": [
                r
                for r in rfpo_data
                if r["approval_instance"]["overall_status"] == "waiting"
                and r["user_action"]["status"] != "pending"
            ],
        }

        return jsonify(
            {
                "success": True,
                "rfpos": rfpo_data,
                "categorized": categorized_rfpos,
                "summary": {
                    "total": len(rfpo_data),
                    "pending": len(categorized_rfpos["pending"]),
                    "approved": len(categorized_rfpos["approved"]),
                    "rejected": len(categorized_rfpos["rejected"]),
                    "waiting": len(categorized_rfpos["waiting"]),
                },
            }
        )

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/users/approval-action/<action_id>", methods=["POST"])
@require_auth
def take_approval_action(action_id):
    """Take an approval action (approve/reject)"""
    try:
        from models import RFPOApprovalAction, RFPOApprovalInstance

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
        if status not in ["approved", "refused"]:
            return (
                jsonify(
                    {"success": False, "message": "Status must be approved or refused"}
                ),
                400,
            )

        comments = data.get("comments", "")

        # Complete the action
        action.complete_action(status, comments, None, user.record_id)

        # Update instance status
        instance = action.instance
        if status == "refused":
            instance.overall_status = "refused"
            instance.completed_at = datetime.utcnow()

            # Update RFPO status
            if instance.rfpo:
                instance.rfpo.status = "Refused"
                instance.rfpo.updated_by = user.get_display_name()
        else:
            # For approvals, advance workflow and check for completion
            instance.advance_to_next_step()

            # If workflow is now complete and approved, update RFPO status
            if instance.overall_status == "approved" and instance.rfpo:
                instance.rfpo.status = "Approved"
                instance.rfpo.updated_by = user.get_display_name()

        instance.updated_at = datetime.utcnow()
        db.session.commit()

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
        return jsonify({"success": False, "message": str(e)}), 500


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
        return jsonify({"success": False, "message": str(e)}), 500


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
        return jsonify({"success": False, "message": str(e)}), 500


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
        return jsonify({"success": False, "message": str(e)}), 500


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
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/users/permissions-summary")
@require_auth
def get_user_permissions_summary():
    """Get comprehensive permissions summary for current user"""
    try:
        from models import Team, Consortium, Project

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
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/rfpos")
@require_auth
def list_rfpos():
    """List RFPOs with permission filtering"""
    try:
        from models import Team, Project

        user = request.current_user

        # If user is super admin, they can see all RFPOs
        if user.is_super_admin():
            rfpos = RFPO.query.all()
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
                from models import RFPOApprovalAction

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
                    rfpos = RFPO.query.filter(db.or_(*filters)).all()
                else:
                    rfpos = RFPO.query.filter(filters[0]).all()
            else:
                # User has no access to any RFPOs
                rfpos = []

        return jsonify(
            {
                "success": True,
                "rfpos": [
                    {
                        "id": r.id,
                        "rfpo_id": r.rfpo_id,
                        "title": r.title,
                        "status": r.status,
                        "created_at": (
                            r.created_at.isoformat() if r.created_at else None
                        ),
                    }
                    for r in rfpos
                ],
                "total": len(rfpos),
                "page": 1,
                "pages": 1,
            }
        )

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/rfpos", methods=["POST"])
@require_auth
def create_rfpo():
    """Create new RFPO"""
    try:
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
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/rfpos/<int:rfpo_id>", methods=["GET"])
@require_auth
def get_rfpo(rfpo_id):
    """Get RFPO details"""
    try:
        from models import (
            Project,
            Consortium,
            Vendor,
            VendorSite,
            RFPOApprovalInstance,
            RFPOApprovalAction,
        )

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

        # Get approval information if user is an approver
        approval_data = None
        user_action = None

        if user.is_approver:
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

        return jsonify(
            {
                "success": True,
                "rfpo": rfpo.to_dict(),
                "approval_data": approval_data,
                "user_action": user_action,
                "files": files_data,
            }
        )

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/rfpos/<int:rfpo_id>", methods=["PUT"])
@require_auth
def update_rfpo(rfpo_id):
    """Update RFPO"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)
        data = request.get_json()

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
        return jsonify({"success": False, "message": str(e)}), 500


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
        from models import RFPOApprovalInstance

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
        return jsonify({"success": False, "message": str(e)}), 500


# Line Items API
@app.route("/api/rfpos/<int:rfpo_id>/line-items", methods=["POST"])
@require_auth
def add_line_item(rfpo_id):
    """Add line item to RFPO"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)
        data = request.get_json()

        # Check permissions
        user = request.current_user
        if not user.is_super_admin():
            has_access = False
            user_teams = user.get_teams()
            team_ids = [team.id for team in user_teams]
            if rfpo.team_id in team_ids:
                has_access = True

            if not has_access:
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
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/rfpos/<int:rfpo_id>/line-items/<int:line_item_id>", methods=["DELETE"])
@require_auth
def delete_line_item(rfpo_id, line_item_id):
    """Delete line item from RFPO"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)
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

        # Check permissions
        user = request.current_user
        if not user.is_super_admin():
            has_access = False
            user_teams = user.get_teams()
            team_ids = [team.id for team in user_teams]
            if rfpo.team_id in team_ids:
                has_access = True

            if not has_access:
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
        return jsonify({"success": False, "message": str(e)}), 500


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
        return jsonify({"success": False, "message": str(e)}), 500


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
        return jsonify({"success": False, "message": str(e)}), 500


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
        return jsonify({"success": False, "message": str(e)}), 500


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
        return jsonify({"success": False, "message": str(e)}), 500


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
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/rfpos/<int:rfpo_id>/rendered-view")
@require_auth
def get_rfpo_rendered_view(rfpo_id):
    """Get RFPO rendered HTML view for approvers (like admin panel)"""
    try:
        from models import Project, Consortium, Vendor, VendorSite
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
                from models import RFPOApprovalAction, RFPOApprovalInstance

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
        return jsonify({"success": False, "message": str(e)}), 500


if __name__ == "__main__":
    print("🚀 Starting Simple RFPO API")
    print(f"📂 Database: {app.config['SQLALCHEMY_DATABASE_URI']}")

    with app.app_context():
        print(f"👥 Users in database: {User.query.count()}")

    app.run(debug=False, host="0.0.0.0", port=5002)
