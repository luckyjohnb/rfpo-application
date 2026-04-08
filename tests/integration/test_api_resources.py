"""
P1 Integration Tests — Consortiums, Teams, Projects, and Vendors.
"""

import pytest
from werkzeug.security import generate_password_hash

from models import db, User, Consortium, Team, Project, Vendor

pytestmark = [pytest.mark.integration]

_counter = {"v": 0}


def _uid():
    _counter["v"] += 1
    return _counter["v"]


def _make_user(perms=None):
    n = _uid()
    u = User(
        record_id=f"UCVT{n:04d}",
        email=f"cvt{n}@test.com",
        fullname=f"User {n}",
        password_hash=generate_password_hash("pass"),
        active=True,
    )
    u.set_permissions(perms or ["RFPO_USER"])
    db.session.add(u)
    db.session.commit()
    return u


def _admin():
    return _make_user(["GOD"])


def _login(client, email):
    return client.post(
        "/api/auth/login", json={"username": email, "password": "pass"}
    ).get_json()["token"]


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


# ── Consortiums ──────────────────────────────────────────────────────────────

class TestConsortiums:
    def test_list_consortiums(self, client):
        admin = _admin()
        tok = _login(client, admin.email)
        resp = client.get("/api/consortiums", headers=_auth(tok))
        assert resp.status_code == 200

    def test_create_consortium_admin(self, client):
        admin = _admin()
        tok = _login(client, admin.email)
        resp = client.post("/api/consortiums", json={
            "name": "Test Consortium",
            "abbrev": "TC",
        }, headers=_auth(tok))
        assert resp.status_code in (200, 201)

    def test_create_consortium_non_admin(self, client):
        user = _make_user()
        tok = _login(client, user.email)
        resp = client.post("/api/consortiums", json={
            "name": "Bad", "abbrev": "BD",
        }, headers=_auth(tok))
        assert resp.status_code in (401, 403)

    def test_list_consortiums_requires_auth(self, client):
        resp = client.get("/api/consortiums")
        assert resp.status_code == 401


# ── Teams ────────────────────────────────────────────────────────────────────

class TestTeams:
    def test_list_teams(self, client):
        admin = _admin()
        tok = _login(client, admin.email)
        resp = client.get("/api/teams", headers=_auth(tok))
        assert resp.status_code == 200

    def test_create_team(self, client):
        admin = _admin()
        tok = _login(client, admin.email)
        n = _uid()
        cons = Consortium(consort_id=f"CTM{n:04d}", name=f"C {n}", abbrev=f"CTM{n}")
        db.session.add(cons)
        db.session.commit()
        resp = client.post("/api/teams", json={
            "name": f"Team {n}",
            "abbrev": f"TM{n}",
            "consortium_id": cons.consort_id,
        }, headers=_auth(tok))
        assert resp.status_code in (200, 201)

    def test_create_team_non_admin(self, client):
        user = _make_user()
        tok = _login(client, user.email)
        resp = client.post("/api/teams", json={
            "name": "Bad Team", "abbrev": "BT",
        }, headers=_auth(tok))
        assert resp.status_code in (401, 403)

    def test_get_team_detail(self, client):
        admin = _admin()
        tok = _login(client, admin.email)
        n = _uid()
        cons = Consortium(consort_id=f"CTD{n:04d}", name=f"C {n}", abbrev=f"CTD{n}")
        db.session.add(cons)
        db.session.flush()
        team = Team(record_id=f"TTD{n:04d}", name=f"T {n}", abbrev=f"TD{n}",
                    consortium_consort_id=cons.consort_id)
        db.session.add(team)
        db.session.commit()
        resp = client.get(f"/api/teams/{team.id}", headers=_auth(tok))
        assert resp.status_code == 200

    def test_get_team_not_found(self, client):
        admin = _admin()
        tok = _login(client, admin.email)
        resp = client.get("/api/teams/99999", headers=_auth(tok))
        assert resp.status_code == 404


# ── Projects ─────────────────────────────────────────────────────────────────

class TestProjects:
    def test_list_projects(self, client):
        admin = _admin()
        tok = _login(client, admin.email)
        resp = client.get("/api/projects", headers=_auth(tok))
        assert resp.status_code == 200

    def test_create_project(self, client):
        admin = _admin()
        tok = _login(client, admin.email)
        n = _uid()
        cons = Consortium(consort_id=f"CPJ{n:04d}", name=f"C {n}", abbrev=f"CPJ{n}")
        db.session.add(cons)
        db.session.commit()
        resp = client.post("/api/projects", json={
            "name": f"Project {n}",
            "ref": f"PR{n:04d}",
            "consortium_id": cons.consort_id,
        }, headers=_auth(tok))
        assert resp.status_code in (200, 201)

    def test_projects_for_consortium(self, client):
        admin = _admin()
        tok = _login(client, admin.email)
        n = _uid()
        cons = Consortium(consort_id=f"CPC{n:04d}", name=f"C {n}", abbrev=f"CPC{n}")
        db.session.add(cons)
        db.session.commit()
        resp = client.get(f"/api/projects/{cons.consort_id}", headers=_auth(tok))
        assert resp.status_code == 200


# ── Vendors ──────────────────────────────────────────────────────────────────

class TestVendors:
    def test_list_vendors(self, client):
        admin = _admin()
        tok = _login(client, admin.email)
        resp = client.get("/api/vendors", headers=_auth(tok))
        assert resp.status_code == 200

    def test_create_vendor(self, client):
        admin = _admin()
        tok = _login(client, admin.email)
        n = _uid()
        resp = client.post("/api/vendors", json={
            "company_name": f"Vendor {n}",
        }, headers=_auth(tok))
        assert resp.status_code in (200, 201)

    def test_create_vendor_non_admin(self, client):
        user = _make_user()
        tok = _login(client, user.email)
        resp = client.post("/api/vendors", json={
            "company_name": "Bad Vendor",
        }, headers=_auth(tok))
        assert resp.status_code in (401, 403)

    def test_list_vendors_requires_auth(self, client):
        resp = client.get("/api/vendors")
        assert resp.status_code == 401
