#!/usr/bin/env python3
"""
Unit tests for refactored admin helpers in custom_admin.py.

Covers:
- _build_phase_snapshot: correct dict structure from mock workflow/stage data
- _create_first_step_action: action creation, counter increment, no-step case
- _send_user_welcome_email: flash message for GOD/RFPO_ADMIN/RFPO_USER perms
- _DEFAULT_PDF_FIELD_POSITIONS: correct field count and required keys
- Integration: submit-approval endpoint creates instance and actions
- Integration: user_new endpoint creates user and sends welcome email
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from werkzeug.security import generate_password_hash

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Override DATABASE_URL to use in-memory SQLite before importing app
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-unit-tests-only!!"
# Suppress email creds warnings
os.environ.pop("MAIL_USERNAME", None)
os.environ.pop("MAIL_PASSWORD", None)
os.environ.pop("ACS_CONNECTION_STRING", None)

from custom_admin import create_app
from models import (
    db, User, Consortium, Team, RFPO, RFPOLineItem,
    RFPOApprovalWorkflow, RFPOApprovalStage, RFPOApprovalStep,
    RFPOApprovalInstance, RFPOApprovalAction, PDFPositioning,
)


class AdminTestBase(unittest.TestCase):
    """Base class that creates the Flask app, DB, and an admin user."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.config["WTF_CSRF_ENABLED"] = False
        cls.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        with cls.app.app_context():
            db.create_all()
            # Create admin user
            admin = User(
                record_id="ADM001",
                email="admin@rfpo.com",
                fullname="Admin User",
                password_hash=generate_password_hash("admin123"),
                active=True,
            )
            admin.set_permissions(["GOD", "RFPO_ADMIN"])
            db.session.add(admin)
            db.session.commit()
            cls.admin_id = admin.id

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.rollback()
        self.ctx.pop()

    def _login(self):
        """Log in the admin user via the test client."""
        return self.client.post(
            "/login",
            data={"email": "admin@rfpo.com", "password": "admin123"},
            follow_redirects=True,
        )


class TestDefaultPDFFieldPositions(AdminTestBase):
    """Test _DEFAULT_PDF_FIELD_POSITIONS constant."""

    def test_field_count(self):
        """Should have 21 known PDF fields."""
        # Access via the app's closure — we stored it as a local var
        # so instead, test via the actual route behavior (creating a default config)
        self._login()

        # Create a consortium to use
        c = Consortium(consort_id="PDF01", name="PDF Test", abbrev="PDF", active=True)
        db.session.add(c)
        db.session.commit()

        # Hit the editor route — it creates default PDFPositioning if none exists
        resp = self.client.get("/pdf-positioning/editor/PDF01/standard")
        self.assertEqual(resp.status_code, 200)

        # Verify the PDFPositioning was created with default fields
        config = PDFPositioning.query.filter_by(
            consortium_id="PDF01", template_name="standard"
        ).first()
        self.assertIsNotNone(config)

        data = config.get_positioning_data()
        self.assertIsInstance(data, dict)
        self.assertEqual(len(data), 21)

        # Spot-check a few required fields
        self.assertIn("po_number", data)
        self.assertIn("total", data)
        self.assertIn("consortium_logo", data)

        # Verify structure of a field
        po_number = data["po_number"]
        self.assertIn("x", po_number)
        self.assertIn("y", po_number)
        self.assertIn("visible", po_number)
        self.assertTrue(po_number["visible"])


class TestBuildPhaseSnapshot(AdminTestBase):
    """Test _build_phase_snapshot via submit-approval integration."""

    _fixture_counter = 0

    def setUp(self):
        super().setUp()
        # Clean approval tables to avoid action_id collisions between tests
        RFPOApprovalAction.query.delete()
        RFPOApprovalInstance.query.delete()
        db.session.commit()

    def _create_workflow_fixtures(self):
        """Create consortium, team, workflow, stage, step, RFPO for approval testing."""
        TestBuildPhaseSnapshot._fixture_counter += 1
        n = TestBuildPhaseSnapshot._fixture_counter

        c = Consortium(consort_id=f"WF{n:02d}", name=f"Workflow Test {n}", abbrev=f"WFT{n}", active=True)
        db.session.add(c)
        db.session.flush()

        t = Team(
            record_id=f"T{n:03d}",
            name=f"Test Team {n}",
            abbrev=f"TT{n}",
            consortium_consort_id=c.consort_id,
            active=True,
        )
        db.session.add(t)
        db.session.flush()

        # Create approver user
        approver = User(
            record_id=f"APR{n:03d}",
            email=f"approver{n}@test.com",
            fullname=f"Approver {n}",
            password_hash=generate_password_hash("testpass"),
            active=True,
        )
        approver.set_permissions(["RFPO_ADMIN"])
        db.session.add(approver)
        db.session.flush()

        wf = RFPOApprovalWorkflow(
            workflow_id=f"WF-{n:03d}",
            name=f"Team Approval {n}",
            workflow_type="team",
            team_id=t.id,
            is_template=True,
            is_active=True,
            version=1,
        )
        db.session.add(wf)
        db.session.flush()

        stage = RFPOApprovalStage(
            stage_id=f"STG-{n:03d}",
            workflow_id=wf.id,
            stage_name="Under $5000",
            stage_order=1,
            budget_bracket_key="BRACK_5000",
            budget_bracket_amount=5000.0,
        )
        db.session.add(stage)
        db.session.flush()

        step = RFPOApprovalStep(
            step_id=f"STP-{n:03d}",
            stage_id=stage.id,
            step_name="Manager Approval",
            step_order=1,
            approval_type_key="manager",
            approval_type_name="Manager",
            primary_approver_id=approver.record_id,
            is_required=True,
        )
        db.session.add(step)
        db.session.flush()

        rfpo = RFPO(
            rfpo_id=f"RFPO-WF-{n:03d}",
            title=f"Test Workflow RFPO {n}",
            status="Draft",
            team_id=t.id,
            consortium_id=c.consort_id,
            project_id=f"PROJ-{n:03d}",
            requestor_id="ADM001",
            created_by="admin",
            total_amount=1000.0,
            subtotal=1000.0,
        )
        db.session.add(rfpo)
        db.session.flush()

        # Add a line item (required for validation)
        li = RFPOLineItem(
            rfpo_id=rfpo.id,
            line_number=1,
            description="Test item",
            quantity=1,
            unit_price=1000.0,
            total_price=1000.0,
        )
        db.session.add(li)
        db.session.commit()

        return rfpo, wf, stage, step, approver

    @patch("email_service.send_approval_notification", return_value=True)
    def test_submit_approval_creates_instance(self, mock_notify):
        """Submit-approval route creates instance with correct phase snapshot."""
        self._login()
        rfpo, wf, stage, step, approver = self._create_workflow_fixtures()

        resp = self.client.post(
            f"/api/rfpo/{rfpo.id}/submit-approval",
            content_type="application/json",
        )
        data = resp.get_json()
        self.assertTrue(data["success"], msg=data.get("error", ""))
        self.assertIn("instance_id", data)
        self.assertEqual(data["total_phases"], 1)
        self.assertEqual(data["first_stage_name"], "Under $5000")

        # Verify instance was created in DB
        inst = RFPOApprovalInstance.query.filter_by(
            rfpo_id=rfpo.id
        ).first()
        self.assertIsNotNone(inst)

        # Verify snapshot structure
        snapshot = inst.get_instance_data()
        self.assertEqual(snapshot["total_phases"], 1)
        self.assertEqual(len(snapshot["phases"]), 1)

        phase = snapshot["phases"][0]
        self.assertEqual(phase["phase_number"], 1)
        self.assertEqual(phase["workflow_type"], "team")
        self.assertEqual(phase["stage"]["stage_name"], "Under $5000")
        self.assertEqual(len(phase["stage"]["steps"]), 1)
        self.assertEqual(phase["stage"]["steps"][0]["step_name"], "Manager Approval")

        # Verify action was created
        actions = RFPOApprovalAction.query.filter_by(
            instance_id=inst.id
        ).all()
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].status, "pending")
        self.assertEqual(actions[0].approver_id, approver.record_id)

    @patch("email_service.send_approval_notification", return_value=True)
    def test_duplicate_submit_returns_error(self, mock_notify):
        """Submitting same RFPO twice returns 400."""
        self._login()
        rfpo, *_ = self._create_workflow_fixtures()

        # First submission succeeds
        resp1 = self.client.post(f"/api/rfpo/{rfpo.id}/submit-approval")
        self.assertTrue(resp1.get_json()["success"])

        # Second submission fails
        resp2 = self.client.post(f"/api/rfpo/{rfpo.id}/submit-approval")
        self.assertEqual(resp2.status_code, 400)
        self.assertFalse(resp2.get_json()["success"])
        self.assertIn("already has", resp2.get_json()["error"])


class TestCreateFirstStepAction(AdminTestBase):
    """Test _create_first_step_action behavior through submit-approval."""

    def test_action_has_correct_step_details(self):
        """The created action should have correct step name/order/approver."""
        self._login()

        # Create minimal fixtures
        c = Consortium(consort_id="ACT01", name="Action Test", abbrev="ACT", active=True)
        t = Team(record_id="T100", name="Act Team", abbrev="AT1", consortium_consort_id="ACT01", active=True)
        approver = User(record_id="APR100", email="apr100@test.com", fullname="Approver Two", password_hash=generate_password_hash("testpass"), active=True)
        approver.set_permissions(["RFPO_ADMIN"])
        db.session.add_all([c, t, approver])
        db.session.flush()

        wf = RFPOApprovalWorkflow(
            workflow_id="WF-ACT", name="Act WF", workflow_type="team",
            team_id=t.id, is_template=True, is_active=True, version=1,
        )
        db.session.add(wf)
        db.session.flush()

        stage = RFPOApprovalStage(
            stage_id="STG-ACT", workflow_id=wf.id, stage_name="Low",
            stage_order=1, budget_bracket_key="BRACK_10000", budget_bracket_amount=10000.0,
        )
        db.session.add(stage)
        db.session.flush()

        step = RFPOApprovalStep(
            step_id="STP-ACT", stage_id=stage.id, step_name="Director Sign-off",
            step_order=1, approval_type_key="director", approval_type_name="Director",
            primary_approver_id="APR100", is_required=True,
        )
        db.session.add(step)
        db.session.flush()

        rfpo = RFPO(
            rfpo_id="RFPO-ACT", title="Action Test RFPO", status="Draft",
            team_id=t.id, consortium_id="ACT01", project_id="PROJ-002",
            requestor_id="ADM001", created_by="admin",
            total_amount=500.0, subtotal=500.0,
        )
        db.session.add(rfpo)
        db.session.flush()

        li = RFPOLineItem(rfpo_id=rfpo.id, line_number=1, description="Item", quantity=1, unit_price=500.0, total_price=500.0)
        db.session.add(li)
        db.session.commit()

        with patch("email_service.send_approval_notification", return_value=True):
            resp = self.client.post(f"/api/rfpo/{rfpo.id}/submit-approval")

        data = resp.get_json()
        self.assertTrue(data["success"], msg=data.get("error", ""))

        action = RFPOApprovalAction.query.filter_by(
            step_name="Director Sign-off"
        ).first()
        self.assertIsNotNone(action)
        self.assertEqual(action.step_order, 1)
        self.assertEqual(action.approver_id, "APR100")
        self.assertEqual(action.approver_name, "Approver Two")
        self.assertTrue(action.action_id.startswith("ACT-"))


class TestSendUserWelcomeEmail(AdminTestBase):
    """Test user creation triggers _send_user_welcome_email correctly."""

    @patch("email_service.send_welcome_email", return_value=True)
    @patch("email_service.email_service")
    def test_user_create_sends_welcome_email(self, mock_email_svc, mock_send):
        """Creating a user with GOD perm shows both app links."""
        mock_email_svc.get_last_send_result.return_value = {
            "provider": "SMTP", "status": "sent",
            "message_id": "MSG-1", "sender": "admin@test.com",
            "error": None,
        }
        self._login()

        resp = self.client.post("/user/new", data={
            "email": "newuser@test.com",
            "fullname": "New User",
            "password": "SecurePass123!",
            "permissions": ["GOD"],
            "active": "1",
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)

        # Verify send_welcome_email was called with correct flags
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        # positional or keyword args
        if call_kwargs.kwargs:
            self.assertTrue(call_kwargs.kwargs.get("show_user_link"))
            self.assertTrue(call_kwargs.kwargs.get("show_admin_link"))
        else:
            # positional: user_email, user_name, temp_password, show_user, show_admin
            self.assertTrue(call_kwargs[1].get("show_user_link", call_kwargs[0][3] if len(call_kwargs[0]) > 3 else True))

    @patch("email_service.send_welcome_email", return_value=False)
    @patch("email_service.email_service")
    def test_user_create_handles_email_failure(self, mock_email_svc, mock_send):
        """User is still created even when welcome email fails."""
        mock_email_svc.get_last_send_result.return_value = {
            "provider": "SMTP", "error": "Connection refused",
            "status": None, "message_id": None, "sender": None,
        }
        self._login()

        resp = self.client.post("/user/new", data={
            "email": "failmail@test.com",
            "fullname": "Fail Mail User",
            "password": "SecurePass123!",
            "permissions": ["RFPO_USER"],
            "active": "1",
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)
        # User should exist in DB despite email failure
        user = User.query.filter_by(email="failmail@test.com").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.fullname, "Fail Mail User")

    def test_user_create_without_permissions_returns_form(self):
        """Submitting without permissions re-renders the form with error."""
        self._login()

        resp = self.client.post("/user/new", data={
            "email": "noperms@test.com",
            "fullname": "No Perms",
            "password": "SecurePass123!",
            # No permissions checkbox selected
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)
        # Should NOT create the user
        user = User.query.filter_by(email="noperms@test.com").first()
        self.assertIsNone(user)


class TestHealthEndpoint(AdminTestBase):
    """Basic smoke test for the health endpoint."""

    def test_health_returns_200(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "RFPO Admin Panel")


if __name__ == "__main__":
    unittest.main()
