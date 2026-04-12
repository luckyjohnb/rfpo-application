"""
Integration tests — Admin RFPO Explorer endpoints.

Tests the /reports/explorer (JSON) and /reports/explorer/csv endpoints
that power the ad-hoc query builder in the admin panel.
"""

import json
import os
import sys

import pytest
from werkzeug.security import generate_password_hash

# Force test database
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ADMIN_SECRET_KEY", "test-admin-secret-key-1234567890ab")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from models import db, User, Consortium, Team, Project, Vendor, RFPO

pytestmark = [pytest.mark.integration]

_ctr = {"v": 0}


def _uid():
    _ctr["v"] += 1
    return _ctr["v"]


@pytest.fixture(scope="module")
def admin_app():
    """Create admin Flask app for testing."""
    # Patch Flask config to strip pool args for SQLite
    from flask import Config as FC
    _orig = FC.__setitem__

    def _filtered(self, key, value):
        if key == "SQLALCHEMY_ENGINE_OPTIONS" and isinstance(value, dict):
            value = {k: v for k, v in value.items()
                     if k not in ("pool_size", "pool_recycle", "max_overflow")}
        return _orig(self, key, value)

    FC.__setitem__ = _filtered

    from custom_admin import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["LOGIN_DISABLED"] = True  # bypass @login_required

    with app.app_context():
        db.create_all()
    yield app

    FC.__setitem__ = _orig


@pytest.fixture()
def client(admin_app):
    with admin_app.test_client() as c:
        with admin_app.app_context():
            yield c
            db.session.rollback()
            # Clean up
            for model in [RFPO, Vendor, Project, Team, Consortium, User]:
                model.query.delete()
            db.session.commit()


def _seed(client_ctx):
    """Seed basic test data: admin user, consortium, team, project, vendor, 3 RFPOs."""
    from datetime import datetime, timedelta
    n = _uid()
    admin = User(
        record_id=f"EXPL_ADM{n:04d}",
        email=f"expladm{n}@test.com",
        fullname=f"Explorer Admin {n}",
        password_hash=generate_password_hash("pass"),
        active=True,
    )
    admin.set_permissions(["GOD"])
    db.session.add(admin)

    cons = Consortium(consort_id=f"ECON{n:04d}", name=f"ExplCons {n}", abbrev=f"EC{n}", active=True)
    db.session.add(cons)
    db.session.flush()

    team = Team(record_id=f"ET{n:04d}", name=f"ExplTeam {n}", abbrev=f"ETM{n}",
                consortium_consort_id=cons.consort_id, active=True)
    db.session.add(team)
    db.session.flush()

    proj = Project(project_id=f"EPID{n:04d}", ref=f"EP{n:04d}", name=f"ExplProject {n}",
                   consortium_ids=json.dumps([cons.consort_id]), active=True)
    db.session.add(proj)
    db.session.flush()

    vendor = Vendor(vendor_id=f"EV{n:04d}", company_name=f"ExplVendor {n}", active=True)
    db.session.add(vendor)
    db.session.flush()

    now = datetime.utcnow()
    rfpos = []
    for i, (status, amt) in enumerate([
        ("Draft", 100.0),
        ("Pending Approval", 250.0),
        ("Approved", 500.0),
    ]):
        rfpo = RFPO(
            rfpo_id=f"RFPO-EC{n:04d}-2025-01-01-N{i+1:02d}",
            title=f"Explorer RFPO {i+1}",
            project_id=proj.project_id,
            consortium_id=cons.consort_id,
            team_id=team.id,
            requestor_id=admin.record_id,
            vendor_id=vendor.id,
            total_amount=amt,
            status=status,
            created_by=admin.fullname,
            created_at=now - timedelta(days=10 - i),
        )
        if status == "Approved":
            rfpo.approved_at = now - timedelta(days=2)
            rfpo.po_number = f"PO-EC{n}-001"
            rfpo.cost_share_amount = 50.0
        db.session.add(rfpo)
        rfpos.append(rfpo)

    db.session.commit()
    return {"admin": admin, "consortium": cons, "team": team,
            "project": proj, "vendor": vendor, "rfpos": rfpos}


class TestExplorerEndpoint:
    """Tests for /reports/explorer JSON endpoint."""

    def test_returns_all_rfpos(self, client):
        ctx = _seed(client)
        resp = client.get("/reports/explorer")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["result_count"] == 3
        assert len(data["rfpos"]) == 3

    def test_filter_by_status(self, client):
        ctx = _seed(client)
        resp = client.get("/reports/explorer?status=Approved")
        data = resp.get_json()
        assert data["result_count"] == 1
        assert data["rfpos"][0]["status"] == "Approved"

    def test_filter_by_consortium(self, client):
        ctx = _seed(client)
        resp = client.get(f"/reports/explorer?consortium_id={ctx['consortium'].consort_id}")
        data = resp.get_json()
        assert data["result_count"] == 3

    def test_filter_by_vendor(self, client):
        ctx = _seed(client)
        resp = client.get(f"/reports/explorer?vendor_id={ctx['vendor'].id}")
        data = resp.get_json()
        assert data["result_count"] == 3

    def test_filter_by_amount_range(self, client):
        ctx = _seed(client)
        resp = client.get("/reports/explorer?amount_min=200&amount_max=600")
        data = resp.get_json()
        assert data["result_count"] == 2
        for r in data["rfpos"]:
            assert 200 <= r["total_amount"] <= 600

    def test_filter_by_cost_sharing_yes(self, client):
        ctx = _seed(client)
        resp = client.get("/reports/explorer?cost_sharing=yes")
        data = resp.get_json()
        assert data["result_count"] == 1
        assert data["rfpos"][0]["status"] == "Approved"

    def test_filter_by_cost_sharing_no(self, client):
        ctx = _seed(client)
        resp = client.get("/reports/explorer?cost_sharing=no")
        data = resp.get_json()
        assert data["result_count"] == 2

    def test_filter_by_po_number(self, client):
        ctx = _seed(client)
        po = ctx["rfpos"][2].po_number
        resp = client.get(f"/reports/explorer?po_number={po}")
        data = resp.get_json()
        assert data["result_count"] == 1

    def test_filter_by_search(self, client):
        ctx = _seed(client)
        rfpo_id = ctx["rfpos"][0].rfpo_id
        resp = client.get(f"/reports/explorer?search={rfpo_id}")
        data = resp.get_json()
        assert data["result_count"] == 1
        assert data["rfpos"][0]["rfpo_id"] == rfpo_id

    def test_sort_by_amount_asc(self, client):
        ctx = _seed(client)
        resp = client.get("/reports/explorer?sort_by=total_amount&sort_dir=asc")
        data = resp.get_json()
        amounts = [r["total_amount"] for r in data["rfpos"]]
        assert amounts == sorted(amounts)

    def test_pagination(self, client):
        ctx = _seed(client)
        resp = client.get("/reports/explorer?per_page=2&page=1")
        data = resp.get_json()
        assert len(data["rfpos"]) == 2
        assert data["pages"] == 2
        assert data["page"] == 1

    def test_result_total_reflects_filters(self, client):
        ctx = _seed(client)
        resp = client.get("/reports/explorer?status=Approved")
        data = resp.get_json()
        assert data["result_total"] == 500.0

    def test_invalid_sort_falls_back(self, client):
        ctx = _seed(client)
        resp = client.get("/reports/explorer?sort_by=invalid_col")
        assert resp.status_code == 200


class TestExplorerCSV:
    """Tests for /reports/explorer/csv endpoint."""

    def test_csv_download(self, client):
        ctx = _seed(client)
        resp = client.get("/reports/explorer/csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.content_type
        assert "attachment" in resp.headers.get("Content-Disposition", "")
        lines = resp.data.decode("utf-8").strip().split("\n")
        # header + 3 data rows
        assert len(lines) == 4

    def test_csv_filtered(self, client):
        ctx = _seed(client)
        resp = client.get("/reports/explorer/csv?status=Approved")
        lines = resp.data.decode("utf-8").strip().split("\n")
        assert len(lines) == 2  # header + 1 row

    def test_csv_header_columns(self, client):
        ctx = _seed(client)
        resp = client.get("/reports/explorer/csv")
        header = resp.data.decode("utf-8").split("\n")[0].strip()
        assert "RFPO ID" in header
        assert "Total Amount" in header
        assert "Vendor" in header
