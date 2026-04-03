"""
Production database migration script for security hardening sprint.

Adds:
- deleted_at column to rfpos table (soft delete support)
- audit_logs table with indexes
- Indexes on rfpos foreign keys

Safe to run multiple times (all operations are idempotent).
Works with both SQLite and PostgreSQL.

Usage:
    # Local SQLite
    python migrate_production.py

    # Azure PostgreSQL (reads DATABASE_URL from .env)
    python migrate_production.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from env_config import get_database_url


def run_migration():
    db_url = get_database_url()
    is_postgres = db_url.startswith("postgresql")

    print(f"Database: {'PostgreSQL' if is_postgres else 'SQLite'}")
    print(f"URL: {db_url[:50]}..." if len(db_url) > 50 else f"URL: {db_url}")

    if is_postgres:
        import psycopg2
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cursor = conn.cursor()
    else:
        import sqlite3
        db_path = db_url.replace("sqlite:///", "")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

    migrations = []

    # 1. Add deleted_at column to rfpos
    if is_postgres:
        migrations.append((
            "Add deleted_at to rfpos",
            """DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'rfpos' AND column_name = 'deleted_at'
                ) THEN
                    ALTER TABLE rfpos ADD COLUMN deleted_at TIMESTAMP NULL;
                END IF;
            END $$;"""
        ))
    else:
        migrations.append((
            "Add deleted_at to rfpos",
            "ALTER TABLE rfpos ADD COLUMN deleted_at DATETIME"
        ))

    # 2. Create audit_logs table
    if is_postgres:
        migrations.append((
            "Create audit_logs table",
            """CREATE TABLE IF NOT EXISTS audit_logs (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER REFERENCES users(id),
                user_email VARCHAR(255),
                action VARCHAR(64) NOT NULL,
                entity_type VARCHAR(64) NOT NULL,
                entity_id VARCHAR(64),
                details TEXT,
                ip_address VARCHAR(45),
                user_agent VARCHAR(512)
            );"""
        ))
    else:
        migrations.append((
            "Create audit_logs table",
            """CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER REFERENCES users(id),
                user_email VARCHAR(255),
                action VARCHAR(64) NOT NULL,
                entity_type VARCHAR(64) NOT NULL,
                entity_id VARCHAR(64),
                details TEXT,
                ip_address VARCHAR(45),
                user_agent VARCHAR(512)
            );"""
        ))

    # 3. Indexes (same syntax for both)
    index_migrations = [
        ("Index: rfpos.deleted_at", "CREATE INDEX IF NOT EXISTS idx_rfpo_deleted_at ON rfpos(deleted_at)"),
        ("Index: rfpos.project_id", "CREATE INDEX IF NOT EXISTS idx_rfpo_project ON rfpos(project_id)"),
        ("Index: rfpos.consortium_id", "CREATE INDEX IF NOT EXISTS idx_rfpo_consortium ON rfpos(consortium_id)"),
        ("Index: rfpos.vendor_id", "CREATE INDEX IF NOT EXISTS idx_rfpo_vendor ON rfpos(vendor_id)"),
        ("Index: rfpos.requestor_id", "CREATE INDEX IF NOT EXISTS idx_rfpo_requestor ON rfpos(requestor_id)"),
        ("Index: audit_logs entity", "CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity_type, entity_id)"),
        ("Index: audit_logs user+action", "CREATE INDEX IF NOT EXISTS idx_audit_user_action ON audit_logs(user_id, action)"),
        ("Index: audit_logs timestamp", "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)"),
    ]
    migrations.extend(index_migrations)

    # Run all migrations
    success = 0
    skipped = 0
    for name, sql in migrations:
        try:
            cursor.execute(sql)
            print(f"  OK: {name}")
            success += 1
        except Exception as e:
            err = str(e).lower()
            if "already exists" in err or "duplicate" in err:
                print(f"  SKIP: {name} (already exists)")
                skipped += 1
            else:
                print(f"  FAIL: {name} - {e}")

    if not is_postgres:
        conn.commit()

    cursor.close()
    conn.close()

    print(f"\nMigration complete: {success} applied, {skipped} skipped")


if __name__ == "__main__":
    run_migration()
