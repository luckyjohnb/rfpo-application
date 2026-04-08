"""
Migration: Add reminder tracking columns to rfpo_approval_actions table.

Adds:
  - last_reminder_sent_utc (TIMESTAMP, nullable)
  - reminder_count (INTEGER, NOT NULL, default 0)

Safe to run multiple times — checks for column existence first.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from env_config import get_database_url
from models import db, RFPOApprovalAction

from flask import Flask


def migrate():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = get_database_url()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        inspector = db.inspect(db.engine)
        existing = [col["name"] for col in inspector.get_columns("rfpo_approval_actions")]

        with db.engine.connect() as conn:
            if "last_reminder_sent_utc" not in existing:
                conn.execute(db.text(
                    "ALTER TABLE rfpo_approval_actions ADD COLUMN last_reminder_sent_utc TIMESTAMP"
                ))
                print("Added column: last_reminder_sent_utc")
            else:
                print("Column already exists: last_reminder_sent_utc")

            if "reminder_count" not in existing:
                conn.execute(db.text(
                    "ALTER TABLE rfpo_approval_actions ADD COLUMN reminder_count INTEGER NOT NULL DEFAULT 0"
                ))
                print("Added column: reminder_count")
            else:
                print("Column already exists: reminder_count")

            conn.commit()

    print("Migration complete.")


if __name__ == "__main__":
    migrate()
