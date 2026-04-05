"""
Team Management API Routes
Centralized team endpoints for both user app and admin panel
"""

from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import uuid
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, Team, Consortium
from utils import require_auth, require_admin_or_team_admin

team_api = Blueprint("team_api", __name__, url_prefix="/api/teams")


@team_api.route("", methods=["GET"])
@require_auth
def list_teams():
    """List teams with filtering and pagination"""
    try:
        # Filters
        query = Team.query

        active = request.args.get("active")
        if active is not None:
            query = query.filter_by(active=(active.lower() == "true"))

        consortium_id = request.args.get("consortium_id")
        if consortium_id:
            query = query.filter_by(consortium_consort_id=consortium_id)

        search = request.args.get("search")
        if search:
            query = query.filter(Team.name.ilike(f"%{search}%"))

        # Pagination
        page = request.args.get("page", 1, type=int)
        per_page = min(request.args.get("per_page", 20, type=int), 200)

        teams = query.order_by(Team.name).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify(
            {
                "success": True,
                "teams": [team.to_dict() for team in teams.items],
                "total": teams.total,
                "page": teams.page,
                "pages": teams.pages,
            }
        )

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@team_api.route("", methods=["POST"])
@require_auth
@require_admin_or_team_admin
def create_team():
    """Create new team"""
    try:
        data = request.get_json()

        # Validate required fields
        if (
            not data.get("name")
            or not data.get("abbrev")
            or not data.get("consortium_id")
        ):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Name, abbreviation, and consortium are required",
                    }
                ),
                400,
            )

        # Auto-generate record_id
        record_id = data.get("record_id") or str(uuid.uuid4())[:8].upper()

        team = Team(
            record_id=record_id,
            name=data["name"],
            description=data.get("description"),
            abbrev=data["abbrev"],
            consortium_consort_id=data["consortium_id"],
            active=data.get("active", True),
            created_by=request.current_user.username,
            updated_by=request.current_user.username,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Set JSON array fields via setter methods
        if data.get("rfpo_viewer_user_ids"):
            team.set_rfpo_viewer_users(data["rfpo_viewer_user_ids"])
        if data.get("rfpo_admin_user_ids"):
            team.set_rfpo_admin_users(data["rfpo_admin_user_ids"])

        db.session.add(team)
        db.session.commit()

        return jsonify({"success": True, "team": team.to_dict()}), 201

    except IntegrityError:
        db.session.rollback()
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Team name or abbreviation already exists in this consortium",
                }
            ),
            400,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@team_api.route("/<int:team_id>", methods=["GET"])
@require_auth
def get_team(team_id):
    """Get team details"""
    try:
        team = Team.query.get_or_404(team_id)
        return jsonify({"success": True, "team": team.to_dict()})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@team_api.route("/<int:team_id>", methods=["PUT"])
@require_auth
@require_admin_or_team_admin
def update_team(team_id):
    """Update team"""
    try:
        team = Team.query.get_or_404(team_id)
        data = request.get_json()

        # Update fields
        team.name = data.get("name", team.name)
        team.description = data.get("description", team.description)
        team.abbrev = data.get("abbrev", team.abbrev)
        if "consortium_id" in data:
            team.consortium_consort_id = data["consortium_id"]
        if "active" in data:
            team.active = data["active"]
        if "rfpo_viewer_user_ids" in data:
            team.set_rfpo_viewer_users(data["rfpo_viewer_user_ids"])
        if "rfpo_admin_user_ids" in data:
            team.set_rfpo_admin_users(data["rfpo_admin_user_ids"])
        team.updated_by = request.current_user.username
        team.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({"success": True, "team": team.to_dict()})

    except IntegrityError:
        db.session.rollback()
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Team name or abbreviation already exists in this consortium",
                }
            ),
            400,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@team_api.route("/<int:team_id>", methods=["DELETE"])
@require_auth
@require_admin_or_team_admin
def delete_team(team_id):
    """Delete team (admin only)"""
    try:
        # Only system admins can delete teams
        user_perms = request.current_user.get_permissions() or []
        if "GOD" not in user_perms:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "System administrator access required",
                    }
                ),
                403,
            )

        team = Team.query.get_or_404(team_id)
        db.session.delete(team)
        db.session.commit()

        return jsonify({"success": True, "message": "Team deleted successfully"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@team_api.route("/<int:team_id>/activate", methods=["POST"])
@require_auth
@require_admin_or_team_admin
def activate_team(team_id):
    """Activate team"""
    try:
        team = Team.query.get_or_404(team_id)
        team.active = True
        team.updated_by = request.current_user.username
        team.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({"success": True, "team": team.to_dict()})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@team_api.route("/<int:team_id>/deactivate", methods=["POST"])
@require_auth
@require_admin_or_team_admin
def deactivate_team(team_id):
    """Deactivate team"""
    try:
        team = Team.query.get_or_404(team_id)
        team.active = False
        team.updated_by = request.current_user.username
        team.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({"success": True, "team": team.to_dict()})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
