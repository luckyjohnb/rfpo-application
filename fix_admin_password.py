#!/usr/bin/env python3
"""
Fix Admin User Password Hash
Updates the admin user password to use Werkzeug hash format instead of bcrypt
"""

import os
import sys
from werkzeug.security import generate_password_hash
from env_config import get_database_url

# Load DATABASE_URL from environment variables
os.environ['DATABASE_URL'] = get_database_url()

# Import Flask and SQLAlchemy models
from flask import Flask
from models import db, User


def create_app():
    """Create Flask app with proper configuration"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    return app


def fix_admin_password():
    """Fix the admin user password hash to use Werkzeug format"""
    try:
        print("🔌 Creating Flask app...")
        app = create_app()
        
        with app.app_context():
            # Find the admin user
            admin_user = User.query.filter_by(email='admin@rfpo.com').first()
            
            if not admin_user:
                print("❌ Admin user not found!")
                return False
            
            print("👤 Found admin user, updating password hash...")
            
            # Generate new password hash using Werkzeug (same format as Flask-Login expects)
            new_password_hash = generate_password_hash('admin123')
            
            # Update the user's password hash
            admin_user.password_hash = new_password_hash
            db.session.commit()
            
            print("✅ Admin user password hash updated successfully!")
            print("📧 Admin Login: admin@rfpo.com")
            print("🔐 Admin Password: admin123")
            print("🔧 Hash format: Werkzeug (compatible with Flask-Login)")
            
            return True
        
    except Exception as e:
        print(f"❌ Password hash update failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🚀 Fixing Admin User Password Hash")
    print("=" * 50)
    
    success = fix_admin_password()
    
    if success:
        print("\n✅ Password hash fix completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Password hash fix failed!")
        sys.exit(1)