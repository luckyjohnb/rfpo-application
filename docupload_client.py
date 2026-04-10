"""
DOCUPLOAD Client - Secure document upload to Azure Blob Storage.

Uploads files to the DOCUPLOAD service with API key authentication
and custom folder structure support.

Usage:
    from docupload_client import upload_to_docupload

    result = upload_to_docupload(
        files={"quote": (filename, file_bytes, mime_type)},
        folder_path="rfpo/RFPO-2026-001/quote",
        form_id="rfpo-documents",
        submitted_by="admin@rfpo.com",
        tags={"rfpo-number": "RFPO-2026-001"}
    )
"""
import os
import json
import logging
import requests

logger = logging.getLogger(__name__)

DOCUPLOAD_URL = os.environ.get(
    "DOCUPLOAD_URL",
    "https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io"
)
DOCUPLOAD_API_KEY = os.environ.get("DOCUPLOAD_API_KEY", "")
DOCUPLOAD_TIMEOUT = int(os.environ.get("DOCUPLOAD_TIMEOUT", "60"))


def is_configured():
    """Check if DOCUPLOAD service is configured."""
    return bool(DOCUPLOAD_URL and DOCUPLOAD_API_KEY)


def upload_to_docupload(files, folder_path, form_id="rfpo-documents",
                         submitted_by="", tags=None):
    """Upload one or more files to DOCUPLOAD with custom folder path.

    Args:
        files: dict of {field_name: (filename, file_bytes_or_stream, content_type)}
               or {field_name: (filename, file_bytes_or_stream)}
        folder_path: Blob folder path, e.g. "rfpo/RFPO-2026-001/quote"
        form_id: Form identifier for tracking
        submitted_by: User who initiated the upload
        tags: Optional dict of metadata tags

    Returns:
        dict with keys:
            success (bool), submission_id (str), uploaded_files (list),
            folder_path (str), scan_status (str), error (str or None)
    """
    if not is_configured():
        logger.warning("DOCUPLOAD not configured — skipping cloud upload")
        return {
            "success": False,
            "error": "DOCUPLOAD service not configured",
            "submission_id": None,
            "uploaded_files": [],
        }

    try:
        # Build multipart files payload
        files_payload = {}
        for field_name, file_tuple in files.items():
            files_payload[field_name] = file_tuple

        # Build form data
        data = {
            "formId": form_id,
            "folderPath": folder_path,
            "submittedBy": submitted_by or "rfpo-system",
        }
        if tags:
            data["tags"] = json.dumps(tags)

        response = requests.post(
            f"{DOCUPLOAD_URL}/submit",
            headers={"X-API-Key": DOCUPLOAD_API_KEY},
            files=files_payload,
            data=data,
            timeout=DOCUPLOAD_TIMEOUT,
        )

        if response.status_code == 201:
            result = response.json()
            logger.info(
                "DOCUPLOAD_SUCCESS: %s → %s (%d files)",
                result.get("submissionId", "?"),
                result.get("folderPath", folder_path),
                result.get("fileCount", 0),
            )
            return {
                "success": True,
                "submission_id": result.get("submissionId"),
                "uploaded_files": result.get("uploadedFiles", []),
                "folder_path": result.get("folderPath", folder_path),
                "scan_status": result.get("scanStatus", "unknown"),
                "blob_path": result.get("blobPath"),
                "error": None,
            }
        else:
            error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            error_msg = error_data.get("message", f"HTTP {response.status_code}")
            logger.error("DOCUPLOAD_FAILED: %s — %s", folder_path, error_msg)
            return {
                "success": False,
                "error": error_msg,
                "submission_id": None,
                "uploaded_files": [],
            }

    except requests.Timeout:
        logger.error("DOCUPLOAD_TIMEOUT: Upload to %s timed out after %ds", folder_path, DOCUPLOAD_TIMEOUT)
        return {
            "success": False,
            "error": "Upload service timed out",
            "submission_id": None,
            "uploaded_files": [],
        }
    except requests.ConnectionError:
        logger.error("DOCUPLOAD_CONNECTION_ERROR: Cannot reach %s", DOCUPLOAD_URL)
        return {
            "success": False,
            "error": "Cannot reach upload service",
            "submission_id": None,
            "uploaded_files": [],
        }
    except Exception as e:
        logger.error("DOCUPLOAD_ERROR: %s — %s", folder_path, str(e))
        return {
            "success": False,
            "error": str(e),
            "submission_id": None,
            "uploaded_files": [],
        }
