#!/usr/bin/env python3
"""
Direct authentication test - run this to test user authentication directly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from user_management import UserManager

def test_direct_authentication():
    """Test authentication directly without Flask"""
    print("=" * 60)
    print("🔐 DIRECT AUTHENTICATION TEST")
    print("=" * 60)

    # Create UserManager instance
    um = UserManager()

    # Print Python version and executable path
    print(f"🐍 Python Version: {sys.version}")
    print(f"🐍 Python Executable: {sys.executable}")
    print()

    # Test admin user authentication
    username = "admin"
    password = "admin"

    print(f"📝 Testing authentication for: {username}")
    print(f"🔑 Using password: {password}")
    print()

    try:
        # Load users and check structure
        data = um._load_data()
        users = {user['username']: user for user in data['users']}
        print(f"👥 Total users loaded: {len(users)}")

        if username in users:
            user_data = users[username]
            print(f"👤 User found: {username}")
            print(f"🎭 Role: {user_data.get('role', 'N/A')}")
            print(f"🔒 Password hash present: {'password' in user_data}")
            print(f"🚫 Account locked: {user_data.get('account_locked', False)}")
            print(f"❌ Failed attempts: {user_data.get('failed_attempts', 0)}")
            print()
        else:
            print(f"❌ User '{username}' not found in users database")
            print(f"Available users: {list(users.keys())}")
            return False

        # Attempt authentication
        print("🔐 Attempting authentication...")
        result = um.authenticate_user(username, password)

        if result:
            print("✅ Authentication SUCCESSFUL!")
            print(f"📊 Authentication result: {result}")
            return True
        else:
            print("❌ Authentication FAILED!")
            print(f"📊 Authentication result: {result}")
            return False

    except Exception as e:
        print(f"💥 Error during authentication: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_direct_authentication()
    print("\n" + "=" * 60)
    if success:
        print("🎉 AUTHENTICATION TEST PASSED")
    else:
        print("💔 AUTHENTICATION TEST FAILED")
    print("=" * 60)
