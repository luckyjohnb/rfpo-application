#!/usr/bin/env python3
"""
Reset Admin User Password to a Custom Password
Updates admin@rfpo.com password for any database (local or Azure)
"""

import os
import sys
from werkzeug.security import generate_password_hash
from datetime import datetime


def create_app(database_url):
    """Create Flask app with specified database URL"""
    from flask import Flask
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Import and initialize db
    from models import db
    db.init_app(app)
    
    return app, db


def reset_admin_password(database_url, new_password, env_name="Database"):
    """Reset the admin user password to the specified value"""
    try:
        print(f"\n📝 Resetting password for {env_name}...")
        print(f"   Database: {database_url[:60]}...")
        
        app, db = create_app(database_url)
        
        with app.app_context():
            # Import User model
            from models import User
            
            # Find the admin user
            admin_user = User.query.filter_by(email='admin@rfpo.com').first()
            
            if not admin_user:
                print(f"❌ Admin user not found in {env_name}!")
                return False
            
            print(f"👤 Found admin user: {admin_user.fullname}")
            
            # Generate new password hash using Werkzeug
            new_password_hash = generate_password_hash(new_password)
            
            # Update the user's password hash
            admin_user.password_hash = new_password_hash
            admin_user.updated_at = datetime.utcnow()
            admin_user.updated_by = 'reset_admin_password_script'
            
            db.session.commit()
            
            print(f"✅ Password reset successfully for {env_name}!")
            print("   Email: admin@rfpo.com")
            print(f"   New Password: {new_password}")
            
            return True
        
    except Exception as e:
        print(f"❌ Password reset failed for {env_name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function to reset passwords for local and Azure databases"""
    print("🚀 Admin Password Reset Utility")
    print("=" * 70)
    
    # Check if we're in the right directory
    if not os.path.exists('models.py'):
        print("❌ Error: models.py not found!")
        print("   Make sure you're running this from the project directory.")
        sys.exit(1)
    
    new_password = "2026$Covid"
    azure_db_url = None
    
    # Reset local database using absolute path
    print("\n🔷 LOCAL DATABASE")
    print("-" * 70)
    # Ensure instance directory exists
    os.makedirs('instance', exist_ok=True)
    # Use absolute path for SQLite DB
    project_root = os.path.dirname(os.path.abspath(__file__))
    local_db_path = os.path.join(project_root, 'instance', 'rfpo_admin.db')
    local_db_url = f"sqlite:///{local_db_path}"
    local_success = reset_admin_password(
        local_db_url, new_password, "Local SQLite DB"
    )
    
    # Reset Azure database (if DATABASE_URL is configured)
    print("\n🔵 AZURE PRODUCTION DATABASE")
    print("-" * 70)
    try:
        from env_config import get_database_url
        azure_db_url = get_database_url()

        # Only proceed if it's actually a PostgreSQL URL
        if 'postgresql' in azure_db_url:
            azure_success = reset_admin_password(
                azure_db_url, new_password, "Azure PostgreSQL DB"
            )
        else:
            print("⚠️  Skipping Azure reset: DATABASE_URL is not PostgreSQL")
            print(f"   Current URL: {azure_db_url[:60]}...")
            azure_success = True  # Don't fail, just skip
    except Exception as e:
        print(f"⚠️  Could not load Azure database URL: {e}")
        msg = "   If you want to reset Azure password, ensure "
        msg += "DATABASE_URL is set in .env"
        print(msg)
        azure_success = True  # Don't fail, just skip
    
    # Summary
    print("\n" + "=" * 70)
    print("📋 SUMMARY")
    print("=" * 70)
    
    if local_success:
        print("✅ Local database password reset successful")
    else:
        print("❌ Local database password reset FAILED")
    
    if azure_success:
        if azure_db_url and 'postgresql' in azure_db_url:
            print("✅ Azure database password reset successful")
        else:
            msg = "⊘  Azure database reset skipped "
            msg += "(not configured as PostgreSQL)"
            print(msg)
    else:
        print("❌ Azure database password reset FAILED")
    
    # Final credentials
    print("\n" + "=" * 70)
    print("🔐 UPDATED LOGIN CREDENTIALS")
    print("=" * 70)
    print("📧 Email: admin@rfpo.com")
    print("🔑 Password: 2026$Covid")
    print("\nLocal Admin Panel: http://localhost:5111/")
    azure_url = "https://rfpo-admin.livelyforest-d06a98a0.eastus"
    azure_url += ".azurecontainerapps.io/"
    print(f"Azure Admin Panel: {azure_url}")
    print("=" * 70)
    
    # Exit with appropriate code
    if local_success and azure_success:
        print("\n🎉 All password resets completed successfully!")
        sys.exit(0)
    else:
        print("\n⚠️  Some password resets failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
