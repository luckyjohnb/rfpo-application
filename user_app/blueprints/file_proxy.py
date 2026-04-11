"""File & stream proxy blueprint — file uploads, CSV export, PDF snapshots."""

import requests
from flask import Blueprint, Response, jsonify, request

from user_app.api_client import get_api_client
from user_app.decorators import require_auth_json

file_proxy_bp = Blueprint("file_proxy", __name__)


@file_proxy_bp.route("/api/rfpos/<int:rfpo_id>/files/upload", methods=["POST"])
@require_auth_json
def api_rfpo_upload_file(rfpo_id):
    """RFPO file upload proxy — forwards multipart form data to API."""
    client = get_api_client()
    try:
        files = {}
        if "file" in request.files:
            f = request.files["file"]
            files["file"] = (f.filename, f.stream, f.content_type)

        form_data = {
            "document_type": request.form.get("document_type", ""),
            "description": request.form.get("description", ""),
        }

        resp = client.raw_post(
            f"/rfpos/{rfpo_id}/files/upload",
            files=files,
            data=form_data,
            timeout=30,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.exceptions.RequestException:
        return jsonify({"success": False, "message": "File upload failed. Please try again."}), 503


@file_proxy_bp.route(
    "/api/rfpos/<int:rfpo_id>/files/<file_id>/view", methods=["GET"]
)
@require_auth_json
def api_rfpo_view_file(rfpo_id, file_id):
    """RFPO file view proxy — streams file content from API."""
    client = get_api_client()
    try:
        resp = client.raw_get(
            f"/rfpos/{rfpo_id}/files/{file_id}/view",
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
                "Content-Disposition": resp.headers.get("Content-Disposition", ""),
            },
        )
    except requests.exceptions.RequestException:
        return jsonify({"success": False, "message": "File not available. Please try again."}), 503


@file_proxy_bp.route(
    "/api/rfpos/<int:rfpo_id>/files/<file_id>", methods=["DELETE"]
)
@require_auth_json
def api_rfpo_delete_file(rfpo_id, file_id):
    """RFPO file delete proxy."""
    client = get_api_client()
    response = client.delete(f"/rfpos/{rfpo_id}/files/{file_id}")
    return jsonify(response)


@file_proxy_bp.route("/api/rfpos/export", methods=["GET"])
@require_auth_json
def api_rfpos_export():
    """RFPO CSV export proxy — streams CSV from API."""
    client = get_api_client()
    try:
        resp = client.raw_get("/rfpos/export", stream=True, timeout=30)
        return Response(
            resp.iter_content(chunk_size=8192),
            mimetype=resp.headers.get("Content-Type", "text/csv"),
            headers={
                "Content-Disposition": resp.headers.get(
                    "Content-Disposition",
                    "attachment; filename=rfpos_export.csv",
                )
            },
        )
    except requests.exceptions.RequestException:
        return (
            jsonify({"success": False, "message": "Export failed. Please try again."}),
            503,
        )


@file_proxy_bp.route("/api/rfpos/<int:rfpo_id>/pdf-snapshot")
@require_auth_json
def api_rfpo_pdf_snapshot(rfpo_id):
    """Proxy the PDF snapshot from the API server (binary stream)."""
    client = get_api_client()
    resp = client.raw_get(f"/rfpos/{rfpo_id}/pdf-snapshot", timeout=30)

    if resp.status_code != 200:
        try:
            return jsonify(resp.json()), resp.status_code
        except Exception:
            return (
                jsonify({"success": False, "message": "PDF snapshot not available"}),
                resp.status_code,
            )

    return Response(
        resp.content,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": resp.headers.get(
                "Content-Disposition",
                f'inline; filename="PO_SNAPSHOT_{rfpo_id}.pdf"',
            )
        },
    )
