#!/usr/bin/env python3
"""
Unit tests for model type hints and method correctness.

Covers:
- User: permissions, display name, admin flags, team membership
- Consortium: viewer/admin user ID getters/setters
- RFPO: soft delete, cost sharing, total calculations, to_dict
- AuditLog: details getter/setter, to_dict
"""

import json
import os
import sys
import unittest
from datetime import datetime
from werkzeug.security import generate_password_hash

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from models import db, User, Consortium, RFPO, RFPOLineItem, AuditLog, Team, UserTeam


def create_test_app():
    """Create a minimal Flask app with in-memory SQLite for testing."""
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["TESTING"] = True
    db.init_app(app)
    return app


class TestUserPermissions(unittest.TestCase):
    """Test User permission methods and type annotations."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_test_app()
        with cls.app.app_context():
            db.create_all()

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        # Clean users before each test
        User.query.delete()
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        self.ctx.pop()

    _user_counter = 0

    def _make_user(self, **kwargs):
        TestUserPermissions._user_counter += 1
        n = TestUserPermissions._user_counter
        defaults = {
            "record_id": f"U{n:04d}",
            "email": f"user{n}@test.com",
            "fullname": "Test User",
            "password_hash": generate_password_hash("testpass"),
            "active": True,
        }
        defaults.update(kwargs)
        u = User(**defaults)
        db.session.add(u)
        db.session.commit()
        return u

    # --- get_permissions / set_permissions ---

    def test_get_permissions_returns_list(self):
        u = self._make_user()
        result = u.get_permissions()
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    def test_set_and_get_permissions(self):
        u = self._make_user()
        u.set_permissions(["GOD", "RFPO_ADMIN"])
        db.session.commit()

        perms = u.get_permissions()
        self.assertEqual(perms, ["GOD", "RFPO_ADMIN"])

    def test_set_permissions_none_clears(self):
        u = self._make_user()
        u.set_permissions(["GOD"])
        db.session.commit()
        u.set_permissions([])
        db.session.commit()
        self.assertIsNone(u.permissions)
        self.assertEqual(u.get_permissions(), [])

    # --- has_permission ---

    def test_has_permission_true(self):
        u = self._make_user()
        u.set_permissions(["RFPO_USER"])
        self.assertTrue(u.has_permission("RFPO_USER"))

    def test_has_permission_false(self):
        u = self._make_user()
        u.set_permissions(["RFPO_USER"])
        self.assertFalse(u.has_permission("GOD"))

    # --- is_super_admin / is_rfpo_admin / is_rfpo_user ---

    def test_is_super_admin_with_god(self):
        u = self._make_user()
        u.set_permissions(["GOD"])
        self.assertTrue(u.is_super_admin())
        # GOD implies rfpo_admin and rfpo_user
        self.assertTrue(u.is_rfpo_admin())
        self.assertTrue(u.is_rfpo_user())

    def test_is_rfpo_admin_without_god(self):
        u = self._make_user()
        u.set_permissions(["RFPO_ADMIN"])
        self.assertFalse(u.is_super_admin())
        self.assertTrue(u.is_rfpo_admin())
        self.assertTrue(u.is_rfpo_user())

    def test_is_rfpo_user_only(self):
        u = self._make_user()
        u.set_permissions(["RFPO_USER"])
        self.assertFalse(u.is_super_admin())
        self.assertFalse(u.is_rfpo_admin())
        self.assertTrue(u.is_rfpo_user())

    def test_no_permissions_not_admin(self):
        u = self._make_user()
        self.assertFalse(u.is_super_admin())
        self.assertFalse(u.is_rfpo_admin())
        self.assertFalse(u.is_rfpo_user())

    # --- get_display_name ---

    def test_display_name_returns_fullname(self):
        u = self._make_user(fullname="Alice Smith")
        result = u.get_display_name()
        self.assertIsInstance(result, str)
        self.assertEqual(result, "Alice Smith")

    def test_display_name_falls_back_to_email(self):
        u = self._make_user(fullname="", email="alice@test.com")
        self.assertEqual(u.get_display_name(), "alice@test.com")

    # --- Return type annotations (runtime check) ---

    def test_return_types_at_runtime(self):
        u = self._make_user()
        u.set_permissions(["GOD"])
        self.assertIsInstance(u.get_permissions(), list)
        self.assertIsInstance(u.has_permission("GOD"), bool)
        self.assertIsInstance(u.is_super_admin(), bool)
        self.assertIsInstance(u.is_rfpo_admin(), bool)
        self.assertIsInstance(u.is_rfpo_user(), bool)
        self.assertIsInstance(u.get_display_name(), str)


class TestConsortiumMethods(unittest.TestCase):
    """Test Consortium viewer/admin user ID methods."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_test_app()
        with cls.app.app_context():
            db.create_all()

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        Consortium.query.delete()
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        self.ctx.pop()

    _consort_counter = 0

    def _make_consortium(self):
        TestConsortiumMethods._consort_counter += 1
        n = TestConsortiumMethods._consort_counter
        c = Consortium(
            consort_id=f"C{n:03d}",
            name=f"Test Consortium {n}",
            abbrev=f"TC{n}",
            active=True,
        )
        db.session.add(c)
        db.session.commit()
        return c

    def test_viewer_users_default_empty_list(self):
        c = self._make_consortium()
        result = c.get_rfpo_viewer_users()
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    def test_set_and_get_viewer_users(self):
        c = self._make_consortium()
        c.set_rfpo_viewer_users(["U001", "U002"])
        db.session.commit()
        self.assertEqual(c.get_rfpo_viewer_users(), ["U001", "U002"])

    def test_set_viewer_users_filters_empty_strings(self):
        c = self._make_consortium()
        c.set_rfpo_viewer_users(["U001", "", "U003"])
        db.session.commit()
        self.assertEqual(c.get_rfpo_viewer_users(), ["U001", "U003"])

    def test_admin_users_roundtrip(self):
        c = self._make_consortium()
        c.set_rfpo_admin_users(["A001"])
        db.session.commit()
        result = c.get_rfpo_admin_users()
        self.assertIsInstance(result, list)
        self.assertEqual(result, ["A001"])

    def test_clear_admin_users(self):
        c = self._make_consortium()
        c.set_rfpo_admin_users(["A001"])
        db.session.commit()
        c.set_rfpo_admin_users(None)
        db.session.commit()
        self.assertEqual(c.get_rfpo_admin_users(), [])

    def test_to_dict_returns_dict(self):
        c = self._make_consortium()
        d = c.to_dict()
        self.assertIsInstance(d, dict)
        self.assertIn("consort_id", d)
        self.assertIn("name", d)


class TestRFPOSoftDelete(unittest.TestCase):
    """Test RFPO soft delete and total calculations."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_test_app()
        with cls.app.app_context():
            db.create_all()

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        RFPO.query.delete()
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        self.ctx.pop()

    _rfpo_counter = 0

    def _make_rfpo(self, **kwargs):
        TestRFPOSoftDelete._rfpo_counter += 1
        n = TestRFPOSoftDelete._rfpo_counter
        defaults = {
            "rfpo_id": f"RFPO-{n:03d}",
            "title": "Test RFPO",
            "status": "Draft",
            "project_id": "PROJ-001",
            "consortium_id": "C001",
            "requestor_id": "U001",
            "created_by": "admin",
        }
        defaults.update(kwargs)
        r = RFPO(**defaults)
        db.session.add(r)
        db.session.commit()
        return r

    # --- is_deleted / soft_delete ---

    def test_new_rfpo_is_not_deleted(self):
        r = self._make_rfpo()
        self.assertIsInstance(r.is_deleted, bool)
        self.assertFalse(r.is_deleted)
        self.assertIsNone(r.deleted_at)

    def test_soft_delete_sets_timestamp(self):
        r = self._make_rfpo()
        r.soft_delete()
        db.session.commit()

        self.assertTrue(r.is_deleted)
        self.assertIsNotNone(r.deleted_at)
        self.assertIsInstance(r.deleted_at, datetime)

    def test_soft_deleted_rfpo_still_exists_in_db(self):
        r = self._make_rfpo()
        r.soft_delete()
        db.session.commit()

        found = RFPO.query.get(r.id)
        self.assertIsNotNone(found)
        self.assertTrue(found.is_deleted)

    # --- Cost sharing calculations ---

    def test_cost_share_percent(self):
        r = self._make_rfpo(
            subtotal=1000.0,
            cost_share_type="percent",
            cost_share_amount=10.0,
        )
        share = r.get_calculated_cost_share_amount()
        self.assertIsInstance(share, float)
        self.assertAlmostEqual(share, 100.0)

    def test_cost_share_dollar(self):
        r = self._make_rfpo(
            subtotal=1000.0,
            cost_share_type="dollar",
            cost_share_amount=250.0,
        )
        share = r.get_calculated_cost_share_amount()
        self.assertAlmostEqual(share, 250.0)

    def test_cost_share_none(self):
        r = self._make_rfpo(subtotal=1000.0)
        share = r.get_calculated_cost_share_amount()
        self.assertAlmostEqual(share, 0.0)

    def test_total_amount_with_cost_share(self):
        r = self._make_rfpo(
            subtotal=1000.0,
            cost_share_type="percent",
            cost_share_amount=20.0,
        )
        total = r.get_calculated_total_amount()
        self.assertIsInstance(total, float)
        self.assertAlmostEqual(total, 800.0)

    def test_update_totals_with_line_items(self):
        r = self._make_rfpo()
        li1 = RFPOLineItem(rfpo_id=r.id, line_number=1, description="Item A", total_price=500.0, quantity=1)
        li2 = RFPOLineItem(rfpo_id=r.id, line_number=2, description="Item B", total_price=300.0, quantity=1)
        db.session.add_all([li1, li2])
        db.session.commit()

        # Refresh to load line items
        db.session.refresh(r)
        r.update_totals()
        self.assertAlmostEqual(r.subtotal, 800.0)
        self.assertAlmostEqual(r.total_amount, 800.0)


class TestAuditLog(unittest.TestCase):
    """Test AuditLog model methods."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_test_app()
        with cls.app.app_context():
            db.create_all()

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        AuditLog.query.delete()
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        self.ctx.pop()

    def test_set_and_get_details(self):
        log = AuditLog(
            action="login",
            entity_type="user",
            entity_id="1",
        )
        log.set_details({"ip": "127.0.0.1", "browser": "Chrome"})
        db.session.add(log)
        db.session.commit()

        details = log.get_details()
        self.assertIsInstance(details, dict)
        self.assertEqual(details["ip"], "127.0.0.1")

    def test_get_details_empty(self):
        log = AuditLog(action="test", entity_type="test")
        result = log.get_details()
        self.assertIsInstance(result, dict)
        self.assertEqual(result, {})

    def test_set_details_none(self):
        log = AuditLog(action="test", entity_type="test")
        log.set_details(None)
        self.assertIsNone(log.details)

    def test_to_dict_returns_dict(self):
        log = AuditLog(
            action="export",
            entity_type="rfpo",
            entity_id="RFPO-001",
            user_email="admin@test.com",
        )
        db.session.add(log)
        db.session.commit()

        d = log.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["action"], "export")
        self.assertEqual(d["entity_type"], "rfpo")
        self.assertEqual(d["entity_id"], "RFPO-001")
        self.assertEqual(d["user_email"], "admin@test.com")
        self.assertIn("timestamp", d)
        self.assertIn("details", d)

    def test_to_dict_with_details(self):
        log = AuditLog(action="delete", entity_type="user", entity_id="5")
        log.set_details({"reason": "inactive"})
        db.session.add(log)
        db.session.commit()

        d = log.to_dict()
        self.assertEqual(d["details"]["reason"], "inactive")


if __name__ == "__main__":
    unittest.main()
