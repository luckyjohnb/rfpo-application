#!/usr/bin/env python3
"""
Create Admin User for Custom Admin Panel
Creates admin@rfpo.com / admin123 user in the SQLAlchemy database (rfpo_admin.db)
"""

import os
import sys
from werkzeug.security import generate_password_hash
from datetime import datetime

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import models and database
from models import db, User


def create_admin_app():
    """Create Flask app with same config as custom_admin.py"""
    from flask import Flask

    app = Flask(__name__)

    # Use same configuration as custom_admin.py
    app.config["SECRET_KEY"] = "rfpo-admin-secret-key-change-in-production"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///rfpo_admin.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialize database
    db.init_app(app)

    return app


def create_admin_user():
    """Create the admin user for custom admin panel"""
    print("🔧 Creating Admin User for Custom Admin Panel...")
    print("=" * 60)

    app = create_admin_app()

    with app.app_context():
        try:
            # Create all database tables if they don't exist
            db.create_all()
            print("✅ Database tables initialized")

            # Check if admin user already exists
            existing_admin = User.query.filter_by(email="admin@rfpo.com").first()
            if existing_admin:
                print("✅ Admin user already exists!")
                print(f"   Email: {existing_admin.email}")
                print(f"   Full Name: {existing_admin.fullname}")
                print(f"   Active: {existing_admin.active}")
                print(f"   Created: {existing_admin.created_at}")
                return True

            # Generate next record ID
            max_user = User.query.order_by(User.record_id.desc()).first()
            if max_user and max_user.record_id:
                try:
                    next_id = int(max_user.record_id) + 1
                except ValueError:
                    next_id = 1
            else:
                next_id = 1

            record_id = f"{next_id:08d}"  # 8-digit padded ID

            # Create admin user
            print("📝 Creating admin user...")
            admin_user = User(
                record_id=record_id,
                fullname="System Administrator",
                email="admin@rfpo.com",
                password_hash=generate_password_hash("admin123"),
                company="RFPO Admin",
                position="Administrator",
                active=True,
                agreed_to_terms=True,
                created_by="setup_script",
                created_at=datetime.utcnow(),
            )

            # Set admin permissions (GOD = Super Admin)
            admin_user.set_permissions(["GOD", "RFPO_ADMIN", "RFPO_USER"])

            # Add to database
            db.session.add(admin_user)
            db.session.commit()

            print("✅ Admin user created successfully!")
            print("=" * 60)
            print("📋 ADMIN LOGIN CREDENTIALS:")
            print("   Email: admin@rfpo.com")
            print("   Password: admin123")
            print("   Record ID:", record_id)
            print("   Permissions: GOD, RFPO_ADMIN, RFPO_USER")
            print("=" * 60)
            print("🌐 You can now login to the custom admin panel:")
            print("   python custom_admin.py")
            print("   http://127.0.0.1:5111/")
            print("=" * 60)

            return True

        except Exception as e:
            print(f"❌ Error creating admin user: {str(e)}")
            import traceback

            traceback.print_exc()
            return False


def verify_admin_user():
    """Verify the admin user can be authenticated"""
    print("\n🔍 Verifying admin user...")

    app = create_admin_app()

    with app.app_context():
        try:
            from werkzeug.security import check_password_hash

            # Find the admin user
            admin_user = User.query.filter_by(email="admin@rfpo.com").first()
            if not admin_user:
                print("❌ Admin user not found!")
                return False

            # Check password
            if check_password_hash(admin_user.password_hash, "admin123"):
                print("✅ Password verification successful!")
                print(f"   User: {admin_user.fullname}")
                print(f"   Email: {admin_user.email}")
                print(f"   Active: {admin_user.active}")
                print(f"   Permissions: {admin_user.get_permissions()}")

                # Check admin privileges
                if admin_user.is_super_admin():
                    print("✅ Super admin privileges: YES")
                elif admin_user.is_rfpo_admin():
                    print("✅ RFPO admin privileges: YES")
                else:
                    print("⚠️  Admin privileges: LIMITED")

                return True
            else:
                print("❌ Password verification failed!")
                return False

        except Exception as e:
            print(f"❌ Error verifying admin user: {str(e)}")
            return False


def main():
    """Main function"""
    print("🚀 RFPO Custom Admin Panel - Admin User Setup")
    print("=" * 60)

    # Check if we're in the right directory
    if not os.path.exists("models.py"):
        print("❌ Error: models.py not found!")
        print("   Make sure you're running this from the project directory.")
        sys.exit(1)

    # Create admin user
    success = create_admin_user()

    if success:
        # Verify the user works
        verify_success = verify_admin_user()

        if verify_success:
            print("\n🎉 Setup completed successfully!")
            print("Next steps:")
            print("1. Run: python custom_admin.py")
            print("2. Open: http://127.0.0.1:5111/")
            print("3. Login: admin@rfpo.com / admin123")
        else:
            print("\n⚠️  User created but verification failed!")
            print("You may still be able to login to the admin panel.")
    else:
        print("\n❌ Setup failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
