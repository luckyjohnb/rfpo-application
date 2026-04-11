"""Team pages — list and detail."""

from flask import render_template

from user_app.blueprints.pages import pages_bp
from user_app.decorators import require_auth


@pages_bp.route("/teams")
@require_auth
def teams_list():
    """Teams list page."""
    return render_template("app/teams.html")


@pages_bp.route("/teams/<int:team_id>")
@require_auth
def team_detail(team_id):
    """Team detail page."""
    return render_template("app/team_detail.html", team_id=team_id)
