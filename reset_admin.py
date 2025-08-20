#!/usr/bin/env python3
"""
Reset admin user with correct password hash
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from user_management import UserManager
import json

def reset_admin_user():
    """Reset admin user with correct password hash"""

    print("=== ADMIN USER RESET ===")

    # Load current data
    with open('config/users.json', 'r') as f:
        data = json.load(f)

    # Create UserManager to generate correct hash
    um = UserManager()

    # Generate new password hash
    new_password = "admin"
    new_hash = um._hash_password(new_password)

    print(f"Original hash: {data['users'][0]['password_hash']}")
    print(f"New hash: {new_hash}")

    # Update admin user
    for user in data['users']:
        if user['username'] == 'admin':
            user['password_hash'] = new_hash
            user['login_attempts'] = 0
            user['locked_until'] = None
            user['failed_login_attempts'] = 0
            break

    # Save updated data
    with open('config/users.json', 'w') as f:
        json.dump(data, f, indent=2)

    print("✅ Admin user password hash updated!")

    # Test the new hash
    print("\n=== TESTING NEW HASH ===")
    result = um._verify_password(new_password, new_hash)
    print(f"Password verification: {result}")

    if result:
        print("✅ Password verification successful!")
    else:
        print("❌ Password verification failed!")

if __name__ == "__main__":
    reset_admin_user()
