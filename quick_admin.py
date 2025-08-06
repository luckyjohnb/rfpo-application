#!/usr/bin/env python3
"""
Quick Admin User Creation Script
Creates admin user directly in JSON file
"""
import json
import os
import bcrypt

def create_admin_user():
    """Create admin user directly"""
    print("🔧 Creating Admin User...")
    
    # Create config directory
    os.makedirs('config', exist_ok=True)
    
    # Hash the password
    password = "Administrator123!"
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Create admin user data
    admin_user = {
        "admin": {
            "id": "admin-001",
            "username": "admin",
            "email": "admin@example.com",
            "password_hash": password_hash,
            "display_name": "System Administrator",
            "roles": ["Administrator"],
            "status": "active",
            "created_at": "2025-08-05T22:00:00Z",
            "last_login": None,
            "failed_login_attempts": 0,
            "locked_until": None,
            "audit_log": []
        }
    }
    
    # Write to file
    with open('config/users.json', 'w') as f:
        json.dump(admin_user, f, indent=2)
    
    print("✅ Admin user created successfully!")
    print("=" * 50)
    print("📋 LOGIN CREDENTIALS:")
    print("   Username: admin")
    print("   Password: Administrator123!")
    print("   Email: admin@example.com")
    print("=" * 50)
    print("🌐 You can now login to the application!")

if __name__ == '__main__':
    create_admin_user()
