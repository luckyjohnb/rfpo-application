"""
Route Coverage Tests — Ensure every user-app proxy route has a matching API endpoint.

This test suite catches the class of bug where a proxy route exists in the
user app but the corresponding API endpoint was never created (or was removed),
causing "AI scan failed" / "API service unavailable" errors in production.

Two layers:
  1. Route-registry check — compare proxy URL patterns against registered
     Flask routes in simple_api.  No HTTP calls, instant, catches 404s.
  2. Smoke tests — actually hit each API endpoint with a valid JWT to verify
     it responds (not 404/405).  Catches auth decorator mismatches, blueprint
     registration issues, etc.
"""

import re
import pytest
from werkzeug.routing import Map
from werkzeug.security import generate_password_hash

from models import (
    db, User, Consortium, Team, Project, Vendor, VendorSite,
    RFPO, RFPOLineItem, UploadedFile, Ticket,
)
import simple_api

pytestmark = [pytest.mark.integration, pytest.mark.routes]

# ── helpers ──────────────────────────────────────────────────────────────────

_ctr = {"v": 0}


def _uid():
    _ctr["v"] += 1
    return _ctr["v"]


def _seed_user(perms=None):
    n = _uid()
    u = User(
        record_id=f"RCU{n:05d}",
        email=f"routeuser{n}@test.com",
        fullname=f"Route User {n}",
        password_hash=generate_password_hash("pass"),
        active=True,
    )
    u.set_permissions(perms or ["GOD"])
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, email):
    resp = client.post(
        "/api/auth/login", json={"username": email, "password": "pass"}
    )
    return resp.get_json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _seed_full_rfpo():
    """Create a complete RFPO with all related entities for endpoint testing."""
    import json as _json
    n = _uid()
    user = _seed_user(["GOD"])

    consortium = Consortium(
        consort_id=f"RC{n:04d}",
        name=f"Route Consortium {n}",
        abbrev=f"RC{n}",
    )
    db.session.add(consortium)
    db.session.flush()

    team = Team(
        record_id=f"RT{n:04d}",
        name=f"Route Team {n}",
        abbrev=f"RTM{n}",
        consortium_consort_id=consortium.consort_id,
    )
    db.session.add(team)
    db.session.flush()

    project = Project(
        project_id=f"RP{n:04d}",
        ref=f"RPR{n:04d}",
        name=f"Route Project {n}",
        consortium_ids=_json.dumps([consortium.consort_id]),
    )
    db.session.add(project)
    db.session.flush()

    vendor = Vendor(vendor_id=f"RV{n:04d}", company_name=f"Route Vendor {n}")
    db.session.add(vendor)
    db.session.flush()

    vendor_site = VendorSite(
        vendor_site_id=f"RS{n:04d}",
        vendor_id=vendor.id,
    )
    db.session.add(vendor_site)
    db.session.flush()

    rfpo = RFPO(
        rfpo_id=f"RFPO-RT-{n:04d}",
        title=f"Route Test RFPO {n}",
        consortium_id=consortium.consort_id,
        team_id=team.id,
        project_id=project.project_id,
        vendor_id=vendor.id,
        vendor_site_id=vendor_site.id,
        requestor_id=user.record_id,
        status="Draft",
        created_by=user.record_id,
    )
    db.session.add(rfpo)
    db.session.flush()

    line_item = RFPOLineItem(
        rfpo_id=rfpo.id,
        line_number=1,
        description="Test Line Item",
        quantity=1,
        unit_price=100.00,
    )
    db.session.add(line_item)
    db.session.commit()

    return {
        "user": user,
        "consortium": consortium,
        "team": team,
        "project": project,
        "vendor": vendor,
        "vendor_site": vendor_site,
        "rfpo": rfpo,
        "line_item": line_item,
    }


# ═════════════════════════════════════════════════════════════════════════════
# LAYER 1: Route Registry — verify every proxy URL has a matching API rule
# ═════════════════════════════════════════════════════════════════════════════

# Proxy routes the user app defines → the API path they forward to.
# Format: (http_method, api_url_pattern)
# Use <int:xxx> or <xxx> for path params — we normalize them for comparison.
#
# This is the SINGLE SOURCE OF TRUTH.  When a new proxy route is added,
# add a row here.  If the test fails, the API endpoint is missing.

PROXY_TO_API_MAP = [
    # ── Auth ──
    ("POST", "/api/auth/login"),
    ("GET",  "/api/auth/verify"),
    ("POST", "/api/auth/sso-token"),
    ("POST", "/api/auth/change-password"),
    # ── RFPO CRUD ──
    ("GET",    "/api/rfpos"),
    ("POST",   "/api/rfpos"),
    ("GET",    "/api/rfpos/<int:rfpo_id>"),
    ("PUT",    "/api/rfpos/<int:rfpo_id>"),
    ("DELETE",  "/api/rfpos/<int:rfpo_id>"),
    ("GET",    "/api/rfpos/<int:rfpo_id>/validate"),
    ("POST",   "/api/rfpos/<int:rfpo_id>/submit-for-approval"),
    ("POST",   "/api/rfpos/<int:rfpo_id>/withdraw-approval"),
    # ── Line Items ──
    ("GET",    "/api/rfpos/<int:rfpo_id>/line-items"),
    ("POST",   "/api/rfpos/<int:rfpo_id>/line-items"),
    ("PUT",    "/api/rfpos/<int:rfpo_id>/line-items/<int:line_item_id>"),
    ("DELETE",  "/api/rfpos/<int:rfpo_id>/line-items/<int:line_item_id>"),
    # ── Files ──
    ("POST",   "/api/rfpos/<int:rfpo_id>/files/upload"),
    ("GET",    "/api/rfpos/<int:rfpo_id>/files/<file_id>/view"),
    ("DELETE",  "/api/rfpos/<int:rfpo_id>/files/<file_id>"),
    ("POST",   "/api/rfpos/<int:rfpo_id>/ai-scan/upload"),
    ("GET",    "/api/rfpos/export"),
    ("GET",    "/api/rfpos/<int:rfpo_id>/pdf-snapshot"),
    ("GET",    "/api/rfpos/<int:rfpo_id>/rendered-view"),
    ("GET",    "/api/rfpos/<int:rfpo_id>/audit-trail"),
    ("GET",    "/api/rfpos/doc-types"),
    ("GET",    "/api/rfpos/analytics"),
    # ── Users ──
    ("GET",    "/api/users/profile"),
    ("PUT",    "/api/users/profile"),
    ("GET",    "/api/users/permissions-summary"),
    ("GET",    "/api/users/approver-status"),
    ("GET",    "/api/users/approver-rfpos"),
    ("POST",   "/api/users/approval-action/<int:action_id>"),
    ("POST",   "/api/users/bulk-approval"),
    ("POST",   "/api/users/reassign-approval/<int:action_id>"),
    ("GET",    "/api/users"),
    # ── Teams ──
    ("GET",    "/api/teams"),
    ("POST",   "/api/teams"),
    ("GET",    "/api/teams/<int:team_id>"),
    # ── Lookups ──
    ("GET",    "/api/consortiums"),
    ("POST",   "/api/consortiums"),
    ("POST",   "/api/projects"),
    ("GET",    "/api/projects/<consortium_id>"),
    ("GET",    "/api/vendors"),
    ("POST",   "/api/vendors"),
    ("GET",    "/api/vendor-sites/<int:vendor_id>"),
    # ── Notifications ──
    ("GET",    "/api/notifications"),
    ("GET",    "/api/notifications/unread-count"),
    ("PUT",    "/api/notifications/<int:notif_id>/read"),
    ("POST",   "/api/notifications/mark-all-read"),
    # ── Tickets ──
    ("GET",    "/api/tickets"),
    ("POST",   "/api/tickets"),
    ("GET",    "/api/tickets/<int:ticket_id>"),
    ("PUT",    "/api/tickets/<int:ticket_id>"),
    ("POST",   "/api/tickets/<int:ticket_id>/comments"),
    ("POST",   "/api/tickets/<int:ticket_id>/attachments"),
    ("GET",    "/api/tickets/<int:ticket_id>/attachments/<file_id>/view"),
]


def _normalize_rule(rule_str):
    """Normalize Flask route rule to a comparable form.

    Converts  /api/rfpos/<int:rfpo_id>  →  /api/rfpos/<param>
    so we can match regardless of converter type or param name.
    """
    return re.sub(r"<(?:\w+:)?(\w+)>", "<param>", rule_str)


def _get_api_routes():
    """Extract all registered (method, normalized_rule) from simple_api.app."""
    routes = set()
    for rule in simple_api.app.url_map.iter_rules():
        for method in rule.methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            routes.add((method, _normalize_rule(rule.rule)))
    return routes


class TestRouteRegistry:
    """Verify every proxy route has a registered API endpoint."""

    def test_all_proxy_routes_have_api_endpoints(self):
        """CRITICAL: Every user-app proxy must map to a real API route.

        If this test fails, a proxy route is forwarding to an API endpoint
        that doesn't exist — users will see 'service unavailable' errors.
        """
        api_routes = _get_api_routes()
        missing = []

        for method, url_pattern in PROXY_TO_API_MAP:
            normalized = _normalize_rule(url_pattern)
            if (method, normalized) not in api_routes:
                missing.append(f"  {method:6s} {url_pattern}")

        if missing:
            msg = (
                f"\n\n{len(missing)} proxy route(s) have NO matching API endpoint!\n"
                "These will cause 'service unavailable' / 404 errors in production:\n\n"
                + "\n".join(missing)
                + "\n\nFix: add the missing route(s) to simple_api.py "
                "or the appropriate API blueprint.\n"
            )
            pytest.fail(msg)

    @pytest.mark.parametrize(
        "method,url_pattern",
        PROXY_TO_API_MAP,
        ids=[f"{m} {u}" for m, u in PROXY_TO_API_MAP],
    )
    def test_individual_proxy_route_exists(self, method, url_pattern):
        """Each proxy route individually verified against API route map."""
        api_routes = _get_api_routes()
        normalized = _normalize_rule(url_pattern)
        assert (method, normalized) in api_routes, (
            f"API route missing: {method} {url_pattern}\n"
            f"(normalized: {method} {normalized})\n"
            "The user-app proxy forwards here but no API route is registered."
        )


# ═════════════════════════════════════════════════════════════════════════════
# LAYER 2: Smoke Tests — actually hit API endpoints and verify non-404/405
# ═════════════════════════════════════════════════════════════════════════════

class TestAPISmokeEndpoints:
    """Hit real API endpoints to verify they respond (not 404/405).

    These tests don't validate business logic — they only ensure the route
    is reachable and the handler executes without crashing.  A 401 (no auth)
    or 400 (bad input) is fine; 404/405 means the route is missing.
    """

    @pytest.fixture(autouse=True)
    def setup(self, client, live_db_cleanup):
        self.client = client
        self.db = live_db_cleanup
        self.data = _seed_full_rfpo()
        self.token = _login(client, self.data["user"].email)

    def _get(self, url, expect_not=(404, 405)):
        resp = self.client.get(url, headers=_auth(self.token))
        assert resp.status_code not in expect_not, (
            f"GET {url} returned {resp.status_code} — route likely missing"
        )
        return resp

    def _post(self, url, json=None, expect_not=(404, 405)):
        resp = self.client.post(url, json=json or {}, headers=_auth(self.token))
        assert resp.status_code not in expect_not, (
            f"POST {url} returned {resp.status_code} — route likely missing"
        )
        return resp

    def _put(self, url, json=None, expect_not=(404, 405)):
        resp = self.client.put(url, json=json or {}, headers=_auth(self.token))
        assert resp.status_code not in expect_not, (
            f"PUT {url} returned {resp.status_code} — route likely missing"
        )
        return resp

    def _delete(self, url, expect_not=(404, 405)):
        resp = self.client.delete(url, headers=_auth(self.token))
        assert resp.status_code not in expect_not, (
            f"DELETE {url} returned {resp.status_code} — route likely missing"
        )
        return resp

    # ── Auth ──

    def test_auth_login(self):
        resp = self.client.post(
            "/api/auth/login",
            json={"username": self.data["user"].email, "password": "pass"},
        )
        assert resp.status_code == 200

    def test_auth_verify(self):
        self._get("/api/auth/verify")

    def test_auth_change_password(self):
        self._post("/api/auth/change-password", json={
            "current_password": "pass",
            "new_password": "newpass123",
        })

    # ── RFPO CRUD ──

    def test_rfpos_list(self):
        self._get("/api/rfpos")

    def test_rfpos_create(self):
        self._post("/api/rfpos", json={
            "consortium_id": self.data["consortium"].consort_id,
            "team_id": self.data["team"].id,
            "project_id": self.data["project"].id,
            "vendor_id": self.data["vendor"].id,
        })

    def test_rfpo_get(self):
        self._get(f"/api/rfpos/{self.data['rfpo'].id}")

    def test_rfpo_update(self):
        self._put(f"/api/rfpos/{self.data['rfpo'].id}", json={
            "status": "draft",
        })

    def test_rfpo_delete(self):
        self._delete(f"/api/rfpos/{self.data['rfpo'].id}")

    def test_rfpo_validate(self):
        self._get(f"/api/rfpos/{self.data['rfpo'].id}/validate")

    # ── Line Items ──

    def test_line_items_list(self):
        self._get(f"/api/rfpos/{self.data['rfpo'].id}/line-items")

    def test_line_items_create(self):
        self._post(f"/api/rfpos/{self.data['rfpo'].id}/line-items", json={
            "description": "Smoke test item",
            "quantity": 1,
            "unit_price": 50.00,
        })

    def test_line_item_update(self):
        self._put(
            f"/api/rfpos/{self.data['rfpo'].id}"
            f"/line-items/{self.data['line_item'].id}",
            json={"description": "Updated"},
        )

    def test_line_item_delete(self):
        self._delete(
            f"/api/rfpos/{self.data['rfpo'].id}"
            f"/line-items/{self.data['line_item'].id}",
        )

    # ── Files / AI Scan ──

    def test_file_upload(self):
        import io
        data = {
            "file": (io.BytesIO(b"%PDF-1.4 test"), "test.pdf", "application/pdf"),
        }
        resp = self.client.post(
            f"/api/rfpos/{self.data['rfpo'].id}/files/upload",
            headers=_auth(self.token),
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code not in (404, 405), (
            f"POST files/upload returned {resp.status_code}"
        )

    def test_ai_scan_upload(self):
        import io
        data = {
            "file": (io.BytesIO(b"%PDF-1.4 test"), "invoice.pdf", "application/pdf"),
        }
        resp = self.client.post(
            f"/api/rfpos/{self.data['rfpo'].id}/ai-scan/upload",
            headers=_auth(self.token),
            data=data,
            content_type="multipart/form-data",
        )
        # 200 or 500 (if OpenAI not configured) are both fine — NOT 404/405
        assert resp.status_code not in (404, 405), (
            f"POST ai-scan/upload returned {resp.status_code} — route missing!"
        )

    def test_doc_types(self):
        self._get("/api/rfpos/doc-types")

    def test_rfpo_rendered_view(self):
        self._get(f"/api/rfpos/{self.data['rfpo'].id}/rendered-view")

    def test_rfpo_audit_trail(self):
        self._get(f"/api/rfpos/{self.data['rfpo'].id}/audit-trail")

    def test_rfpo_analytics(self):
        self._get("/api/rfpos/analytics")

    # ── Users ──

    def test_users_list(self):
        self._get("/api/users")

    def test_user_profile_get(self):
        self._get("/api/users/profile")

    def test_user_profile_update(self):
        self._put("/api/users/profile", json={"fullname": "Updated Name"})

    def test_user_permissions_summary(self):
        self._get("/api/users/permissions-summary")

    def test_user_approver_status(self):
        self._get("/api/users/approver-status")

    def test_user_approver_rfpos(self):
        self._get("/api/users/approver-rfpos")

    # ── Teams ──

    def test_teams_list(self):
        self._get("/api/teams")

    def test_team_get(self):
        self._get(f"/api/teams/{self.data['team'].id}")

    # ── Lookups ──

    def test_consortiums_list(self):
        self._get("/api/consortiums")

    def test_projects_for_consortium(self):
        self._get(f"/api/projects/{self.data['consortium'].consort_id}")

    def test_vendors_list(self):
        self._get("/api/vendors")

    def test_vendor_sites(self):
        self._get(f"/api/vendor-sites/{self.data['vendor'].id}")

    # ── Notifications ──

    def test_notifications_list(self):
        self._get("/api/notifications")

    def test_notifications_unread_count(self):
        self._get("/api/notifications/unread-count")

    def test_notifications_mark_all_read(self):
        self._post("/api/notifications/mark-all-read")

    # ── Tickets ──

    def test_tickets_list(self):
        self._get("/api/tickets")

    def test_tickets_create(self):
        self._post("/api/tickets", json={
            "type": "bug",
            "title": "Smoke test bug",
            "description": "A test bug",
        })

    def test_ticket_get(self):
        ticket = Ticket(
            ticket_number="BUG-9999",
            type="bug",
            title="Get Test",
            description="desc",
            created_by=self.data["user"].id,
        )
        db.session.add(ticket)
        db.session.commit()
        self._get(f"/api/tickets/{ticket.id}")

    def test_ticket_update(self):
        ticket = Ticket(
            ticket_number="BUG-9998",
            type="bug",
            title="Update Test",
            description="desc",
            created_by=self.data["user"].id,
        )
        db.session.add(ticket)
        db.session.commit()
        self._put(f"/api/tickets/{ticket.id}", json={"title": "Updated"})

    def test_ticket_add_comment(self):
        ticket = Ticket(
            ticket_number="BUG-9997",
            type="bug",
            title="Comment Test",
            description="desc",
            created_by=self.data["user"].id,
        )
        db.session.add(ticket)
        db.session.commit()
        self._post(f"/api/tickets/{ticket.id}/comments", json={"content": "test comment"})

    def test_ticket_upload_attachment(self):
        ticket = Ticket(
            ticket_number="BUG-9996",
            type="bug",
            title="Attach Test",
            description="desc",
            created_by=self.data["user"].id,
        )
        db.session.add(ticket)
        db.session.commit()
        import io
        data = {
            "file": (io.BytesIO(b"%PDF-1.4 test"), "attach.pdf", "application/pdf"),
        }
        resp = self.client.post(
            f"/api/tickets/{ticket.id}/attachments",
            headers=_auth(self.token),
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code not in (404, 405)

    def test_ticket_view_attachment(self):
        # Just verify the route exists (will 404 without real attachment)
        ticket = Ticket(
            ticket_number="BUG-9995",
            type="bug",
            title="View Attach Test",
            description="desc",
            created_by=self.data["user"].id,
        )
        db.session.add(ticket)
        db.session.commit()
        resp = self.client.get(
            f"/api/tickets/{ticket.id}/attachments/fake-uuid/view",
            headers=_auth(self.token),
        )
        # 404 is OK here (no attachment) — but 405 means route missing
        assert resp.status_code != 405

    # ── Health ──

    def test_health_check(self):
        resp = self.client.get("/api/health")
        assert resp.status_code == 200
