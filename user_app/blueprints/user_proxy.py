"""User API proxy blueprint — /api/users/* routes."""

from flask import Blueprint, jsonify, request

from user_app.api_client import get_api_client

user_proxy_bp = Blueprint("user_proxy", __name__)


@user_proxy_bp.route("/api/users/profile", methods=["GET"])
def api_user_profile():
    """User profile API proxy."""
    client = get_api_client()
    response = client.get("/users/profile")
    return jsonify(response)


@user_proxy_bp.route("/api/users/profile", methods=["PUT"])
def api_update_profile():
    """Update user profile API proxy."""
    client = get_api_client()
    data = request.get_json()
    response = client.put("/users/profile", data)
    return jsonify(response)


@user_proxy_bp.route("/api/users/permissions-summary", methods=["GET"])
def api_user_permissions_summary():
    """User permissions summary API proxy."""
    client = get_api_client()
    response = client.get("/users/permissions-summary")
    return jsonify(response)


@user_proxy_bp.route("/api/users/approver-status", methods=["GET"])
def api_user_approver_status():
    """User approver status API proxy."""
    client = get_api_client()
    response = client.get("/users/approver-status")
    return jsonify(response)


@user_proxy_bp.route("/api/users/approver-rfpos", methods=["GET"])
def api_user_approver_rfpos():
    """User approver RFPOs API proxy."""
    client = get_api_client()
    response = client.get("/users/approver-rfpos")
    return jsonify(response)


@user_proxy_bp.route("/api/users/approval-action/<action_id>", methods=["POST"])
def api_take_approval_action(action_id):
    """Take approval action API proxy."""
    client = get_api_client()
    data = request.get_json()
    response = client.post(f"/users/approval-action/{action_id}", data)
    return jsonify(response)


@user_proxy_bp.route("/api/users/bulk-approval", methods=["POST"])
def api_bulk_approval():
    """Bulk approval action API proxy."""
    client = get_api_client()
    data = request.get_json()
    response = client.post("/users/bulk-approval", data)
    return jsonify(response)


@user_proxy_bp.route("/api/users/reassign-approval/<action_id>", methods=["POST"])
def api_reassign_approval(action_id):
    """Reassign approval action API proxy."""
    client = get_api_client()
    data = request.get_json()
    response = client.post(f"/users/reassign-approval/{action_id}", data)
    return jsonify(response)


@user_proxy_bp.route("/api/users/list", methods=["GET"])
def api_list_users():
    """List active users API proxy."""
    client = get_api_client()
    response = client.get("/users")
    return jsonify(response)
