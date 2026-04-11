"""Ticket system proxy blueprint — /api/tickets/* routes."""

import requests
from flask import Blueprint, Response, jsonify, request, session

from user_app.api_client import get_api_client
from user_app.decorators import require_auth_json

ticket_proxy_bp = Blueprint("ticket_proxy", __name__)


@ticket_proxy_bp.route("/api/tickets", methods=["GET"])
@require_auth_json
def api_tickets_list():
    """Proxy GET /api/tickets to API with query params."""
    client = get_api_client()
    qs = request.query_string.decode()
    endpoint = f"/tickets?{qs}" if qs else "/tickets"
    result = client.get(endpoint)
    return jsonify(result)


@ticket_proxy_bp.route("/api/tickets", methods=["POST"])
@require_auth_json
def api_tickets_create():
    """Proxy POST /api/tickets to API."""
    client = get_api_client()
    data = request.get_json()
    result = client.post("/tickets", data)
    return jsonify(result)


@ticket_proxy_bp.route("/api/tickets/<int:ticket_id>", methods=["GET"])
@require_auth_json
def api_ticket_get(ticket_id):
    """Proxy GET /api/tickets/<id> to API."""
    client = get_api_client()
    result = client.get(f"/tickets/{ticket_id}")
    return jsonify(result)


@ticket_proxy_bp.route("/api/tickets/<int:ticket_id>", methods=["PUT"])
@require_auth_json
def api_ticket_update(ticket_id):
    """Proxy PUT /api/tickets/<id> to API."""
    client = get_api_client()
    data = request.get_json()
    result = client.put(f"/tickets/{ticket_id}", data)
    return jsonify(result)


@ticket_proxy_bp.route("/api/tickets/<int:ticket_id>/comments", methods=["POST"])
@require_auth_json
def api_ticket_add_comment(ticket_id):
    """Proxy POST comment to API."""
    client = get_api_client()
    data = request.get_json()
    result = client.post(f"/tickets/{ticket_id}/comments", data)
    return jsonify(result)


@ticket_proxy_bp.route("/api/tickets/<int:ticket_id>/attachments", methods=["POST"])
@require_auth_json
def api_ticket_upload_attachment(ticket_id):
    """Proxy file upload to ticket attachment API."""
    client = get_api_client()
    try:
        files = {}
        if "file" in request.files:
            f = request.files["file"]
            files["file"] = (f.filename, f.stream, f.content_type)
        resp = client.raw_post(
            f"/tickets/{ticket_id}/attachments", files=files, timeout=30
        )
        return jsonify(resp.json()), resp.status_code
    except requests.exceptions.RequestException:
        return jsonify({"success": False, "message": "API service unavailable"}), 503


@ticket_proxy_bp.route(
    "/api/tickets/<int:ticket_id>/attachments/<file_id>/view", methods=["GET"]
)
@require_auth_json
def api_ticket_view_attachment(ticket_id, file_id):
    """Proxy attachment download from API."""
    client = get_api_client()
    try:
        resp = client.raw_get(
            f"/tickets/{ticket_id}/attachments/{file_id}/view",
            stream=True,
            timeout=30,
        )
        if resp.status_code != 200:
            return (
                jsonify({"success": False, "message": "File not found"}),
                resp.status_code,
            )
        return Response(
            resp.iter_content(chunk_size=8192),
            content_type=resp.headers.get(
                "Content-Type", "application/octet-stream"
            ),
            headers={
                "Content-Disposition": resp.headers.get("Content-Disposition", "")
            },
        )
    except requests.exceptions.RequestException:
        return jsonify({"success": False, "message": "API service unavailable"}), 503
