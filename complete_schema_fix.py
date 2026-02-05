#!/usr/bin/env python3
"""
Comprehensive Database Schema Fix for Azure PostgreSQL
This script drops existing tables and recreates them using SQLAlchemy models
to ensure complete schema compatibility
"""

import os
import sys
from werkzeug.security import generate_password_hash
from datetime import datetime
from env_config import get_database_url

# Load DATABASE_URL from environment variables
os.environ["DATABASE_URL"] = get_database_url()

# Import Flask and all SQLAlchemy models
from flask import Flask
from models import (
    db,
    User,
    Team,
    Consortium,
    Project,
    Vendor,
    VendorSite,
    RFPO,
    RFPOLineItem,
    UploadedFile,
    DocumentChunk,
    UserTeam,
    PDFPositioning,
    List,
    RFPOApprovalWorkflow,
    RFPOApprovalStage,
    RFPOApprovalStep,
)


def create_app():
    """Create Flask app with proper configuration"""
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    return app


def recreate_database_schema():
    """Drop all tables and recreate them using SQLAlchemy models"""
    try:
        print("🔌 Creating Flask app...")
        app = create_app()

        with app.app_context():
            print("🗑️  Dropping all existing tables...")
            # Drop all tables to start fresh
            db.drop_all()
            print("✅ All tables dropped")

            print("🔧 Creating all tables from SQLAlchemy models...")
            # Create all tables from models
            db.create_all()
            print("✅ All tables created successfully")

            # Verify tables were created
            from sqlalchemy import text

            result = db.session.execute(
                text(
                    """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """
                )
            )
            tables = [row[0] for row in result.fetchall()]

            print(f"📋 Created {len(tables)} tables:")
            for table in tables:
                print(f"   ✓ {table}")

            # Create admin user with Werkzeug-compatible hash
            print("👤 Creating admin user...")
            password_hash = generate_password_hash("admin123")

            admin_user = User(
                record_id="ADM00000001",
                fullname="System Administrator",
                email="admin@rfpo.com",
                password_hash=password_hash,
                permissions='["GOD"]',
                global_admin=True,
                active=True,
                use_rfpo=True,
                agreed_to_terms=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                created_by="system",
                updated_by="system",
            )

            db.session.add(admin_user)
            db.session.commit()

            print("✅ Admin user created successfully")

            # Verify user count
            user_count = User.query.count()
            print(f"👥 Total users in database: {user_count}")

            return True

    except Exception as e:
        print(f"❌ Database schema recreation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🚀 Starting Comprehensive Database Schema Fix")
    print("=" * 60)
    print("⚠️  WARNING: This will DROP ALL EXISTING DATA!")
    print("=" * 60)

    success = recreate_database_schema()

    if success:
        print("\n" + "=" * 60)
        print("✅ Database schema recreation completed successfully!")
        print("=" * 60)
        print("📧 Admin Login: admin@rfpo.com")
        print("🔐 Admin Password: admin123")
        print("🔧 Hash format: Werkzeug (compatible with Flask-Login)")
        print("🎯 All SQLAlchemy models properly synchronized")
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("❌ Database schema recreation failed!")
        print("=" * 60)
        sys.exit(1)
