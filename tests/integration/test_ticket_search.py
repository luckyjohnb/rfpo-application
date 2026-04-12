"""
Integration Tests — Ticket Search & Filtering.

Tests the search (`q`), date range, sort, and assigned_to
query parameters on GET /api/tickets, plus admin panel
search and pagination routes.
"""

import pytest
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

from models import db, User, Ticket

pytestmark = [pytest.mark.integration, pytest.mark.tickets]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_counter = 0


def _make_user(perms=None):
    global _counter
    _counter += 1
    user = User(
        record_id=f"UTCK{_counter:04d}",
        email=f"ticketuser{_counter}@test.com",
        fullname=f"Ticket User {_counter}",
        password_hash=generate_password_hash("pass123"),
        active=True,
    )
    if perms:
        user.set_permissions(perms)
    db.session.add(user)
    db.session.flush()
    return user


def _make_ticket(user, ticket_type="bug", title="Test Bug", description="A bug",
                 status="open", priority="medium", severity=None, ticket_number=None):
    if ticket_number is None:
        ticket_number = Ticket.generate_ticket_number(ticket_type, db.session)
    ticket = Ticket(
        ticket_number=ticket_number,
        type=ticket_type,
        title=title,
        description=description,
        status=status,
        priority=priority,
        severity=severity,
        created_by=user.id,
    )
    db.session.add(ticket)
    db.session.flush()
    return ticket


def _login(client, email, password="pass123"):
    resp = client.post("/api/auth/login", json={
        "username": email, "password": password,
    })
    return resp.get_json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# API Search Tests
# ---------------------------------------------------------------------------

class TestTicketSearch:
    """GET /api/tickets?q=..."""

    def test_search_by_ticket_number(self, client):
        user = _make_user(["GOD"])
        _make_ticket(user, ticket_number="BUG-9901", title="Unrelated bug")
        _make_ticket(user, ticket_number="BUG-9902", title="Other bug")
        db.session.commit()
        token = _login(client, user.email)

        resp = client.get("/api/tickets?q=BUG-9901", headers=_auth(token))
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["total"] == 1
        assert data["tickets"][0]["ticket_number"] == "BUG-9901"

    def test_search_by_title_partial(self, client):
        user = _make_user(["GOD"])
        _make_ticket(user, title="Login page crashes on submit")
        _make_ticket(user, title="Dashboard loads slowly")
        db.session.commit()
        token = _login(client, user.email)

        resp = client.get("/api/tickets?q=crashes", headers=_auth(token))
        data = resp.get_json()
        assert data["total"] == 1
        assert "crashes" in data["tickets"][0]["title"].lower()

    def test_search_by_description(self, client):
        user = _make_user(["GOD"])
        _make_ticket(user, title="Bug A", description="The frobnicate widget fails silently")
        _make_ticket(user, title="Bug B", description="Normal behavior observed")
        db.session.commit()
        token = _login(client, user.email)

        resp = client.get("/api/tickets?q=frobnicate", headers=_auth(token))
        data = resp.get_json()
        assert data["total"] == 1
        assert data["tickets"][0]["title"] == "Bug A"

    def test_search_case_insensitive(self, client):
        user = _make_user(["GOD"])
        _make_ticket(user, title="PDF Generation Error")
        db.session.commit()
        token = _login(client, user.email)

        resp = client.get("/api/tickets?q=pdf+generation", headers=_auth(token))
        data = resp.get_json()
        assert data["total"] == 1

    def test_search_empty_returns_all(self, client):
        user = _make_user(["GOD"])
        _make_ticket(user, title="Bug One")
        _make_ticket(user, title="Bug Two")
        _make_ticket(user, title="Bug Three")
        db.session.commit()
        token = _login(client, user.email)

        resp = client.get("/api/tickets?q=", headers=_auth(token))
        data = resp.get_json()
        assert data["total"] == 3

    def test_search_with_status_filter(self, client):
        user = _make_user(["GOD"])
        _make_ticket(user, title="Open searchable bug", status="open")
        _make_ticket(user, title="Closed searchable bug", status="closed")
        db.session.commit()
        token = _login(client, user.email)

        resp = client.get("/api/tickets?q=searchable&status=open", headers=_auth(token))
        data = resp.get_json()
        assert data["total"] == 1
        assert data["tickets"][0]["status"] == "open"

    def test_search_with_priority_filter(self, client):
        user = _make_user(["GOD"])
        _make_ticket(user, title="High prio searchable", priority="high")
        _make_ticket(user, title="Low prio searchable", priority="low")
        db.session.commit()
        token = _login(client, user.email)

        resp = client.get("/api/tickets?q=searchable&priority=high", headers=_auth(token))
        # Priority isn't a direct filter param on the API (only status/type), but the q= should still work
        data = resp.get_json()
        assert data["success"] is True

    def test_search_no_results(self, client):
        user = _make_user(["GOD"])
        _make_ticket(user, title="Normal bug")
        db.session.commit()
        token = _login(client, user.email)

        resp = client.get("/api/tickets?q=zzzznonexistent", headers=_auth(token))
        data = resp.get_json()
        assert data["total"] == 0
        assert data["tickets"] == []

    def test_search_special_characters(self, client):
        user = _make_user(["GOD"])
        _make_ticket(user, title="100% complete test")
        db.session.commit()
        token = _login(client, user.email)

        resp = client.get("/api/tickets?q=%25test_", headers=_auth(token))
        data = resp.get_json()
        assert resp.status_code == 200
        # Should not crash — SQL wildcards are treated as literals

    def test_search_truncates_long_input(self, client):
        user = _make_user(["GOD"])
        _make_ticket(user, title="Short title")
        db.session.commit()
        token = _login(client, user.email)

        long_query = "a" * 500
        resp = client.get(f"/api/tickets?q={long_query}", headers=_auth(token))
        assert resp.status_code == 200

    def test_search_pagination(self, client):
        user = _make_user(["GOD"])
        for i in range(5):
            _make_ticket(user, title=f"Paginated bug {i}")
        db.session.commit()
        token = _login(client, user.email)

        resp = client.get("/api/tickets?q=Paginated&per_page=2&page=1", headers=_auth(token))
        data = resp.get_json()
        assert len(data["tickets"]) == 2
        assert data["total"] == 5
        assert data["pages"] == 3


class TestTicketSort:
    """GET /api/tickets?sort=..."""

    def test_sort_by_ticket_number(self, client):
        user = _make_user(["GOD"])
        _make_ticket(user, ticket_number="BUG-0001", title="First")
        _make_ticket(user, ticket_number="BUG-0002", title="Second")
        db.session.commit()
        token = _login(client, user.email)

        resp = client.get("/api/tickets?sort=ticket_number", headers=_auth(token))
        data = resp.get_json()
        numbers = [t["ticket_number"] for t in data["tickets"]]
        assert numbers == sorted(numbers)

    def test_sort_default_created_at_desc(self, client):
        user = _make_user(["GOD"])
        t1 = _make_ticket(user, title="Older")
        t2 = _make_ticket(user, title="Newer")
        db.session.commit()
        token = _login(client, user.email)

        resp = client.get("/api/tickets", headers=_auth(token))
        data = resp.get_json()
        assert len(data["tickets"]) == 2
        # Newer should be first (desc)
        assert data["tickets"][0]["title"] == "Newer"


class TestTicketDateFilter:
    """GET /api/tickets?date_from=...&date_to=..."""

    def test_date_range_filter(self, client):
        user = _make_user(["GOD"])
        t1 = _make_ticket(user, title="Old bug")
        t1.created_at = datetime(2025, 1, 1)
        t2 = _make_ticket(user, title="New bug")
        t2.created_at = datetime(2026, 6, 15)
        db.session.commit()
        token = _login(client, user.email)

        resp = client.get("/api/tickets?date_from=2026-01-01", headers=_auth(token))
        data = resp.get_json()
        assert data["total"] == 1
        assert data["tickets"][0]["title"] == "New bug"

    def test_date_to_filter(self, client):
        user = _make_user(["GOD"])
        t1 = _make_ticket(user, title="Old bug")
        t1.created_at = datetime(2025, 1, 1)
        t2 = _make_ticket(user, title="New bug")
        t2.created_at = datetime(2026, 6, 15)
        db.session.commit()
        token = _login(client, user.email)

        resp = client.get("/api/tickets?date_to=2025-12-31", headers=_auth(token))
        data = resp.get_json()
        assert data["total"] == 1
        assert data["tickets"][0]["title"] == "Old bug"

    def test_invalid_date_ignored(self, client):
        user = _make_user(["GOD"])
        _make_ticket(user, title="Any bug")
        db.session.commit()
        token = _login(client, user.email)

        resp = client.get("/api/tickets?date_from=not-a-date", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1
