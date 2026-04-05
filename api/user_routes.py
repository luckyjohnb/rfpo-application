"""
User Profile API Routes
Endpoints for user profile management
"""

from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import sys
import os
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, RFPO, RFPOApprovalInstance, RFPOApprovalAction, Consortium,
)
from utils import require_auth

logger = logging.getLogger(__name__)

user_api = Blueprint("user_api", __name__, url_prefix="/api/users")


@user_api.route("/profile", methods=["GET"])
@require_auth
def get_user_profile():
    """Get current user's profile"""
    try:
        user = request.current_user
        return jsonify({"success": True, "user": user.to_dict()})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@user_api.route("/profile", methods=["PUT"])
@require_auth
def update_user_profile():
    """Update current user's profile"""
    try:
        user = request.current_user
        data = request.get_json()

        # Update allowed fields
        updatable_fields = [
            "fullname",
            "sex",
            "position",
            "company_code",
            "company",
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

        for field in updatable_fields:
            if field in data:
                setattr(user, field, data[field])

        # Update timestamp
        user.updated_at = datetime.utcnow()
        user.updated_by = user.email

        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": "Profile updated successfully",
                "user": user.to_dict(),
            }
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@user_api.route("/change-password", methods=["POST"])
@require_auth
def change_password():
    """Change user password"""
    try:
        user = request.current_user
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

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@user_api.route("/permissions-summary", methods=["GET"])
@require_auth
def get_user_permissions_summary():
    """Get comprehensive permissions summary for current user"""
    try:
        from models import Team, Consortium, Project, RFPO

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
                direct_consortium_access.append(
                    {
                        "consort_id": consortium.consort_id,
                        "name": consortium.name,
                        "abbrev": consortium.abbrev,
                        "access_type": access_type,
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
                project_access.append(
                    {
                        "project_id": project.project_id,
                        "name": project.name,
                        "ref": project.ref,
                        "consortium_ids": project.get_consortium_ids(),
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


@user_api.route("/approver-status", methods=["GET"])
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


@user_api.route("/sync-approver-status", methods=["POST"])
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


@user_api.route("/approver-rfpos", methods=["GET"])
@require_auth
def get_user_approver_rfpos():
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

        # Summary counts
        total_pending = len(all_actions)
        total_rfpos = len(rfpos_list)

        return jsonify({
            "success": True,
            "rfpos": rfpos_list,
            "summary": {
                "total": total_rfpos,
                "pending": total_pending,
            },
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Approver RFPOs error for user {request.current_user.record_id}: {e}", flush=True)
        return jsonify({"success": False, "message": str(e)}), 500


def _get_authorized_approver_ids_api(instance, action):
    """Return the set of user record_ids authorized to execute this action."""
    authorized = {action.approver_id}
    try:
        data = instance.get_instance_data()
        for phase in data.get("phases", []):
            stage = phase.get("stage", {})
            if stage.get("stage_order") == action.stage_order:
                for step in stage.get("steps", []):
                    if step.get("step_order") == action.step_order:
                        backup_id = step.get("backup_approver_id")
                        if backup_id:
                            authorized.add(backup_id)
                        break
                break
    except Exception:
        pass
    return authorized


def _create_next_sequential_action_api(instance, completed_action):
    """Create the next sequential action after a step is approved."""
    data = instance.get_instance_data()
    phases = data.get("phases", [])

    ordered_steps = []
    for phase in sorted(phases, key=lambda p: p.get("phase_number", 0)):
        stage = phase.get("stage", {})
        for step in sorted(stage.get("steps", []), key=lambda s: s.get("step_order", 0)):
            ordered_steps.append((
                phase.get("phase_number", 0),
                stage.get("stage_order", 0),
                stage.get("stage_name", ""),
                step,
            ))

    current_idx = None
    for idx, (phase_num, stage_ord, stage_name, step) in enumerate(ordered_steps):
        if (stage_ord == completed_action.stage_order
                and step.get("step_order") == completed_action.step_order):
            current_idx = idx
            break

    if current_idx is None or current_idx + 1 >= len(ordered_steps):
        return None

    next_phase, next_stage_order, next_stage_name, next_step = ordered_steps[current_idx + 1]

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    existing_count = RFPOApprovalAction.query.filter_by(
        instance_id=instance.id,
    ).count()
    action_id = f"ACT-{timestamp}-{existing_count + 1:03d}"

    primary_approver = User.query.filter_by(
        record_id=next_step.get("primary_approver_id"), active=True,
    ).first()

    new_action = RFPOApprovalAction(
        action_id=action_id,
        instance_id=instance.id,
        stage_order=next_stage_order,
        step_order=next_step.get("step_order", 1),
        stage_name=next_stage_name,
        step_name=next_step.get("step_name", ""),
        approval_type_key=next_step.get("approval_type_key", ""),
        approver_id=next_step.get("primary_approver_id", ""),
        approver_name=(
            primary_approver.get_display_name()
            if primary_approver
            else "Unknown User"
        ),
        status="pending",
    )
    db.session.add(new_action)
    return new_action


@user_api.route("/approval-action/<action_id>", methods=["POST"])
@require_auth
def take_approval_action(action_id):
    """Take an approval action (approve/refuse) on a pending action"""
    try:
        user = request.current_user

        # Find the action by action_id string (not database PK)
        action = RFPOApprovalAction.query.filter_by(action_id=action_id).first()
        if not action:
            # Try by database ID
            try:
                action = RFPOApprovalAction.query.get(int(action_id))
            except (ValueError, TypeError):
                pass
        if not action:
            return jsonify({"success": False, "message": "Action not found"}), 404

        instance = RFPOApprovalInstance.query.get(action.instance_id)
        if not instance:
            return jsonify({"success": False, "message": "Approval instance not found"}), 404

        if action.status != "pending":
            return jsonify({"success": False, "message": "Action is no longer pending"}), 400

        # Authorization check
        authorized_ids = _get_authorized_approver_ids_api(instance, action)
        if user.record_id not in authorized_ids:
            logger.warning(
                "SECURITY: User %s (record_id=%s) attempted to approve action %s "
                "(authorized: %s)",
                user.email, user.record_id, action.action_id, authorized_ids,
            )
            return jsonify({
                "success": False,
                "message": "You are not authorized to take this action.",
            }), 403

        data = request.get_json()
        status = data.get("status")
        comments = data.get("comments", "")

        if status not in ("approved", "refused"):
            return jsonify({
                "success": False,
                "message": "Invalid status. Must be 'approved' or 'refused'.",
            }), 400

        # Complete the action
        action.complete_action(status, comments, None, user.record_id)

        if status == "refused":
            instance.overall_status = "refused"
            instance.completed_at = datetime.utcnow()
            if instance.rfpo:
                instance.rfpo.status = "Refused"
                instance.rfpo.updated_by = user.get_display_name()
        else:
            next_action = _create_next_sequential_action_api(instance, action)
            if next_action is None:
                instance.overall_status = "approved"
                instance.completed_at = datetime.utcnow()
                if instance.rfpo:
                    instance.rfpo.status = "Approved"
                    instance.rfpo.updated_by = user.get_display_name()
                    if not instance.rfpo.po_number:
                        consortium = Consortium.query.filter_by(
                            consort_id=instance.rfpo.consortium_id,
                        ).first()
                        abbrev = consortium.abbrev if consortium else "GEN"
                        instance.rfpo.po_number = RFPO.generate_po_number(abbrev)
                        logger.info(
                            "AUDIT: PO number %s assigned to RFPO %s on approval",
                            instance.rfpo.po_number, instance.rfpo.rfpo_id,
                        )
            else:
                instance.current_stage_order = next_action.stage_order
                instance.current_step_order = next_action.step_order

        instance.updated_at = datetime.utcnow()
        db.session.commit()

        # Send notifications (best-effort)
        try:
            if instance.rfpo:
                if instance.overall_status == "approved":
                    _notify_workflow_complete_api(instance.rfpo, "Approved")
                elif instance.overall_status == "refused":
                    _notify_workflow_complete_api(instance.rfpo, "Refused")
                else:
                    pending = instance.get_pending_actions()
                    if pending:
                        _notify_pending_approvers_api(pending, instance.rfpo)
        except Exception as e:
            logger.error("Notification failed (non-fatal): %s", e)

        return jsonify({
            "success": True,
            "message": f"Action {status} successfully",
            "action": action.to_dict(),
            "instance_status": instance.overall_status,
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


def _notify_pending_approvers_api(actions, rfpo):
    """Send email notifications to approvers for pending actions."""
    try:
        from email_service import send_approval_notification
        for action in actions:
            if action.status != "pending":
                continue
            approver = User.query.filter_by(
                record_id=action.approver_id, active=True,
            ).first()
            if not approver or not approver.email:
                continue
            send_approval_notification(
                user_email=approver.email,
                user_name=approver.get_display_name(),
                rfpo_id=rfpo.rfpo_id,
                approval_type=action.step_name,
            )
    except Exception as e:
        logger.error("Failed to send approval notification: %s", e)


def _notify_workflow_complete_api(rfpo, outcome):
    """Send email notification to RFPO creator when workflow completes."""
    try:
        from email_service import email_service as _email_svc
        creator = User.query.filter_by(
            email=rfpo.created_by, active=True,
        ).first()
        if not creator or not creator.email:
            return
        user_app_url = (
            os.environ.get("USER_APP_URL")
            or os.environ.get("APP_URL")
            or "http://localhost:5000"
        )
        _email_svc.send_templated_email(
            to_emails=[creator.email],
            template_name="approval_complete",
            template_data={
                "user_name": creator.get_display_name(),
                "rfpo_id": rfpo.rfpo_id,
                "po_number": rfpo.po_number,
                "outcome": outcome,
                "rfpo_url": f"{user_app_url}/rfpos/{rfpo.id}",
            },
            subject=f"RFPO {outcome} - {rfpo.rfpo_id}",
        )
    except Exception as e:
        logger.error("Failed to send completion notification: %s", e)
