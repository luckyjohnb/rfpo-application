"""Lookup/reference-data proxy blueprint — consortiums, projects, vendors."""

from flask import Blueprint, jsonify, request

from user_app.api_client import get_api_client
from user_app.decorators import require_auth_json

lookup_proxy_bp = Blueprint("lookup_proxy", __name__)


@lookup_proxy_bp.route("/api/consortiums", methods=["GET", "POST"])
@require_auth_json
def api_consortiums():
    """Consortiums API proxy."""
    client = get_api_client()
    if request.method == "POST":
        data = request.get_json()
        response = client.post("/consortiums", data)
        return jsonify(response)
    response = client.get("/consortiums")
    return jsonify(response)


@lookup_proxy_bp.route("/api/projects", methods=["POST"])
@require_auth_json
def api_create_project():
    """Create project API proxy."""
    client = get_api_client()
    data = request.get_json()
    response = client.post("/projects", data)
    return jsonify(response)


@lookup_proxy_bp.route("/api/projects/<consortium_id>", methods=["GET"])
@require_auth_json
def api_projects_for_consortium(consortium_id):
    """Projects for consortium API proxy."""
    client = get_api_client()
    response = client.get(f"/projects/{consortium_id}")
    return jsonify(response)


@lookup_proxy_bp.route("/api/vendors", methods=["GET", "POST"])
@require_auth_json
def api_vendors():
    """Vendors API proxy."""
    client = get_api_client()
    if request.method == "POST":
        data = request.get_json()
        response = client.post("/vendors", data)
        return jsonify(response)
    response = client.get("/vendors")
    return jsonify(response)


@lookup_proxy_bp.route("/api/vendor-sites/<int:vendor_id>", methods=["GET"])
@require_auth_json
def api_vendor_sites(vendor_id):
    """Vendor sites API proxy."""
    client = get_api_client()
    response = client.get(f"/vendor-sites/{vendor_id}")
    return jsonify(response)
