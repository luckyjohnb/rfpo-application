"""
Shared test fixtures for RFPO application.

Provides Flask test apps (API, Admin), database setup with transaction
rollback, pre-created entities, and JWT helpers for authenticated requests.
"""

import os
import sys
import json
import pytest
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test-safe env vars BEFORE any app code imports
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-unit-tests")
os.environ.setdefault("API_SECRET_KEY", "test-api-secret")
os.environ.setdefault("ADMIN_SECRET_KEY", "test-admin-secret")
os.environ.setdefault("FLASK_ENV", "testing")

import jwt as pyjwt
from flask import Flask
from models import (
    db,
    User,
    Consortium,
    RFPO,
    RFPOLineItem,
    UploadedFile,
    Team,
    UserTeam,
    Project,
    Vendor,
    VendorSite,
    PDFPositioning,
    List,
    RFPOApprovalWorkflow,
    RFPOApprovalStage,
    RFPOApprovalStep,
    RFPOApprovalInstance,
    RFPOApprovalAction,
    AuditLog,
    Notification,
    EmailLog,
)

# The JWT secret used by tests — matches what we set in env
TEST_JWT_SECRET = "test-jwt-secret-key-for-unit-tests"


# ---------------------------------------------------------------------------
# App factories
# ---------------------------------------------------------------------------

def _create_api_app():
    """Create a minimal Flask app that mirrors simple_api.py for testing.

    We can't just import simple_api because it creates the app at module level
    and triggers db.create_all() against the real database path.  Instead we
    build a fresh app and register the key routes we need.
    """
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-api-secret"
    db.init_app(app)
    return app


def _create_admin_app():
    """Create admin app with in-memory DB for testing."""
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-admin-secret"
    app.config["WTF_CSRF_ENABLED"] = False
    db.init_app(app)
    return app


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app():
    """Session-scoped Flask test app with in-memory SQLite."""
    application = _create_api_app()
    with application.app_context():
        db.create_all()
    yield application


@pytest.fixture(scope="session")
def admin_app():
    """Session-scoped admin Flask test app."""
    application = _create_admin_app()
    with application.app_context():
        db.create_all()
    yield application


@pytest.fixture(autouse=True)
def db_cleanup(app):
    """Clean up all table data after each test.

    Uses delete (not drop) to preserve schema across the session.
    """
    with app.app_context():
        yield db.session
        db.session.rollback()
        # Delete in dependency order to avoid FK violations
        for model in [
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
def api_client(app):
    """Flask test client for API requests."""
    return app.test_client()


@pytest.fixture
def admin_client(admin_app):
    """Flask test client for admin panel requests."""
    return admin_app.test_client()


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------

_counter = {"user": 0, "consortium": 0, "team": 0, "project": 0, "vendor": 0, "rfpo": 0}


def _next(key):
    _counter[key] += 1
    return _counter[key]


@pytest.fixture
def admin_user(db_cleanup):
    """Pre-created admin user with GOD permission."""
    n = _next("user")
    user = User(
        record_id=f"UADM{n:04d}",
        email=f"admin{n}@test.com",
        fullname="Test Admin",
        password_hash=generate_password_hash("admin123"),
        active=True,
    )
    user.set_permissions(["GOD"])
    db.session.add(user)
    db.session.flush()
    return user


@pytest.fixture
def regular_user(db_cleanup):
    """Pre-created regular user with RFPO_USER permission."""
    n = _next("user")
    user = User(
        record_id=f"UREG{n:04d}",
        email=f"user{n}@test.com",
        fullname="Regular User",
        password_hash=generate_password_hash("user123"),
        active=True,
    )
    user.set_permissions(["RFPO_USER"])
    db.session.add(user)
    db.session.flush()
    return user


@pytest.fixture
def approver_user(db_cleanup):
    """Pre-created approver user."""
    n = _next("user")
    user = User(
        record_id=f"UAPR{n:04d}",
        email=f"approver{n}@test.com",
        fullname="Test Approver",
        password_hash=generate_password_hash("approver123"),
        active=True,
        is_approver=True,
    )
    user.set_permissions(["RFPO_USER"])
    db.session.add(user)
    db.session.flush()
    return user


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def make_auth_headers(user, expired=False):
    """Build Authorization headers with a JWT for the given user."""
    exp = datetime.utcnow() + (timedelta(hours=-1) if expired else timedelta(hours=24))
    token = pyjwt.encode(
        {"user_id": user.id, "pv": getattr(user, "permissions_version", 0) or 0, "exp": exp},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture
def auth_headers(admin_user):
    """JWT auth headers for the admin user."""
    return make_auth_headers(admin_user)


@pytest.fixture
def user_auth_headers(regular_user):
    """JWT auth headers for a regular user."""
    return make_auth_headers(regular_user)


@pytest.fixture
def expired_auth_headers(admin_user):
    """Expired JWT auth headers — should be rejected."""
    return make_auth_headers(admin_user, expired=True)


# ---------------------------------------------------------------------------
# Entity fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_consortium(db_cleanup):
    """Pre-created consortium."""
    n = _next("consortium")
    c = Consortium(
        consort_id=f"C{n:04d}",
        name=f"Test Consortium {n}",
        abbrev=f"TC{n}",
    )
    db.session.add(c)
    db.session.flush()
    return c


@pytest.fixture
def sample_team(db_cleanup, sample_consortium):
    """Pre-created team linked to sample_consortium."""
    n = _next("team")
    t = Team(
        record_id=f"T{n:04d}",
        name=f"Test Team {n}",
        abbrev=f"TT{n}",
        consortium_consort_id=sample_consortium.consort_id,
    )
    db.session.add(t)
    db.session.flush()
    return t


@pytest.fixture
def sample_project(db_cleanup, sample_consortium):
    """Pre-created project linked to sample_consortium."""
    n = _next("project")
    p = Project(
        project_id=f"P{n:04d}",
        name=f"Test Project {n}",
        ref=f"TP{n:04d}",
    )
    p.set_consortium_ids([sample_consortium.consort_id])
    db.session.add(p)
    db.session.flush()
    return p


@pytest.fixture
def sample_vendor(db_cleanup):
    """Pre-created vendor."""
    n = _next("vendor")
    v = Vendor(
        vendor_id=f"V{n:04d}",
        company_name=f"Test Vendor {n}",
    )
    db.session.add(v)
    db.session.flush()
    return v


@pytest.fixture
def sample_rfpo(db_cleanup, sample_consortium, sample_team, sample_project, sample_vendor, admin_user):
    """Pre-created RFPO with one line item."""
    n = _next("rfpo")
    rfpo = RFPO(
        rfpo_id=f"RFPO-{n:06d}",
        title=f"Test RFPO {n}",
        consortium_id=sample_consortium.consort_id,
        team_id=sample_team.id,
        project_id=sample_project.project_id,
        vendor_id=sample_vendor.id,
        requestor_id=admin_user.record_id,
        status="draft",
        created_by=admin_user.record_id,
    )
    db.session.add(rfpo)
    db.session.flush()

    line = RFPOLineItem(
        rfpo_id=rfpo.id,
        description="Test item",
        quantity=2,
        unit_price=100.00,
        total_price=200.00,
        line_number=1,
    )
    db.session.add(line)
    db.session.flush()
    rfpo.update_totals()
    db.session.flush()
    return rfpo


# ---------------------------------------------------------------------------
# Mock services
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_email_service(monkeypatch):
    """Patch email service so no real SMTP/ACS calls are made."""
    from unittest.mock import MagicMock

    mock = MagicMock()
    mock.send_email.return_value = {"success": True}
    monkeypatch.setattr("email_service.EmailService.send_email", mock.send_email)
    return mock
