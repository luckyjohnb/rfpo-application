#!/usr/bin/env python3
"""
Comprehensive schema checker and fixer for all models
"""

import os
import sys
from env_config import get_database_url

# Load DATABASE_URL from environment variables
os.environ["DATABASE_URL"] = get_database_url()

from flask import Flask
from models import db
from sqlalchemy import text, inspect


def create_app():
    """Create Flask app with proper configuration"""
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    return app


def check_and_fix_all_schemas(app):
    """Check all tables and add missing columns"""
    with app.app_context():
        try:
            inspector = inspect(db.engine)

            # Get all tables
            tables = inspector.get_table_names()
            print(f"📊 Found {len(tables)} tables in database")

            # Tables that commonly have created_by/updated_by
            tables_to_check = ["teams", "projects", "vendors", "vendor_sites"]

            for table_name in tables_to_check:
                if table_name not in tables:
                    print(f"⚠️  Table {table_name} doesn't exist, skipping...")
                    continue

                print(f"\n🔍 Checking {table_name} table...")
                columns = [col["name"] for col in inspector.get_columns(table_name)]

                with db.engine.connect() as conn:
                    # Check for created_by
                    if "created_by" not in columns:
                        print(f"  📝 Adding created_by to {table_name}...")
                        conn.execute(
                            text(
                                f"""
                            ALTER TABLE {table_name} 
                            ADD COLUMN created_by VARCHAR(64)
                        """
                            )
                        )
                        conn.commit()
                        print(f"  ✅ Added created_by")
                    else:
                        print(f"  ✓ created_by exists")

                    # Check for updated_by
                    if "updated_by" not in columns:
                        print(f"  📝 Adding updated_by to {table_name}...")
                        conn.execute(
                            text(
                                f"""
                            ALTER TABLE {table_name} 
                            ADD COLUMN updated_by VARCHAR(64)
                        """
                            )
                        )
                        conn.commit()
                        print(f"  ✅ Added updated_by")
                    else:
                        print(f"  ✓ updated_by exists")

            print("\n✅ All schema checks completed!")
            return True

        except Exception as e:
            print(f"❌ Error checking schemas: {e}")
            import traceback

            traceback.print_exc()
            return False


if __name__ == "__main__":
    print("🔧 Comprehensive Schema Checker and Fixer")
    print("=" * 50)

    app = create_app()
    success = check_and_fix_all_schemas(app)

    if success:
        print("\n✅ Schema checks completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Schema checks failed!")
        sys.exit(1)
