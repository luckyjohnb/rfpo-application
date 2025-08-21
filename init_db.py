#!/usr/bin/env python3
"""Initialize database tables"""

from models import db, Team
from app import app

def init_database():
    """Create all database tables"""
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("✅ Database tables created successfully!")

        # Check if we can query the teams table
        try:
            teams_count = Team.query.count()
            print(f"✅ Teams table is ready. Current teams count: {teams_count}")
        except Exception as e:
            print(f"⚠️ Error checking teams table: {e}")

if __name__ == "__main__":
    init_database()
