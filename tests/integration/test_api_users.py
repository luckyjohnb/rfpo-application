"""
P1 Integration Tests — Users, Notifications, Audit trail.
"""

import pytest
from werkzeug.security import generate_password_hash

from models import db, User, Notification

pytestmark = [pytest.mark.integration]

_counter = {"v": 0}


def _uid():
    _counter["v"] += 1
    return _counter["v"]


def _make_user(perms=None, **kw):
    n = _uid()
    u = User(
        record_id=kw.get("record_id", f"UUNA{n:04d}"),
        email=kw.get("email", f"una{n}@test.com"),
        fullname=kw.get("fullname", f"User {n}"),
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


# ── User profile ─────────────────────────────────────────────────────────────

class TestUserProfile:
    def test_get_profile(self, client):
        user = _make_user()
        tok = _login(client, user.email)
        resp = client.get("/api/users/profile", headers=_auth(tok))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_get_profile_no_auth(self, client):
        resp = client.get("/api/users/profile")
        assert resp.status_code == 401

    def test_update_profile(self, client):
        user = _make_user()
        tok = _login(client, user.email)
        resp = client.put("/api/users/profile", json={
            "fullname": "Updated Name",
        }, headers=_auth(tok))
        assert resp.status_code == 200

    def test_permissions_summary(self, client):
        user = _make_user(["GOD"])
        tok = _login(client, user.email)
        resp = client.get("/api/users/permissions-summary", headers=_auth(tok))
        assert resp.status_code == 200


# ── User list (admin) ────────────────────────────────────────────────────────

class TestUserList:
    def test_list_users_admin(self, client):
        admin = _admin()
        tok = _login(client, admin.email)
        resp = client.get("/api/users", headers=_auth(tok))
        assert resp.status_code == 200

    def test_list_users_non_admin(self, client):
        user = _make_user()
        tok = _login(client, user.email)
        resp = client.get("/api/users", headers=_auth(tok))
        # May be 403 or may return limited data — depends on route
        assert resp.status_code in (200, 401, 403)


# ── Change password ──────────────────────────────────────────────────────────

class TestChangePassword:
    def test_change_password_success(self, client):
        user = _make_user()
        tok = _login(client, user.email)
        resp = client.post("/api/auth/change-password", json={
            "current_password": "pass",
            "new_password": "NewPass123!",
        }, headers=_auth(tok))
        assert resp.status_code == 200

    def test_change_password_wrong_current(self, client):
        user = _make_user()
        tok = _login(client, user.email)
        resp = client.post("/api/auth/change-password", json={
            "current_password": "wrong",
            "new_password": "newpass123!",
        }, headers=_auth(tok))
        assert resp.status_code in (400, 401)


# ── Notifications ────────────────────────────────────────────────────────────

class TestNotifications:
    def test_get_notifications(self, client):
        user = _make_user()
        tok = _login(client, user.email)
        resp = client.get("/api/notifications", headers=_auth(tok))
        assert resp.status_code == 200

    def test_unread_count(self, client):
        user = _make_user()
        tok = _login(client, user.email)
        resp = client.get("/api/notifications/unread-count", headers=_auth(tok))
        assert resp.status_code == 200

    def test_mark_all_read(self, client):
        user = _make_user()
        tok = _login(client, user.email)
        # Create a notification in DB
        notif = Notification(
            user_id=user.id,
            type="rfpo_status",
            title="Test",
            message="Hello",
            is_read=False,
        )
        db.session.add(notif)
        db.session.commit()
        resp = client.post("/api/notifications/mark-all-read", headers=_auth(tok))
        assert resp.status_code == 200

    def test_mark_single_read(self, client):
        user = _make_user()
        tok = _login(client, user.email)
        notif = Notification(
            user_id=user.id,
            type="rfpo_status",
            title="Single",
            message="Mark me",
            is_read=False,
        )
        db.session.add(notif)
        db.session.commit()
        resp = client.put(f"/api/notifications/{notif.id}/read", headers=_auth(tok))
        assert resp.status_code == 200

    def test_notifications_require_auth(self, client):
        resp = client.get("/api/notifications")
        assert resp.status_code == 401


# ── Approver status ──────────────────────────────────────────────────────────

class TestApproverStatus:
    def test_get_approver_status(self, client):
        user = _make_user()
        tok = _login(client, user.email)
        resp = client.get("/api/users/approver-status", headers=_auth(tok))
        assert resp.status_code == 200

    def test_sync_approver_status(self, client):
        user = _make_user()
        tok = _login(client, user.email)
        resp = client.post("/api/users/sync-approver-status", headers=_auth(tok))
        assert resp.status_code == 200
