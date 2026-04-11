"""Team API proxy blueprint — /api/teams/* routes."""

from urllib.parse import urlencode

from flask import Blueprint, jsonify, request

from user_app.api_client import get_api_client

team_proxy_bp = Blueprint("team_proxy", __name__)


@team_proxy_bp.route("/api/teams", methods=["GET", "POST"])
def api_teams():
    """Teams API proxy."""
    client = get_api_client()
    if request.method == "POST":
        data = request.get_json()
        response = client.post("/teams", data)
        return jsonify(response)
    params = urlencode(request.args.to_dict(flat=False), doseq=True)
    endpoint = f"/teams?{params}" if params else "/teams"
    response = client.get(endpoint)
    return jsonify(response)


@team_proxy_bp.route("/api/teams/<int:team_id>", methods=["GET"])
def api_team_detail(team_id):
    """Team detail API proxy."""
    client = get_api_client()
    response = client.get(f"/teams/{team_id}")
    return jsonify(response)
