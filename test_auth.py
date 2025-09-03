#!/usr/bin/env python3
"""
Quick authentication test
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import db, User
from custom_admin import create_app
from werkzeug.security import check_password_hash
import jwt
from datetime import datetime, timedelta

# JWT Configuration
JWT_SECRET_KEY = 'dev-jwt-secret-change-in-production'

def test_user_auth(email, password):
    """Test user authentication logic"""
    app = create_app()
    with app.app_context():
        print(f"Testing authentication for: {email}")
        
        # Find user by email
        user = User.query.filter_by(email=email).first()
        if not user:
            print("❌ User not found")
            return None
        
        print(f"✅ User found: {user.fullname}")
        
        # Check if user is active
        if not user.active:
            print("❌ User is not active")
            return None
        
        print(f"✅ User is active")
        
        # Check password
        if not check_password_hash(user.password_hash, password):
            print("❌ Invalid password")
            return None
        
        print(f"✅ Password is valid")
        
        # Generate JWT token
        expiry = datetime.utcnow() + timedelta(hours=24)
        payload = {
            'user_id': user.id,
            'username': user.email,
            'exp': expiry
        }
        
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')
        
        result = {
            'success': True,
            'token': token,
            'user': {
                'id': user.id,
                'username': user.email,
                'display_name': user.fullname,
                'email': user.email,
                'roles': user.get_permissions()
            }
        }
        
        print(f"✅ Authentication successful!")
        print(f"Token: {token[:50]}...")
        print(f"Permissions: {user.get_permissions()}")
        
        return result

if __name__ == '__main__':
    print("=" * 60)
    print("🔐 TESTING AUTHENTICATION LOGIC")
    print("=" * 60)
    
    # Test with your user
    test_user_auth("casahome2000+newnew@gmail.com", "@34!pXgn5A6aAi6b")
    
    print("\n" + "-" * 60)
    
    # Test with admin user
    test_user_auth("admin@rfpo.com", "admin123")


