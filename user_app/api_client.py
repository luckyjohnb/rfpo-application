"""Centralised API client for the User App.

Encapsulates all HTTP communication with the backend API layer so that
route handlers never build URLs or manage headers directly.

Usage inside a blueprint::

    from user_app.api_client import get_api_client

    client = get_api_client()
    result = client.get("/rfpos")
"""

import logging

import requests
from flask import current_app, session

logger = logging.getLogger("user_app.api_client")


class APIClient:
    """Thin wrapper around ``requests`` that adds auth, timeouts and
    standard error handling for the RFPO API layer."""

    def __init__(self, base_url: str, admin_url: str | None = None,
                 timeout: int = 10):
        self.base_url = base_url
        self.admin_url = admin_url or base_url
        self.timeout = timeout

    # ── public helpers ──────────────────────────────────────────────

    def get(self, endpoint: str, *, use_admin: bool = False,
            extra_headers: dict | None = None, timeout: int | None = None):
        return self._request("GET", endpoint, use_admin=use_admin,
                             extra_headers=extra_headers, timeout=timeout)

    def post(self, endpoint: str, data=None, *, use_admin: bool = False,
             extra_headers: dict | None = None, timeout: int | None = None):
        return self._request("POST", endpoint, data=data,
                             use_admin=use_admin, extra_headers=extra_headers,
                             timeout=timeout)

    def put(self, endpoint: str, data=None, *, use_admin: bool = False,
            extra_headers: dict | None = None, timeout: int | None = None):
        return self._request("PUT", endpoint, data=data,
                             use_admin=use_admin, extra_headers=extra_headers,
                             timeout=timeout)

    def delete(self, endpoint: str, *, use_admin: bool = False,
               extra_headers: dict | None = None, timeout: int | None = None):
        return self._request("DELETE", endpoint, use_admin=use_admin,
                             extra_headers=extra_headers, timeout=timeout)

    def raw_get(self, endpoint: str, *, stream: bool = False,
                timeout: int | None = None):
        """Low-level GET that returns the raw ``requests.Response``.

        Use for binary streams (PDF, CSV, file downloads).
        """
        url = f"{self.base_url}{endpoint}"
        headers = self._auth_headers()
        return requests.get(url, headers=headers, stream=stream,
                            timeout=timeout or self.timeout)

    def raw_post(self, endpoint: str, *, files=None, data=None,
                 timeout: int | None = None):
        """Low-level POST that returns the raw ``requests.Response``.

        Use for multipart file uploads.
        """
        url = f"{self.base_url}{endpoint}"
        headers = self._auth_headers()
        return requests.post(url, headers=headers, files=files, data=data,
                             timeout=timeout or self.timeout)

    # ── internals ───────────────────────────────────────────────────

    def _auth_headers(self) -> dict:
        headers: dict[str, str] = {}
        if "auth_token" in session:
            headers["Authorization"] = f"Bearer {session['auth_token']}"
        return headers

    def _request(self, method: str, endpoint: str, data=None, *,
                 use_admin: bool = False, extra_headers: dict | None = None,
                 timeout: int | None = None) -> dict:
        base = self.admin_url if use_admin else self.base_url
        url = f"{base}{endpoint}"
        effective_timeout = timeout or self.timeout

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if extra_headers:
            headers.update(extra_headers)
        headers.update(self._auth_headers())

        try:
            if method == "GET":
                resp = requests.get(url, headers=headers,
                                    timeout=effective_timeout)
            elif method == "POST":
                resp = requests.post(url, json=data, headers=headers,
                                     timeout=effective_timeout)
            elif method == "PUT":
                resp = requests.put(url, json=data, headers=headers,
                                    timeout=effective_timeout)
            elif method == "DELETE":
                resp = requests.delete(url, headers=headers,
                                       timeout=effective_timeout)
            else:
                return {"success": False, "message": "Unsupported method"}

            # Handle permission revocation
            if resp.status_code == 401:
                try:
                    body = resp.json()
                    if body.get("error") == "permissions_changed":
                        session.pop("auth_token", None)
                        session.pop("nav_context", None)
                        session.pop("nav_context_ts", None)
                        return {
                            "success": False,
                            "error": "permissions_changed",
                            "message": body.get(
                                "message",
                                "Your permissions have been updated. "
                                "Please log in again.",
                            ),
                        }
                except ValueError:
                    pass

            if not resp.content:
                return {"success": True}

            try:
                result = resp.json()
                if resp.status_code >= 500 and "message" in result:
                    logger.error("API 5xx for %s: %s", endpoint,
                                 result.get("message", ""))
                    result["message"] = (
                        "A server error occurred. Please try again later."
                    )
                return result
            except ValueError:
                return {
                    "success": False,
                    "message": (
                        f"API returned non-JSON response "
                        f"(HTTP {resp.status_code})"
                    ),
                }

        except requests.exceptions.ConnectTimeout as exc:
            logger.error("Connection timeout for %s: %s", endpoint, exc)
            return {
                "success": False,
                "message": "Request timed out. Please try again.",
            }
        except requests.exceptions.ReadTimeout as exc:
            logger.error("Read timeout for %s: %s", endpoint, exc)
            return {
                "success": False,
                "message": "The request took too long. Please try again.",
            }
        except requests.exceptions.ConnectionError as exc:
            logger.error("Connection failed for %s: %s", endpoint, exc)
            return {
                "success": False,
                "message": (
                    "Unable to reach the API service. "
                    "Please try again later."
                ),
            }
        except requests.exceptions.RequestException as exc:
            logger.error("API request failed for %s: %s", endpoint, exc)
            return {
                "success": False,
                "message": "Something went wrong. Please try again.",
            }


# ── Flask integration ───────────────────────────────────────────────


def init_api_client(app):
    """Create an APIClient and store it on ``app.extensions``."""
    import os

    base = os.environ.get("API_BASE_URL", "http://127.0.0.1:5002/api")
    admin = os.environ.get("ADMIN_API_URL", "http://127.0.0.1:5111/api")
    client = APIClient(base, admin)
    app.extensions["api_client"] = client
    return client


def get_api_client() -> APIClient:
    """Retrieve the APIClient from the current Flask app."""
    return current_app.extensions["api_client"]
