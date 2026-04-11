"""Notification API proxy blueprint — /api/notifications/* routes."""

from urllib.parse import urlencode

from flask import Blueprint, jsonify, request

from user_app.api_client import get_api_client
from user_app.decorators import require_auth_json

notification_proxy_bp = Blueprint("notification_proxy", __name__)


@notification_proxy_bp.route("/api/notifications", methods=["GET"])
@require_auth_json
def api_notifications():
    """Notifications list API proxy."""
    client = get_api_client()
    params = urlencode(request.args.to_dict(flat=False), doseq=True)
    endpoint = f"/notifications?{params}" if params else "/notifications"
    response = client.get(endpoint)
    return jsonify(response)


@notification_proxy_bp.route("/api/notifications/unread-count", methods=["GET"])
@require_auth_json
def api_notifications_unread_count():
    """Unread notification count API proxy."""
    client = get_api_client()
    response = client.get("/notifications/unread-count")
    return jsonify(response)


@notification_proxy_bp.route("/api/notifications/<int:notif_id>/read", methods=["PUT"])
@require_auth_json
def api_notification_mark_read(notif_id):
    """Mark notification as read API proxy."""
    client = get_api_client()
    response = client.put(f"/notifications/{notif_id}/read")
    return jsonify(response)


@notification_proxy_bp.route("/api/notifications/mark-all-read", methods=["POST"])
@require_auth_json
def api_notifications_mark_all_read():
    """Mark all notifications as read API proxy."""
    client = get_api_client()
    response = client.post("/notifications/mark-all-read")
    return jsonify(response)
