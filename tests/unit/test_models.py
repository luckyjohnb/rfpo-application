"""
P0 Unit Tests — Model layer.

Covers to_dict(), JSON get/set methods, permissions, defaults,
relationships, and calculated fields for all major models.
"""

import json
import pytest
from datetime import datetime, date
from decimal import Decimal
from werkzeug.security import generate_password_hash, check_password_hash

from models import (
    db,
    User,
    Consortium,
    RFPO,
    RFPOLineItem,
    Team,
    UserTeam,
    Project,
    Vendor,
    VendorSite,
    AuditLog,
    Notification,
    EmailLog,
    RFPOApprovalWorkflow,
    RFPOApprovalStage,
    RFPOApprovalStep,
    RFPOApprovalInstance,
    RFPOApprovalAction,
)

pytestmark = [pytest.mark.unit, pytest.mark.models]


# ── User ──────────────────────────────────────────────────────────────────

class TestUser:
    def _make(self, **kw):
        n = id(kw) % 100000
        defaults = dict(
            record_id=f"U{n}", email=f"u{n}@t.com", fullname="Test",
            password_hash=generate_password_hash("pw"), active=True,
        )
        defaults.update(kw)
        u = User(**defaults)
        db.session.add(u)
        db.session.flush()
        return u

    def test_get_permissions_default_empty(self, app):
        u = self._make()
        assert u.get_permissions() == []

    def test_set_and_get_permissions(self, app):
        u = self._make()
        u.set_permissions(["GOD", "RFPO_ADMIN"])
        assert u.get_permissions() == ["GOD", "RFPO_ADMIN"]

    def test_has_permission(self, app):
        u = self._make()
        u.set_permissions(["RFPO_USER"])
        assert u.has_permission("RFPO_USER") is True
        assert u.has_permission("GOD") is False

    def test_is_super_admin(self, app):
        u = self._make()
        u.set_permissions(["GOD"])
        assert u.is_super_admin() is True

    def test_is_rfpo_admin(self, app):
        u = self._make()
        u.set_permissions(["RFPO_ADMIN"])
        assert u.is_rfpo_admin() is True

    def test_is_rfpo_user(self, app):
        u = self._make()
        u.set_permissions(["RFPO_USER"])
        assert u.is_rfpo_user() is True

    def test_display_name_fallback(self, app):
        u = self._make(fullname="John Doe")
        assert u.get_display_name() == "John Doe"

    def test_password_hashing(self, app):
        u = self._make()
        assert check_password_hash(u.password_hash, "pw")

    def test_to_dict_returns_dict(self, app):
        u = self._make()
        d = u.to_dict()
        assert isinstance(d, dict)
        assert "email" in d
        assert "id" in d

    def test_to_dict_no_password(self, app):
        u = self._make()
        d = u.to_dict()
        assert "password_hash" not in d

    def test_permissions_version_default(self, app):
        u = self._make()
        assert (u.permissions_version or 0) == 0

    def test_inactive_user(self, app):
        u = self._make(active=False)
        assert u.active is False


# ── Consortium ────────────────────────────────────────────────────────────

class TestConsortium:
    def _make(self, **kw):
        n = id(kw) % 100000
        defaults = dict(consort_id=f"C{n}", name=f"Cons {n}", abbrev=f"C{n}")
        defaults.update(kw)
        c = Consortium(**defaults)
        db.session.add(c)
        db.session.flush()
        return c

    def test_to_dict(self, app):
        c = self._make()
        d = c.to_dict()
        assert d["consort_id"] == c.consort_id
        assert "name" in d

    def test_viewer_users_default_empty(self, app):
        c = self._make()
        assert c.get_rfpo_viewer_users() == []

    def test_set_get_viewer_users(self, app):
        c = self._make()
        c.set_rfpo_viewer_users(["U001", "U002"])
        assert c.get_rfpo_viewer_users() == ["U001", "U002"]

    def test_set_get_admin_users(self, app):
        c = self._make()
        c.set_rfpo_admin_users(["A001"])
        assert c.get_rfpo_admin_users() == ["A001"]

    def test_filters_empty_strings(self, app):
        c = self._make()
        c.set_rfpo_viewer_users(["U001", "", "U002"])
        assert c.get_rfpo_viewer_users() == ["U001", "U002"]


# ── RFPO + LineItem ──────────────────────────────────────────────────────

class TestRFPO:
    def test_defaults(self, app, sample_rfpo):
        assert sample_rfpo.status == "draft"
        assert sample_rfpo.deleted_at is None

    def test_soft_delete(self, app, sample_rfpo):
        sample_rfpo.soft_delete()
        assert sample_rfpo.is_deleted is True
        assert sample_rfpo.deleted_at is not None

    def test_update_totals(self, app, sample_rfpo):
        # sample_rfpo has 1 line: qty=2 x price=100 = 200
        assert float(sample_rfpo.subtotal) == 200.0
        assert float(sample_rfpo.total_amount) == 200.0

    def test_cost_share_percent(self, app, sample_rfpo):
        sample_rfpo.cost_share_type = "percent"
        sample_rfpo.cost_share_amount = 10  # 10%
        sample_rfpo.update_totals()
        expected_share = float(sample_rfpo.subtotal) * 0.10
        assert float(sample_rfpo.total_amount) == pytest.approx(
            float(sample_rfpo.subtotal) - expected_share, rel=0.01
        )

    def test_cost_share_total(self, app, sample_rfpo):
        sample_rfpo.cost_share_type = "total"
        sample_rfpo.cost_share_amount = 50
        sample_rfpo.update_totals()
        assert float(sample_rfpo.total_amount) == pytest.approx(
            float(sample_rfpo.subtotal) - 50, rel=0.01
        )

    def test_to_dict(self, app, sample_rfpo):
        d = sample_rfpo.to_dict()
        assert d["rfpo_id"] == sample_rfpo.rfpo_id
        assert "total_amount" in d
        assert "status" in d

    def test_to_dict_includes_deleted_at(self, app, sample_rfpo):
        d = sample_rfpo.to_dict()
        assert "deleted_at" in d

    def test_generate_po_number(self, app):
        po = RFPO.generate_po_number("TST")
        assert po.startswith("PO-TST-")


class TestRFPOLineItem:
    def test_calculate_total(self, app):
        li = RFPOLineItem(
            rfpo_id=1, description="Test", quantity=3,
            unit_price=50.00, line_number=1,
        )
        li.calculate_total()
        assert float(li.total_price) == 150.0

    def test_to_dict(self, app):
        li = RFPOLineItem(
            rfpo_id=1, description="Test", quantity=1,
            unit_price=10.00, total_price=10.00, line_number=1,
        )
        db.session.add(li)
        db.session.flush()
        d = li.to_dict()
        assert "description" in d


# ── Team ──────────────────────────────────────────────────────────────────

class TestTeam:
    def test_viewer_users(self, app, sample_team):
        sample_team.set_rfpo_viewer_users(["U1", "U2"])
        assert sample_team.get_rfpo_viewer_users() == ["U1", "U2"]

    def test_admin_users(self, app, sample_team):
        sample_team.set_rfpo_admin_users(["A1"])
        assert sample_team.get_rfpo_admin_users() == ["A1"]

    def test_to_dict(self, app, sample_team):
        d = sample_team.to_dict()
        assert d["name"] == sample_team.name


# ── Project ───────────────────────────────────────────────────────────────

class TestProject:
    def test_consortium_ids(self, app, sample_project, sample_consortium):
        ids = sample_project.get_consortium_ids()
        assert sample_consortium.consort_id in ids

    def test_multi_consortium(self, app, sample_project):
        sample_project.set_consortium_ids(["C1", "C2"])
        assert sample_project.is_multi_consortium() is True

    def test_project_type_gov(self, app, sample_project):
        sample_project.gov_funded = True
        assert sample_project.get_project_type() == "Government Funded"

    def test_to_dict(self, app, sample_project):
        d = sample_project.to_dict()
        assert "project_id" in d


# ── Vendor ────────────────────────────────────────────────────────────────

class TestVendor:
    def test_approved_consortiums(self, app, sample_vendor):
        sample_vendor.set_approved_consortiums(["TC1", "TC2"])
        assert sample_vendor.get_approved_consortiums() == ["TC1", "TC2"]

    def test_is_approved_for_consortium(self, app, sample_vendor):
        sample_vendor.set_approved_consortiums(["TC1"])
        assert sample_vendor.is_approved_for_consortium("TC1") is True
        assert sample_vendor.is_approved_for_consortium("TC2") is False

    def test_vendor_type_display(self, app, sample_vendor):
        sample_vendor.vendor_type = 1
        assert sample_vendor.get_vendor_type_display() == "University"

    def test_to_dict(self, app, sample_vendor):
        d = sample_vendor.to_dict()
        assert "company_name" in d
        assert d["vendor_id"] == sample_vendor.vendor_id


# ── AuditLog ──────────────────────────────────────────────────────────────

class TestAuditLog:
    def test_set_get_details(self, app):
        log = AuditLog(action="test", entity_type="rfpo")
        log.set_details({"foo": "bar"})
        assert log.get_details() == {"foo": "bar"}

    def test_details_none(self, app):
        log = AuditLog(action="test", entity_type="rfpo")
        assert log.get_details() == {}

    def test_to_dict(self, app):
        log = AuditLog(action="create", entity_type="rfpo", entity_id="R001")
        db.session.add(log)
        db.session.flush()
        d = log.to_dict()
        assert d["action"] == "create"


# ── Notification ──────────────────────────────────────────────────────────

class TestNotification:
    def test_mark_read(self, app, admin_user):
        n = Notification(
            user_id=admin_user.id, type="info",
            title="Test", message="msg",
        )
        db.session.add(n)
        db.session.flush()
        n.mark_read()
        assert n.is_read is True
        assert n.read_at is not None

    def test_to_dict(self, app, admin_user):
        n = Notification(
            user_id=admin_user.id, type="info",
            title="Test", message="msg",
        )
        db.session.add(n)
        db.session.flush()
        d = n.to_dict()
        assert d["title"] == "Test"


# ── EmailLog ──────────────────────────────────────────────────────────────

class TestEmailLog:
    def test_get_to_emails(self, app):
        el = EmailLog(
            email_type="approval", subject="Test", from_email="a@t.com",
            to_emails=json.dumps(["b@t.com"]), status="sent",
        )
        db.session.add(el)
        db.session.flush()
        assert el.get_to_emails() == ["b@t.com"]

    def test_to_dict(self, app):
        el = EmailLog(
            email_type="approval", subject="Test", from_email="a@t.com",
            to_emails=json.dumps(["b@t.com"]), status="sent",
        )
        db.session.add(el)
        db.session.flush()
        d = el.to_dict()
        assert d["status"] == "sent"


# ── Approval Workflow Models ──────────────────────────────────────────────

class TestApprovalWorkflow:
    def test_create_workflow(self, app, sample_consortium):
        wf = RFPOApprovalWorkflow(
            workflow_id="WF001", name="Test WF",
            workflow_type="consortium",
            consortium_id=sample_consortium.consort_id,
            is_active=True, is_template=True,
        )
        db.session.add(wf)
        db.session.flush()
        assert wf.get_total_stages() == 0

    def test_workflow_to_dict(self, app, sample_consortium):
        wf = RFPOApprovalWorkflow(
            workflow_id="WF002", name="Test WF 2",
            workflow_type="consortium",
            consortium_id=sample_consortium.consort_id,
        )
        db.session.add(wf)
        db.session.flush()
        d = wf.to_dict()
        assert d["workflow_id"] == "WF002"


class TestApprovalStage:
    def test_create_stage(self, app, sample_consortium):
        wf = RFPOApprovalWorkflow(
            workflow_id="WFS01", name="WF", workflow_type="consortium",
            consortium_id=sample_consortium.consort_id,
        )
        db.session.add(wf)
        db.session.flush()

        stage = RFPOApprovalStage(
            stage_id="STG01", stage_name="Stage 1", stage_order=1,
            budget_bracket_key="0-5000", budget_bracket_amount=5000,
            workflow_id=wf.id,
        )
        db.session.add(stage)
        db.session.flush()
        assert stage.get_total_steps() == 0

    def test_parallel_flag(self, app, sample_consortium):
        wf = RFPOApprovalWorkflow(
            workflow_id="WFS02", name="WF", workflow_type="consortium",
            consortium_id=sample_consortium.consort_id,
        )
        db.session.add(wf)
        db.session.flush()

        stage = RFPOApprovalStage(
            stage_id="STG02", stage_name="Parallel", stage_order=1,
            budget_bracket_key="0-5000", budget_bracket_amount=5000,
            workflow_id=wf.id, is_parallel=True,
        )
        db.session.add(stage)
        db.session.flush()
        assert stage.is_parallel is True


class TestApprovalInstance:
    def test_instance_data_roundtrip(self, app):
        inst = RFPOApprovalInstance(
            instance_id="INST01", rfpo_id=1,
            template_workflow_id=1, workflow_name="Test",
            workflow_version="1.0", consortium_id="C01",
        )
        data = {"stages": [{"stage_order": 1, "steps": []}]}
        inst.set_instance_data(data)
        assert inst.get_instance_data() == data

    def test_overall_status_default(self, app):
        inst = RFPOApprovalInstance(
            instance_id="INST02", rfpo_id=1,
            template_workflow_id=1, workflow_name="Test",
            workflow_version="1.0", consortium_id="C01",
            overall_status="draft",
        )
        assert inst.overall_status == "draft"
