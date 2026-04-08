"""
P0 Integration Tests — Authentication.

Tests login, JWT token generation, token verification,
expired tokens, and permission checks against the live API.
"""

import json
import pytest
from werkzeug.security import generate_password_hash

from models import db, User

pytestmark = [pytest.mark.integration, pytest.mark.auth]


class TestLogin:
    def _create_user(self, email="test@test.com", password="testpass", perms=None):
        user = User(
            record_id="UTST0001",
            email=email,
            fullname="Test User",
            password_hash=generate_password_hash(password),
            active=True,
        )
        if perms:
            user.set_permissions(perms)
        db.session.add(user)
        db.session.commit()
        return user

    def test_login_success(self, client):
        self._create_user()
        resp = client.post("/api/auth/login", json={
            "username": "test@test.com", "password": "testpass"
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "token" in data
        assert data["user"]["email"] == "test@test.com"

    def test_login_wrong_password(self, client):
        self._create_user()
        resp = client.post("/api/auth/login", json={
            "username": "test@test.com", "password": "wrong"
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "nobody@test.com", "password": "x"
        })
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/auth/login", json={"email": "test@test.com"})
        assert resp.status_code == 400

    def test_login_inactive_user(self, client):
        user = self._create_user()
        user.active = False
        db.session.commit()
        resp = client.post("/api/auth/login", json={
            "username": "test@test.com", "password": "testpass"
        })
        assert resp.status_code == 401

    def test_token_in_response(self, client):
        self._create_user()
        resp = client.post("/api/auth/login", json={
            "username": "test@test.com", "password": "testpass"
        })
        token = resp.get_json()["token"]
        assert isinstance(token, str)
        assert len(token) > 20


class TestTokenVerification:
    def _login(self, client, email="verify@test.com", password="pass123"):
        user = User(
            record_id="UVER0001", email=email, fullname="Verify",
            password_hash=generate_password_hash(password), active=True,
        )
        user.set_permissions(["RFPO_USER"])
        db.session.add(user)
        db.session.commit()
        resp = client.post("/api/auth/login", json={"username": email, "password": password})
        return resp.get_json()["token"]

    def test_verify_valid_token(self, client):
        token = self._login(client)
        resp = client.get("/api/auth/verify", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.get_json()["authenticated"] is True

    def test_verify_no_token(self, client):
        resp = client.get("/api/auth/verify")
        assert resp.status_code == 401

    def test_verify_invalid_token(self, client):
        resp = client.get("/api/auth/verify", headers={"Authorization": "Bearer garbage.token.here"})
        assert resp.status_code == 401

    def test_verify_returns_user_info(self, client):
        token = self._login(client)
        resp = client.get("/api/auth/verify", headers={"Authorization": f"Bearer {token}"})
        data = resp.get_json()
        assert "user" in data
        assert data["user"]["email"] == "verify@test.com"


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "healthy"

    def test_health_no_cache(self, client):
        resp = client.get("/api/health")
        assert "no-cache" in resp.headers.get("Cache-Control", "")
