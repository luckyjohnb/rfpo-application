"""
P0 Unit Tests — API utilities.

Covers format_response, validate_required_fields, generate_next_id,
and permission-check helper functions.
"""

import pytest
from flask import Flask
from unittest.mock import MagicMock

from models import db, User, Consortium
from api.utils import (
    format_response,
    validate_required_fields,
    generate_next_id,
    is_system_admin,
    is_team_admin,
    is_limited_admin,
    error_response,
)

pytestmark = pytest.mark.unit


# ── format_response ──────────────────────────────────────────────────────

class TestFormatResponse:
    def test_success_default(self, app):
        with app.test_request_context():
            resp, code = format_response()
            assert code == 200
            data = resp.get_json()
            assert data["success"] is True

    def test_with_data(self, app):
        with app.test_request_context():
            resp, code = format_response(data={"items": [1, 2]})
            data = resp.get_json()
            assert data["items"] == [1, 2]

    def test_with_message(self, app):
        with app.test_request_context():
            resp, code = format_response(success=False, message="bad", status_code=400)
            assert code == 400
            assert resp.get_json()["message"] == "bad"


# ── validate_required_fields ─────────────────────────────────────────────

class TestValidateRequiredFields:
    def test_all_present(self):
        result = validate_required_fields(
            {"name": "x", "email": "y"}, ["name", "email"]
        )
        assert result is None

    def test_missing_field(self):
        result = validate_required_fields({"name": "x"}, ["name", "email"])
        assert result is not None
        assert "email" in result

    def test_empty_value_detected(self):
        result = validate_required_fields({"name": ""}, ["name"])
        assert result is not None


# ── generate_next_id ─────────────────────────────────────────────────────

class TestGenerateNextId:
    def test_first_id(self, app):
        """When no records exist, should return '00000001'."""
        result = generate_next_id(Consortium, "consort_id")
        assert result == "00000001"

    def test_increments(self, app):
        c = Consortium(consort_id="00000001", name="A", abbrev="A")
        db.session.add(c)
        db.session.flush()
        result = generate_next_id(Consortium, "consort_id")
        assert result == "00000002"

    def test_prefix(self, app):
        result = generate_next_id(Consortium, "consort_id", prefix="C")
        assert result.startswith("C")


# ── Permission helpers ───────────────────────────────────────────────────

class TestPermissionHelpers:
    def _mock_user(self, perms):
        u = MagicMock()
        u.get_permissions.return_value = perms
        return u

    def test_is_system_admin_true(self):
        assert is_system_admin(self._mock_user(["GOD"])) is True

    def test_is_system_admin_false(self):
        assert is_system_admin(self._mock_user(["RFPO_USER"])) is False

    def test_is_team_admin(self):
        assert is_team_admin(self._mock_user(["RFPO_ADMIN"])) is True
        assert is_team_admin(self._mock_user(["GOD"])) is True
        assert is_team_admin(self._mock_user(["RFPO_USER"])) is False

    def test_is_limited_admin(self):
        assert is_limited_admin(self._mock_user(["RFPO_USER"])) is True
        assert is_limited_admin(self._mock_user([])) is False


# ── error_response ───────────────────────────────────────────────────────

class TestErrorResponse:
    def test_returns_500(self, app):
        with app.test_request_context():
            resp, code = error_response(Exception("boom"))
            assert code == 500
            assert resp.get_json()["success"] is False
