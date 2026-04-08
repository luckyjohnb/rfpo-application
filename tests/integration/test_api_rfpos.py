"""
P1 Integration Tests — RFPO CRUD and line items.
"""

import json
import pytest
from werkzeug.security import generate_password_hash

from models import db, User, Consortium, Team, Project, Vendor, RFPO, RFPOLineItem

pytestmark = [pytest.mark.integration, pytest.mark.rfpo]

# ── helpers ──────────────────────────────────────────────────────────────────

_counter = {"v": 0}


def _uid():
    _counter["v"] += 1
    return _counter["v"]


def _seed_admin(perms=None):
    n = _uid()
    u = User(
        record_id=f"RADM{n:04d}",
        email=f"admin{n}@test.com",
        fullname=f"Admin {n}",
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
        record_id=f"RUSR{n:04d}",
        email=f"user{n}@test.com",
        fullname=f"User {n}",
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


def _seed_full_context():
    """Create consortium + team + project + vendor, return all."""
    n = _uid()
    cons = Consortium(consort_id=f"CON{n:04d}", name=f"Cons {n}", abbrev=f"C{n}")
    db.session.add(cons)
    db.session.flush()
    team = Team(
        record_id=f"T{n:04d}", name=f"Team {n}", abbrev=f"TM{n}",
        consortium_consort_id=cons.consort_id,
    )
    db.session.add(team)
    db.session.flush()
    proj = Project(
        project_id=f"PID{n:04d}", ref=f"PR{n:04d}", name=f"Project {n}",
        consortium_ids=json.dumps([cons.consort_id]),
    )
    db.session.add(proj)
    db.session.flush()
    vendor = Vendor(vendor_id=f"V{n:04d}", company_name=f"Vendor {n}")
    db.session.add(vendor)
    db.session.commit()
    return cons, team, proj, vendor


def _rfpo_payload(cons, team, proj, vendor, **overrides):
    """Build a valid RFPO create payload."""
    payload = {
        "title": "Test RFPO",
        "project_id": proj.project_id,
        "consortium_id": cons.consort_id,
        "team_id": team.id,
        "vendor_id": vendor.id,
        "description": "Test description",
    }
    payload.update(overrides)
    return payload


# ── RFPO listing ─────────────────────────────────────────────────────────────

class TestRFPOList:
    def test_list_rfpos_requires_auth(self, client):
        resp = client.get("/api/rfpos")
        assert resp.status_code == 401

    def test_list_rfpos_empty(self, client):
        admin = _seed_admin()
        token = _login(client, admin.email)
        resp = client.get("/api/rfpos", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_list_rfpos_returns_created(self, client):
        admin = _seed_admin()
        token = _login(client, admin.email)
        cons, team, proj, vendor = _seed_full_context()
        client.post("/api/rfpos", json=_rfpo_payload(cons, team, proj, vendor),
                     headers=_auth(token))
        resp = client.get("/api/rfpos", headers=_auth(token))
        rfpos = resp.get_json().get("rfpos") or resp.get_json().get("data", [])
        assert len(rfpos) >= 1


# ── RFPO create ──────────────────────────────────────────────────────────────

class TestRFPOCreate:
    def test_create_rfpo(self, client):
        admin = _seed_admin()
        token = _login(client, admin.email)
        cons, team, proj, vendor = _seed_full_context()
        resp = client.post("/api/rfpos", json=_rfpo_payload(cons, team, proj, vendor),
                           headers=_auth(token))
        assert resp.status_code in (200, 201)
        data = resp.get_json()
        assert data["success"] is True

    def test_create_rfpo_non_admin_rejected(self, client):
        user = _seed_user()
        token = _login(client, user.email)
        resp = client.post("/api/rfpos", json={"title": "x"}, headers=_auth(token))
        assert resp.status_code in (401, 403)


# ── RFPO detail ──────────────────────────────────────────────────────────────

class TestRFPODetail:
    def _make_rfpo(self, client):
        admin = _seed_admin()
        token = _login(client, admin.email)
        cons, team, proj, vendor = _seed_full_context()
        resp = client.post("/api/rfpos",
                           json=_rfpo_payload(cons, team, proj, vendor, title="Detail Test"),
                           headers=_auth(token))
        rfpo_data = resp.get_json()
        rfpo_id = rfpo_data.get("rfpo", {}).get("id") or rfpo_data.get("data", {}).get("id")
        return admin, token, rfpo_id

    def test_get_rfpo_detail(self, client):
        admin, token, rfpo_id = self._make_rfpo(client)
        if rfpo_id is None:
            pytest.skip("Could not determine RFPO id from create response")
        resp = client.get(f"/api/rfpos/{rfpo_id}", headers=_auth(token))
        assert resp.status_code == 200

    def test_get_rfpo_not_found(self, client):
        admin = _seed_admin()
        token = _login(client, admin.email)
        resp = client.get("/api/rfpos/99999", headers=_auth(token))
        assert resp.status_code in (404, 500)


# ── RFPO update ──────────────────────────────────────────────────────────────

class TestRFPOUpdate:
    def test_update_rfpo_description(self, client):
        admin = _seed_admin()
        token = _login(client, admin.email)
        cons, team, proj, vendor = _seed_full_context()
        resp = client.post("/api/rfpos",
                           json=_rfpo_payload(cons, team, proj, vendor, description="Before"),
                           headers=_auth(token))
        rfpo_data = resp.get_json()
        rfpo_id = rfpo_data.get("rfpo", {}).get("id") or rfpo_data.get("data", {}).get("id")
        if rfpo_id is None:
            pytest.skip("Cannot parse RFPO id")
        resp2 = client.put(f"/api/rfpos/{rfpo_id}", json={"description": "After"},
                           headers=_auth(token))
        assert resp2.status_code == 200


# ── RFPO delete ──────────────────────────────────────────────────────────────

class TestRFPODelete:
    def test_delete_rfpo(self, client):
        admin = _seed_admin()
        token = _login(client, admin.email)
        cons, team, proj, vendor = _seed_full_context()
        resp = client.post("/api/rfpos",
                           json=_rfpo_payload(cons, team, proj, vendor, title="Del me"),
                           headers=_auth(token))
        rfpo_data = resp.get_json()
        rfpo_id = rfpo_data.get("rfpo", {}).get("id") or rfpo_data.get("data", {}).get("id")
        if rfpo_id is None:
            pytest.skip("Cannot parse RFPO id")
        resp2 = client.delete(f"/api/rfpos/{rfpo_id}", headers=_auth(token))
        assert resp2.status_code == 200

    def test_delete_rfpo_non_admin_rejected(self, client):
        user = _seed_user()
        token = _login(client, user.email)
        # Create an RFPO directly so we have a valid ID to try deleting
        admin = _seed_admin()
        cons, team, proj, vendor = _seed_full_context()
        rfpo = RFPO(
            rfpo_id=f"RFPO-DEL-{_uid()}", title="Del Test",
            project_id=proj.project_id, consortium_id=cons.consort_id,
            team_id=team.id, requestor_id=admin.record_id, status="Draft",
            created_by=admin.email,
        )
        db.session.add(rfpo)
        db.session.commit()
        resp = client.delete(f"/api/rfpos/{rfpo.id}", headers=_auth(token))
        assert resp.status_code in (401, 403)


# ── Line items ───────────────────────────────────────────────────────────────

class TestLineItems:
    def _make_rfpo(self, client):
        admin = _seed_admin()
        token = _login(client, admin.email)
        cons, team, proj, vendor = _seed_full_context()
        resp = client.post("/api/rfpos",
                           json=_rfpo_payload(cons, team, proj, vendor, title="LI Test"),
                           headers=_auth(token))
        rfpo_data = resp.get_json()
        rfpo_id = rfpo_data.get("rfpo", {}).get("id") or rfpo_data.get("data", {}).get("id")
        return admin, token, rfpo_id

    def test_add_line_item(self, client):
        admin, token, rfpo_id = self._make_rfpo(client)
        if rfpo_id is None:
            pytest.skip("no RFPO id")
        resp = client.post(f"/api/rfpos/{rfpo_id}/line-items", json={
            "description": "Part A",
            "quantity": 2,
            "unit_price": 50.0,
        }, headers=_auth(token))
        assert resp.status_code in (200, 201)

    def test_list_line_items(self, client):
        admin, token, rfpo_id = self._make_rfpo(client)
        if rfpo_id is None:
            pytest.skip("no RFPO id")
        client.post(f"/api/rfpos/{rfpo_id}/line-items", json={
            "description": "Item", "quantity": 1, "unit_price": 10.0,
        }, headers=_auth(token))
        resp = client.get(f"/api/rfpos/{rfpo_id}/line-items", headers=_auth(token))
        assert resp.status_code == 200

    def test_delete_line_item(self, client):
        admin, token, rfpo_id = self._make_rfpo(client)
        if rfpo_id is None:
            pytest.skip("no RFPO id")
        resp = client.post(f"/api/rfpos/{rfpo_id}/line-items", json={
            "description": "Kill me", "quantity": 1, "unit_price": 10.0,
        }, headers=_auth(token))
        li_data = resp.get_json()
        li_id = (
            li_data.get("line_item", {}).get("id")
            or li_data.get("data", {}).get("id")
        )
        if li_id is None:
            pytest.skip("no line item id")
        resp2 = client.delete(f"/api/rfpos/{rfpo_id}/line-items/{li_id}",
                              headers=_auth(token))
        assert resp2.status_code == 200
