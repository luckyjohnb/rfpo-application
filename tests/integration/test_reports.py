"""
P1 Integration Tests — Report endpoints and ad-hoc RFPO filters.
"""

import json
from datetime import datetime, timedelta

import pytest
from werkzeug.security import generate_password_hash

from models import (
    db, User, Consortium, Team, Project, Vendor,
    RFPO, RFPOLineItem, RFPOApprovalWorkflow, RFPOApprovalStage,
    RFPOApprovalStep, RFPOApprovalInstance, RFPOApprovalAction,
)

pytestmark = [pytest.mark.integration, pytest.mark.reports]

# ── helpers ──────────────────────────────────────────────────────────────────

_counter = {"v": 0}


def _uid():
    _counter["v"] += 1
    return _counter["v"]


def _seed_admin(perms=None):
    n = _uid()
    u = User(
        record_id=f"RPT_ADM{n:04d}",
        email=f"rptadmin{n}@test.com",
        fullname=f"Report Admin {n}",
        password_hash=generate_password_hash("pass"),
        active=True,
    )
    u.set_permissions(perms or ["GOD"])
    db.session.add(u)
    db.session.commit()
    return u


def _seed_user(perms=None):
    n = _uid()
    u = User(
        record_id=f"RPT_USR{n:04d}",
        email=f"rptuser{n}@test.com",
        fullname=f"Report User {n}",
        password_hash=generate_password_hash("pass"),
        active=True,
    )
    u.set_permissions(perms or ["RFPO_USER"])
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, email):
    resp = client.post("/api/auth/login", json={"username": email, "password": "pass"})
    return resp.get_json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _seed_context():
    """Seed consortium + team + project + vendor + 3 RFPOs at various statuses."""
    n = _uid()
    cons = Consortium(consort_id=f"RCON{n:04d}", name=f"RptCons {n}", abbrev=f"RC{n}")
    db.session.add(cons)
    db.session.flush()

    team = Team(
        record_id=f"RT{n:04d}", name=f"RptTeam {n}", abbrev=f"RTM{n}",
        consortium_consort_id=cons.consort_id,
    )
    db.session.add(team)
    db.session.flush()

    proj = Project(
        project_id=f"RPID{n:04d}", ref=f"RP{n:04d}", name=f"RptProject {n}",
        consortium_ids=json.dumps([cons.consort_id]),
    )
    db.session.add(proj)
    db.session.flush()

    vendor = Vendor(vendor_id=f"RV{n:04d}", company_name=f"RptVendor {n}")
    db.session.add(vendor)
    db.session.flush()

    admin = _seed_admin()

    now = datetime.utcnow()
    rfpos = []
    for i, (status, amt) in enumerate([
        ("Draft", 100.00),
        ("Pending Approval", 250.00),
        ("Approved", 500.00),
    ]):
        rfpo = RFPO(
            rfpo_id=f"RFPO-RP{n:04d}-2025-01-01-N{i+1:02d}",
            title=f"Report Test RFPO {i+1}",
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
            rfpo.po_number = f"PO-RC{n}-001"
        db.session.add(rfpo)
        rfpos.append(rfpo)

    db.session.commit()
    return {
        "consortium": cons, "team": team, "project": proj,
        "vendor": vendor, "admin": admin, "rfpos": rfpos,
    }


# ── Auth Tests ───────────────────────────────────────────────────────────────

class TestReportAuth:
    """Report endpoints should require GOD or RFPO_ADMIN permission."""

    def test_reports_rfpos_requires_auth(self, client):
        resp = client.get("/api/reports/rfpos?report_type=summary")
        assert resp.status_code in (401, 403)

    def test_reports_rfpos_denied_for_regular_user(self, client):
        user = _seed_user(["RFPO_USER"])
        token = _login(client, user.email)
        resp = client.get(
            "/api/reports/rfpos?report_type=summary",
            headers=_auth(token),
        )
        assert resp.status_code == 403

    def test_reports_rfpos_allowed_for_god(self, client):
        ctx = _seed_context()
        token = _login(client, ctx["admin"].email)
        resp = client.get(
            "/api/reports/rfpos?report_type=summary",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_reports_rfpos_allowed_for_rfpo_admin(self, client):
        admin = _seed_admin(["RFPO_ADMIN"])
        token = _login(client, admin.email)
        resp = client.get(
            "/api/reports/rfpos?report_type=summary",
            headers=_auth(token),
        )
        assert resp.status_code == 200


# ── RFPO Report Tests ────────────────────────────────────────────────────────

class TestRFPOReports:
    """Verify /api/reports/rfpos endpoint outputs."""

    def test_summary_report(self, client):
        ctx = _seed_context()
        token = _login(client, ctx["admin"].email)
        resp = client.get(
            "/api/reports/rfpos?report_type=summary",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "all_rfpos" in data
        assert data["all_rfpos"]["count"] >= 3

    def test_summary_with_group_by(self, client):
        ctx = _seed_context()
        token = _login(client, ctx["admin"].email)
        # group_by is a drilldown param, summary ignores it — just verify summary still works
        resp = client.get(
            "/api/reports/rfpos?report_type=summary&group_by=consortium",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "all_rfpos" in data

    def test_drilldown_report(self, client):
        ctx = _seed_context()
        token = _login(client, ctx["admin"].email)
        resp = client.get(
            "/api/reports/rfpos?report_type=drilldown&group_by=vendor",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "groups" in data
        assert len(data["groups"]) >= 1

    def test_time_to_fulfill_report(self, client):
        ctx = _seed_context()
        token = _login(client, ctx["admin"].email)
        resp = client.get(
            "/api/reports/rfpos?report_type=time_to_fulfill",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "average_days" in data

    def test_rejected_by_category_report(self, client):
        ctx = _seed_context()
        token = _login(client, ctx["admin"].email)
        resp = client.get(
            "/api/reports/rfpos?report_type=rejected_by_category",
            headers=_auth(token),
        )
        assert resp.status_code == 200

    def test_invalid_report_type(self, client):
        admin = _seed_admin()
        token = _login(client, admin.email)
        resp = client.get(
            "/api/reports/rfpos?report_type=bogus",
            headers=_auth(token),
        )
        assert resp.status_code == 400

    def test_date_range_filter(self, client):
        ctx = _seed_context()
        token = _login(client, ctx["admin"].email)
        today = datetime.utcnow().strftime("%Y-%m-%d")
        resp = client.get(
            f"/api/reports/rfpos?report_type=summary&date_from=2020-01-01&date_to={today}",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["all_rfpos"]["count"] >= 3


# ── Approval Report Tests ────────────────────────────────────────────────────

class TestApprovalReports:

    def test_busiest_approvers(self, client):
        admin = _seed_admin()
        token = _login(client, admin.email)
        resp = client.get(
            "/api/reports/approvals?report_type=busiest_approvers",
            headers=_auth(token),
        )
        assert resp.status_code == 200

    def test_pending_queue(self, client):
        admin = _seed_admin()
        token = _login(client, admin.email)
        resp = client.get(
            "/api/reports/approvals?report_type=pending_queue",
            headers=_auth(token),
        )
        assert resp.status_code == 200

    def test_overdue_report(self, client):
        admin = _seed_admin()
        token = _login(client, admin.email)
        resp = client.get(
            "/api/reports/approvals?report_type=overdue",
            headers=_auth(token),
        )
        assert resp.status_code == 200

    def test_invalid_approval_report_type(self, client):
        admin = _seed_admin()
        token = _login(client, admin.email)
        resp = client.get(
            "/api/reports/approvals?report_type=bogus",
            headers=_auth(token),
        )
        assert resp.status_code == 400


# ── Vendor Report Tests ──────────────────────────────────────────────────────

class TestVendorReports:

    def test_top_by_volume(self, client):
        ctx = _seed_context()
        token = _login(client, ctx["admin"].email)
        resp = client.get(
            "/api/reports/vendors?report_type=top_by_volume",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "vendors" in data

    def test_certifications_report(self, client):
        admin = _seed_admin()
        token = _login(client, admin.email)
        resp = client.get(
            "/api/reports/vendors?report_type=certifications",
            headers=_auth(token),
        )
        assert resp.status_code == 200


# ── Email Health Report Tests ────────────────────────────────────────────────

class TestEmailHealthReports:

    def test_email_health(self, client):
        admin = _seed_admin()
        token = _login(client, admin.email)
        resp = client.get(
            "/api/reports/email-health",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "total_sent" in data


# ── Ad-hoc Filter Tests (list_rfpos) ─────────────────────────────────────────

class TestAdHocFilters:
    """Verify the new ad-hoc filters on /api/rfpos."""

    def test_filter_by_vendor_id(self, client):
        ctx = _seed_context()
        token = _login(client, ctx["admin"].email)
        resp = client.get(
            f"/api/rfpos?vendor_id={ctx['vendor'].id}",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] >= 3

    def test_filter_by_consortium_id(self, client):
        ctx = _seed_context()
        token = _login(client, ctx["admin"].email)
        resp = client.get(
            f"/api/rfpos?consortium_id={ctx['consortium'].consort_id}",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["total"] >= 3

    def test_filter_by_amount_range(self, client):
        ctx = _seed_context()
        token = _login(client, ctx["admin"].email)
        resp = client.get(
            "/api/rfpos?amount_min=200&amount_max=600",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        rfpos = resp.get_json()["rfpos"]
        for r in rfpos:
            assert 200 <= r["total_amount"] <= 600

    def test_filter_by_po_number(self, client):
        ctx = _seed_context()
        token = _login(client, ctx["admin"].email)
        # approved RFPO has a po_number
        resp = client.get(
            f"/api/rfpos?po_number=PO-RC",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["total"] >= 1

    def test_filter_cost_sharing_yes(self, client):
        ctx = _seed_context()
        # Add cost sharing to one RFPO
        rfpo = ctx["rfpos"][0]
        rfpo.cost_share_amount = 50.00
        db.session.commit()

        token = _login(client, ctx["admin"].email)
        resp = client.get(
            "/api/rfpos?cost_sharing=yes",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["total"] >= 1

    def test_sort_by_total_amount_asc(self, client):
        ctx = _seed_context()
        token = _login(client, ctx["admin"].email)
        resp = client.get(
            "/api/rfpos?sort_by=total_amount&sort_dir=asc",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        rfpos = resp.get_json()["rfpos"]
        if len(rfpos) >= 2:
            assert rfpos[0]["total_amount"] <= rfpos[-1]["total_amount"]

    def test_sort_by_invalid_field_falls_back(self, client):
        ctx = _seed_context()
        token = _login(client, ctx["admin"].email)
        resp = client.get(
            "/api/rfpos?sort_by=DROP_TABLE&sort_dir=asc",
            headers=_auth(token),
        )
        # Should fall back to created_at, not error
        assert resp.status_code == 200

    def test_filter_by_requestor_id(self, client):
        ctx = _seed_context()
        token = _login(client, ctx["admin"].email)
        resp = client.get(
            f"/api/rfpos?requestor_id={ctx['admin'].record_id}",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["total"] >= 3

    def test_filter_by_project_id(self, client):
        ctx = _seed_context()
        token = _login(client, ctx["admin"].email)
        resp = client.get(
            f"/api/rfpos?project_id={ctx['project'].project_id}",
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["total"] >= 3
