"""
Admin-specific API Routes
Additional endpoints needed by the admin panel
"""

from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, User, Consortium, Project, Vendor, VendorSite, List, RFPOApprovalAction, RFPOApprovalInstance, RFPO
from utils import require_auth, require_admin, error_response

admin_api = Blueprint("admin_api", __name__, url_prefix="/api/admin")


# User Management Routes
@admin_api.route("/users", methods=["GET"])
@require_auth
@require_admin
def list_users():
    """List all users for admin panel"""
    try:
        users = User.query.all()
        return jsonify(
            {
                "success": True,
                "users": [
                    (
                        user.to_dict()
                        if hasattr(user, "to_dict")
                        else {
                            "id": user.id,
                            "record_id": user.record_id,
                            "fullname": user.fullname,
                            "email": user.email,
                            "active": user.active,
                            "permissions": user.get_permissions(),
                            "company": user.company,
                            "position": user.position,
                            "created_at": (
                                user.created_at.isoformat() if user.created_at else None
                            ),
                        }
                    )
                    for user in users
                ],
            }
        )
    except Exception as e:
        return error_response(e)


@admin_api.route("/users", methods=["POST"])
@require_auth
@require_admin
def create_user():
    """Create new user"""
    try:
        data = request.get_json()

        # Auto-generate record ID (simplified version)
        import uuid

        record_id = str(uuid.uuid4())[:8].upper()

        from werkzeug.security import generate_password_hash

        user = User(
            record_id=record_id,
            fullname=data.get("fullname", ""),
            email=data.get("email", ""),
            password_hash=generate_password_hash(data.get("password", "")),
            sex=data.get("sex", ""),
            company_code=data.get("company_code", ""),
            company=data.get("company", ""),
            position=data.get("position", ""),
            department=data.get("department", ""),
            active=data.get("active", True),
            created_at=datetime.utcnow(),
            created_by=request.current_user.email,
        )

        # Set permissions
        permissions = data.get("permissions", [])
        user.set_permissions(permissions)

        db.session.add(user)
        db.session.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "user": {
                        "id": user.id,
                        "record_id": user.record_id,
                        "fullname": user.fullname,
                        "email": user.email,
                    },
                }
            ),
            201,
        )

    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Email already exists"}), 400
    except Exception as e:
        db.session.rollback()
        return error_response(e)


# Consortium Management Routes
@admin_api.route("/consortiums", methods=["GET"])
@require_auth
def list_consortiums():
    """List all consortiums"""
    try:
        consortiums = Consortium.query.all()
        return jsonify(
            {
                "success": True,
                "consortiums": [
                    {
                        "id": c.id,
                        "consort_id": c.consort_id,
                        "name": c.name,
                        "abbrev": c.abbrev,
                        "logo": c.logo,
                        "created_at": (
                            c.created_at.isoformat() if c.created_at else None
                        ),
                    }
                    for c in consortiums
                ],
            }
        )
    except Exception as e:
        return error_response(e)


@admin_api.route("/consortiums", methods=["POST"])
@require_auth
@require_admin
def create_consortium():
    """Create new consortium"""
    try:
        data = request.get_json()

        # Auto-generate consortium ID
        import uuid

        consort_id = str(uuid.uuid4())[:8].upper()

        consortium = Consortium(
            consort_id=consort_id,
            name=data.get("name", ""),
            abbrev=data.get("abbrev", ""),
            logo=data.get("logo", ""),
            created_at=datetime.utcnow(),
            created_by=request.current_user.email,
        )

        db.session.add(consortium)
        db.session.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "consortium": {
                        "id": consortium.id,
                        "consort_id": consortium.consort_id,
                        "name": consortium.name,
                        "abbrev": consortium.abbrev,
                    },
                }
            ),
            201,
        )

    except IntegrityError:
        db.session.rollback()
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Consortium name or abbreviation already exists",
                }
            ),
            400,
        )
    except Exception as e:
        db.session.rollback()
        return error_response(e)


# Project Management Routes
@admin_api.route("/projects", methods=["GET"])
@require_auth
def list_projects():
    """List all projects"""
    try:
        projects = Project.query.all()
        return jsonify(
            {
                "success": True,
                "projects": [
                    {
                        "id": p.id,
                        "project_id": p.project_id,
                        "name": p.name,
                        "description": p.description,
                        "consortium_id": p.consortium_id,
                        "created_at": (
                            p.created_at.isoformat() if p.created_at else None
                        ),
                    }
                    for p in projects
                ],
            }
        )
    except Exception as e:
        return error_response(e)


# Vendor Management Routes
@admin_api.route("/vendors", methods=["GET"])
@require_auth
def list_vendors():
    """List all vendors"""
    try:
        vendors = Vendor.query.all()
        return jsonify(
            {
                "success": True,
                "vendors": [
                    {
                        "id": v.id,
                        "vendor_id": v.vendor_id,
                        "name": v.name,
                        "consortium_id": v.consortium_id,
                        "created_at": (
                            v.created_at.isoformat() if v.created_at else None
                        ),
                    }
                    for v in vendors
                ],
            }
        )
    except Exception as e:
        return error_response(e)


# Configuration Lists Routes
@admin_api.route("/lists", methods=["GET"])
@require_auth
def list_configuration_lists():
    """List all configuration lists"""
    try:
        lists = List.query.all()
        return jsonify(
            {
                "success": True,
                "lists": [
                    {
                        "id": l.id,
                        "list_type": l.list_type,
                        "value": l.value,
                        "display_text": l.display_text,
                        "sort_order": l.sort_order,
                        "active": l.active,
                    }
                    for l in lists
                ],
            }
        )
    except Exception as e:
        return error_response(e)


# Approval Reminder Routes
@admin_api.route("/approval-reminders", methods=["GET"])
@require_auth
@require_admin
def list_overdue_approvals():
    """List overdue pending approval actions with reminder status"""
    try:
        now = datetime.utcnow()
        overdue_actions = (
            db.session.query(RFPOApprovalAction)
            .join(RFPOApprovalInstance)
            .join(RFPO, RFPOApprovalInstance.rfpo_id == RFPO.id)
            .filter(
                RFPOApprovalAction.status == "pending",
                RFPOApprovalAction.due_date < now,
                RFPOApprovalInstance.overall_status == "waiting",
            )
            .order_by(RFPOApprovalAction.due_date.asc())
            .all()
        )

        results = []
        for action in overdue_actions:
            days_overdue = (now - action.due_date).days if action.due_date else 0
            rfpo = action.instance.rfpo if action.instance else None
            results.append({
                "id": action.id,
                "action_id": action.action_id,
                "rfpo_id": rfpo.rfpo_id if rfpo else None,
                "rfpo_db_id": rfpo.id if rfpo else None,
                "approver_name": action.approver_name,
                "step_name": action.step_name,
                "stage_name": action.stage_name,
                "due_date": action.due_date.isoformat() if action.due_date else None,
                "days_overdue": days_overdue,
                "reminder_count": action.reminder_count or 0,
                "last_reminder_sent_utc": (
                    action.last_reminder_sent_utc.isoformat()
                    if action.last_reminder_sent_utc else None
                ),
                "is_escalated": action.is_escalated,
                "escalated_at": (
                    action.escalated_at.isoformat() if action.escalated_at else None
                ),
            })

        return jsonify({
            "success": True,
            "overdue_actions": results,
            "total": len(results),
        })
    except Exception as e:
        return error_response(e)
