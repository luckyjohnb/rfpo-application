#!/usr/bin/env python3
"""
Migration Script: Add Approver Tracking to Users
Adds is_approver and approver_updated_at columns to the users table
and syncs the initial approver status for all existing users.

Usage in Docker:
docker exec -it rfpo-admin python migrate_add_approver_tracking.py
"""

import os
import sys
from datetime import datetime

# Add the parent directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import db, User
from custom_admin import create_app, sync_all_users_approver_status


def migrate_add_approver_tracking():
    """Add approver tracking columns and sync initial status"""

    app = create_app()

    with app.app_context():
        try:
            print("🔄 Starting approver tracking migration...")

            # Check if columns already exist
            inspector = db.inspect(db.engine)
            columns = [col["name"] for col in inspector.get_columns("users")]

            if "is_approver" in columns and "approver_updated_at" in columns:
                print("✅ Approver tracking columns already exist")
            else:
                print("📝 Adding approver tracking columns to users table...")

                # Add the new columns using raw SQL since SQLAlchemy might not detect schema changes
                with db.engine.connect() as conn:
                    # Add is_approver column
                    if "is_approver" not in columns:
                        conn.execute(
                            db.text(
                                "ALTER TABLE users ADD COLUMN is_approver BOOLEAN DEFAULT FALSE"
                            )
                        )
                        print("   ✓ Added is_approver column")

                    # Add approver_updated_at column
                    if "approver_updated_at" not in columns:
                        conn.execute(
                            db.text(
                                "ALTER TABLE users ADD COLUMN approver_updated_at DATETIME"
                            )
                        )
                        print("   ✓ Added approver_updated_at column")

                    conn.commit()

            # Sync approver status for all existing users
            print("🔄 Syncing approver status for all users...")
            updated_count = sync_all_users_approver_status(
                updated_by="migration_script"
            )

            print(f"✅ Migration completed successfully!")
            print(f"   📊 Updated approver status for {updated_count} users")

            # Show summary of approvers
            approvers = User.query.filter_by(is_approver=True).all()
            if approvers:
                print(f"   👥 Found {len(approvers)} users with approver roles:")
                for user in approvers[:10]:  # Show first 10
                    summary = user.get_approver_summary()
                    print(
                        f"      • {user.get_display_name()} ({user.email}): {summary['assignments_summary']}"
                    )
                if len(approvers) > 10:
                    print(f"      ... and {len(approvers) - 10} more")
            else:
                print("   ℹ️  No users currently assigned as approvers")

            return True

        except Exception as e:
            print(f"❌ Migration failed: {str(e)}")
            import traceback

            traceback.print_exc()
            return False


def verify_migration():
    """Verify the migration was successful"""

    app = create_app()

    with app.app_context():
        try:
            print("\n🔍 Verifying migration...")

            # Check columns exist
            inspector = db.inspect(db.engine)
            columns = [col["name"] for col in inspector.get_columns("users")]

            required_columns = ["is_approver", "approver_updated_at"]
            missing_columns = [col for col in required_columns if col not in columns]

            if missing_columns:
                print(f"❌ Missing columns: {missing_columns}")
                return False

            print("✅ All required columns present")

            # Check if approver status is working
            total_users = User.query.count()
            approver_users = User.query.filter_by(is_approver=True).count()

            print(f"📊 Database status:")
            print(f"   • Total users: {total_users}")
            print(f"   • Users with approver status: {approver_users}")

            # Test a user's approver summary method
            test_user = User.query.first()
            if test_user:
                summary = test_user.get_approver_summary()
                print(
                    f"   • Sample user ({test_user.email}) approver status: {summary['is_approver']}"
                )

            print("✅ Migration verification successful")
            return True

        except Exception as e:
            print(f"❌ Verification failed: {str(e)}")
            import traceback

            traceback.print_exc()
            return False


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 RFPO Approver Tracking Migration")
    print("=" * 60)

    # Run migration
    success = migrate_add_approver_tracking()

    if success:
        # Verify migration
        verify_migration()
        print("\n🎉 Migration completed successfully!")
        print(
            "💡 You can now use the approver tracking features in the admin panel and API"
        )
    else:
        print("\n💥 Migration failed! Please check the error messages above.")
        sys.exit(1)

    print("=" * 60)
