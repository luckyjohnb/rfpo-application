"""
RFPO Management API Routes
Centralized RFPO endpoints for both user app and admin panel
"""

from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, RFPO, RFPOLineItem, Team, UploadedFile
from utils import require_auth

rfpo_api = Blueprint("rfpo_api", __name__, url_prefix="/api/rfpos")


@rfpo_api.route("", methods=["GET"])
@require_auth
def list_rfpos():
    """List RFPOs with filtering and pagination based on user permissions"""
    try:
        from models import Team, Project

        user = request.current_user

        # Build base query with permission filtering
        query = RFPO.query

        # If user is super admin, they can see all RFPOs
        if not user.is_super_admin():
            # Get user's accessible team IDs
            user_teams = user.get_teams()
            team_ids = [team.id for team in user_teams]

            # Get user's accessible project IDs
            all_projects = Project.query.all()
            accessible_project_ids = []
            for project in all_projects:
                viewer_users = project.get_rfpo_viewer_users()
                if user.record_id in viewer_users:
                    accessible_project_ids.append(project.project_id)

            # Filter RFPOs to only those user can access
            if team_ids or accessible_project_ids:
                filters = []
                if team_ids:
                    filters.append(RFPO.team_id.in_(team_ids))
                if accessible_project_ids:
                    filters.append(RFPO.project_id.in_(accessible_project_ids))

                if len(filters) > 1:
                    query = query.filter(db.or_(*filters))
                else:
                    query = query.filter(filters[0])
            else:
                # User has no access to any RFPOs
                query = query.filter(RFPO.id == -1)  # This will return no results

        # Apply additional filters
        team_id = request.args.get("team_id")
        if team_id:
            query = query.filter_by(team_id=team_id)

        status = request.args.get("status")
        if status:
            query = query.filter_by(status=status)

        search = request.args.get("search")
        if search:
            query = query.filter(
                RFPO.title.ilike(f"%{search}%")
                | RFPO.rfpo_id.ilike(f"%{search}%")
                | RFPO.description.ilike(f"%{search}%")
            )

        # Pagination
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))

        rfpos = query.order_by(RFPO.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify(
            {
                "success": True,
                "rfpos": [rfpo.to_dict() for rfpo in rfpos.items],
                "total": rfpos.total,
                "page": rfpos.page,
                "pages": rfpos.pages,
            }
        )

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@rfpo_api.route("", methods=["POST"])
@require_auth
def create_rfpo():
    """Create new RFPO"""
    try:
        data = request.get_json()

        # Validate required fields
        if not data.get("title") or not data.get("team_id"):
            return (
                jsonify({"success": False, "message": "Title and team are required"}),
                400,
            )

        # Verify team exists
        team = Team.query.get(data["team_id"])
        if not team:
            return jsonify({"success": False, "message": "Team not found"}), 404

        # Generate RFPO ID
        rfpo_count = RFPO.query.count()
        rfpo_id = f"RFPO-{rfpo_count + 1:04d}"

        # Ensure unique RFPO ID
        while RFPO.query.filter_by(rfpo_id=rfpo_id).first():
            rfpo_count += 1
            rfpo_id = f"RFPO-{rfpo_count + 1:04d}"

        rfpo = RFPO(
            rfpo_id=rfpo_id,
            title=data["title"],
            description=data.get("description", ""),
            vendor=data.get("vendor", ""),
            due_date=(
                datetime.fromisoformat(data["due_date"])
                if data.get("due_date")
                else None
            ),
            status=data.get("status", "Draft"),
            team_id=data["team_id"],
            created_by=request.current_user.username,
            updated_by=request.current_user.username,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.session.add(rfpo)
        db.session.commit()

        return jsonify({"success": True, "rfpo": rfpo.to_dict()}), 201

    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "RFPO ID already exists"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@rfpo_api.route("/<int:rfpo_id>", methods=["GET"])
@require_auth
def get_rfpo(rfpo_id):
    """Get RFPO details"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)
        rfpo_data = rfpo.to_dict()

        # Add line items
        line_items = RFPOLineItem.query.filter_by(rfpo_id=rfpo_id).all()
        rfpo_data["line_items"] = [item.to_dict() for item in line_items]

        # Add uploaded files
        files = UploadedFile.query.filter_by(rfpo_id=rfpo_id).all()
        rfpo_data["files"] = [file.to_dict() for file in files]

        return jsonify({"success": True, "rfpo": rfpo_data})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@rfpo_api.route("/<int:rfpo_id>", methods=["PUT"])
@require_auth
def update_rfpo(rfpo_id):
    """Update RFPO"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)
        data = request.get_json()

        # Update fields
        rfpo.title = data.get("title", rfpo.title)
        rfpo.description = data.get("description", rfpo.description)
        rfpo.vendor = data.get("vendor", rfpo.vendor)
        if data.get("due_date"):
            rfpo.due_date = datetime.fromisoformat(data["due_date"])
        rfpo.status = data.get("status", rfpo.status)
        rfpo.updated_by = request.current_user.username
        rfpo.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({"success": True, "rfpo": rfpo.to_dict()})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@rfpo_api.route("/<int:rfpo_id>", methods=["DELETE"])
@require_auth
def delete_rfpo(rfpo_id):
    """Delete RFPO"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)

        # Check permissions (only creator or admin can delete)
        if (
            rfpo.created_by != request.current_user.username
            and "Administrator" not in request.current_user.roles
        ):
            return jsonify({"success": False, "message": "Permission denied"}), 403

        db.session.delete(rfpo)
        db.session.commit()

        return jsonify({"success": True, "message": "RFPO deleted successfully"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@rfpo_api.route("/<int:rfpo_id>/line-items", methods=["GET"])
@require_auth
def get_rfpo_line_items(rfpo_id):
    """Get RFPO line items"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)
        line_items = RFPOLineItem.query.filter_by(rfpo_id=rfpo_id).all()

        return jsonify(
            {"success": True, "line_items": [item.to_dict() for item in line_items]}
        )

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@rfpo_api.route("/<int:rfpo_id>/line-items", methods=["POST"])
@require_auth
def create_line_item(rfpo_id):
    """Create RFPO line item"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)
        data = request.get_json()

        line_item = RFPOLineItem(
            rfpo_id=rfpo_id,
            line_number=data.get("line_number", 1),
            description=data.get("description", ""),
            quantity=data.get("quantity", 1),
            unit_price=data.get("unit_price", 0.0),
            total_price=data.get("quantity", 1) * data.get("unit_price", 0.0),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.session.add(line_item)
        db.session.commit()

        return jsonify({"success": True, "line_item": line_item.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@rfpo_api.route("/<int:rfpo_id>/files", methods=["GET"])
@require_auth
def get_rfpo_files(rfpo_id):
    """Get RFPO uploaded files"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)
        files = UploadedFile.query.filter_by(rfpo_id=rfpo_id).all()

        return jsonify({"success": True, "files": [file.to_dict() for file in files]})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
