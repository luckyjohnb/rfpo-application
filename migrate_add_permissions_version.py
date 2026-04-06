#!/usr/bin/env python3
"""
Migration Script: Add permissions_version to Users
Adds the permissions_version column used to invalidate JWT tokens when
a user's permissions are made more restrictive.

Usage:
  Local:  python migrate_add_permissions_version.py
  Docker: docker exec -it rfpo-admin python migrate_add_permissions_version.py
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import db
from custom_admin import create_app


def migrate():
    app = create_app()

    with app.app_context():
        inspector = db.inspect(db.engine)
        columns = [col["name"] for col in inspector.get_columns("users")]

        if "permissions_version" in columns:
            print("✅ permissions_version column already exists — nothing to do.")
            return True

        print("📝 Adding permissions_version column to users table...")
        with db.engine.connect() as conn:
            conn.execute(
                db.text(
                    "ALTER TABLE users ADD COLUMN permissions_version INTEGER NOT NULL DEFAULT 0"
                )
            )
            conn.commit()

        print("✅ Migration completed. All existing tokens remain valid (version 0).")
        return True


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)
