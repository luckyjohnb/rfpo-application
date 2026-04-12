"""
Integration test fixtures — extends root conftest.

Provides a live Flask test client pointing at simple_api.py routes
with an in-memory SQLite database.
"""

import os
import sys
import unittest.mock as mock
import pytest

# Force test database BEFORE simple_api.py is imported (module-level app)
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-unit-tests"
os.environ["API_SECRET_KEY"] = "test-api-secret"
os.environ["ADMIN_SECRET_KEY"] = "test-admin-secret"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Patch Flask config __setitem__ to drop pool_size/pool_recycle for SQLite
_orig_flask_config_setitem = None


def _patch_engine_options():
    """Intercept SQLALCHEMY_ENGINE_OPTIONS and strip pool args for SQLite."""
    from flask import Config as FlaskConfig

    _orig = FlaskConfig.__setitem__

    def _filtered_setitem(self, key, value):
        if key == "SQLALCHEMY_ENGINE_OPTIONS" and isinstance(value, dict):
            value = {k: v for k, v in value.items()
                     if k not in ("pool_size", "pool_recycle", "max_overflow")}
        return _orig(self, key, value)

    FlaskConfig.__setitem__ = _filtered_setitem


_patch_engine_options()

import simple_api  # noqa: E402 — must come after env + patch
from models import db  # noqa: E402


@pytest.fixture(scope="session")
def live_app():
    """The actual simple_api Flask app configured for testing."""
    simple_api.app.config["TESTING"] = True
    simple_api.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    # Remove pool options that are invalid for SQLite
    opts = simple_api.app.config.get("SQLALCHEMY_ENGINE_OPTIONS", {})
    for k in ("pool_size", "pool_recycle", "max_overflow"):
        opts.pop(k, None)
    simple_api.app.config["SQLALCHEMY_ENGINE_OPTIONS"] = opts
    with simple_api.app.app_context():
        db.create_all()
    yield simple_api.app


@pytest.fixture(autouse=True)
def live_db_cleanup(live_app):
    """Clean integration test DB after each test."""
    with live_app.app_context():
        yield db.session
        db.session.rollback()
        from models import (
            RFPOApprovalAction, RFPOApprovalInstance,
            RFPOApprovalStep, RFPOApprovalStage, RFPOApprovalWorkflow,
            EmailLog, Notification, AuditLog,
            UploadedFile, RFPOLineItem, RFPO,
            UserTeam, VendorSite, Vendor, Project, Team, Consortium, User,
            Ticket, TicketComment, TicketAttachment,
        )
        for model in [
            TicketAttachment, TicketComment, Ticket,
            RFPOApprovalAction, RFPOApprovalInstance,
            RFPOApprovalStep, RFPOApprovalStage, RFPOApprovalWorkflow,
            EmailLog, Notification, AuditLog,
            UploadedFile, RFPOLineItem, RFPO,
            UserTeam, VendorSite, Vendor, Project, Team, Consortium, User,
        ]:
            try:
                model.query.delete()
            except Exception:
                db.session.rollback()
        db.session.commit()


@pytest.fixture
def client(live_app):
    """Flask test client for integration tests."""
    return live_app.test_client()
