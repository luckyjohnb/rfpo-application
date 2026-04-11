"""RFPO API proxy blueprint — /api/rfpos/* routes."""

from urllib.parse import urlencode

import requests
from flask import Blueprint, Response, jsonify, request, session

from user_app.api_client import get_api_client
from user_app.decorators import require_auth_json

rfpo_proxy_bp = Blueprint("rfpo_proxy", __name__)


@rfpo_proxy_bp.route("/api/rfpos", methods=["GET", "POST"])
def api_rfpos():
    """RFPOs API proxy."""
    client = get_api_client()
    if request.method == "GET":
        params = urlencode(request.args.to_dict(flat=False), doseq=True)
        endpoint = f"/rfpos?{params}" if params else "/rfpos"
        response = client.get(endpoint)
    else:
        data = request.get_json()
        response = client.post("/rfpos", data)
    return jsonify(response)


@rfpo_proxy_bp.route("/api/rfpos/<int:rfpo_id>", methods=["GET", "PUT", "DELETE"])
def api_rfpo_detail(rfpo_id):
    """RFPO detail API proxy."""
    client = get_api_client()
    if request.method == "GET":
        response = client.get(f"/rfpos/{rfpo_id}")
    elif request.method == "PUT":
        data = request.get_json()
        response = client.put(f"/rfpos/{rfpo_id}", data)
    else:
        response = client.delete(f"/rfpos/{rfpo_id}")
    return jsonify(response)


@rfpo_proxy_bp.route("/api/rfpos/<int:rfpo_id>/validate", methods=["GET"])
def api_validate_rfpo(rfpo_id):
    """Validate RFPO readiness."""
    client = get_api_client()
    response = client.get(f"/rfpos/{rfpo_id}/validate")
    return jsonify(response)


@rfpo_proxy_bp.route("/api/rfpos/<int:rfpo_id>/submit-for-approval", methods=["POST"])
def api_submit_for_approval(rfpo_id):
    """Submit RFPO for approval."""
    client = get_api_client()
    response = client.post(f"/rfpos/{rfpo_id}/submit-for-approval")
    return jsonify(response)


@rfpo_proxy_bp.route("/api/rfpos/<int:rfpo_id>/withdraw-approval", methods=["POST"])
def api_withdraw_approval(rfpo_id):
    """Withdraw RFPO from approval process."""
    client = get_api_client()
    data = request.get_json() if request.is_json else {}
    response = client.post(f"/rfpos/{rfpo_id}/withdraw-approval", data)
    return jsonify(response)


@rfpo_proxy_bp.route("/api/rfpos/<int:rfpo_id>/line-items", methods=["GET", "POST"])
def api_rfpo_line_items(rfpo_id):
    """RFPO line items API proxy."""
    client = get_api_client()
    if request.method == "POST":
        data = request.get_json()
        response = client.post(f"/rfpos/{rfpo_id}/line-items", data)
    else:
        response = client.get(f"/rfpos/{rfpo_id}/line-items")
    return jsonify(response)


@rfpo_proxy_bp.route(
    "/api/rfpos/<int:rfpo_id>/line-items/<int:line_item_id>",
    methods=["PUT", "DELETE"],
)
def api_rfpo_line_item_detail(rfpo_id, line_item_id):
    """RFPO line item detail API proxy."""
    client = get_api_client()
    if request.method == "PUT":
        data = request.get_json()
        response = client.put(f"/rfpos/{rfpo_id}/line-items/{line_item_id}", data)
    else:
        response = client.delete(f"/rfpos/{rfpo_id}/line-items/{line_item_id}")
    return jsonify(response)


@rfpo_proxy_bp.route("/api/rfpos/<int:rfpo_id>/rendered-view", methods=["GET"])
def api_rfpo_rendered_view(rfpo_id):
    """RFPO rendered view API proxy."""
    client = get_api_client()
    response = client.get(f"/rfpos/{rfpo_id}/rendered-view")
    return jsonify(response)


@rfpo_proxy_bp.route("/api/rfpos/<int:rfpo_id>/audit-trail", methods=["GET"])
@require_auth_json
def api_rfpo_audit_trail(rfpo_id):
    """RFPO audit trail API proxy."""
    client = get_api_client()
    response = client.get(f"/rfpos/{rfpo_id}/audit-trail")
    return jsonify(response)


@rfpo_proxy_bp.route("/api/rfpos/doc-types", methods=["GET"])
@require_auth_json
def api_doc_types():
    """Document types API proxy."""
    client = get_api_client()
    response = client.get("/rfpos/doc-types")
    return jsonify(response)


@rfpo_proxy_bp.route("/api/rfpos/analytics", methods=["GET"])
@require_auth_json
def api_rfpos_analytics():
    """RFPO analytics API proxy."""
    client = get_api_client()
    response = client.get("/rfpos/analytics")
    return jsonify(response)
