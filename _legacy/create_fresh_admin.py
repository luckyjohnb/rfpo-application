#!/usr/bin/env python3
"""
Create fresh admin user with Administrator123! password
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from user_management import UserManager

print("🔧 Creating fresh admin user...")

# Create UserManager
um = UserManager()

# Create admin user with the expected password
result = um.create_user(
    username="admin",
    email="admin@example.com",
    password="Administrator123!",
    display_name="System Administrator",
    roles=["Administrator"],
    status="active"
)

print(f"Create result: {result}")

if result.get('success'):
    print("✅ Admin user created successfully!")

    # Test authentication immediately
    auth_result = um.authenticate_user("admin", "Administrator123!")
    if auth_result:
        print("✅ Authentication test PASSED!")
        print(f"User: {auth_result.get('username')}")
        print(f"Roles: {auth_result.get('roles')}")
    else:
        print("❌ Authentication test FAILED!")

    print("\n" + "="*50)
    print("LOGIN CREDENTIALS:")
    print("Username: admin")
    print("Password: Administrator123!")
    print("="*50)
else:
    print(f"❌ Failed to create admin user: {result.get('message')}")
