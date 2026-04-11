"""Ticket pages — bugs, feature requests, detail."""

from flask import render_template

from user_app.blueprints.pages import pages_bp
from user_app.decorators import require_auth


@pages_bp.route("/bugs")
@require_auth
def bugs_page():
    """Bug report page."""
    return render_template("app/bugs.html")


@pages_bp.route("/feature-requests")
@require_auth
def feature_requests_page():
    """Feature request page."""
    return render_template("app/feature_requests.html")


@pages_bp.route("/tickets/<int:ticket_id>")
@require_auth
def ticket_detail_page(ticket_id):
    """Individual ticket detail page."""
    return render_template("app/ticket_detail.html", ticket_id=ticket_id)
