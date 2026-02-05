#!/usr/bin/env python3
"""
Test full authentication flow with UserManager
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from user_management import UserManager


def test_full_authentication():
    """Test complete authentication flow"""
    print("=== FULL AUTHENTICATION TEST ===")

    # Create UserManager
    um = UserManager()

    # Test authentication
    username = "admin"
    password = "admin"

    print(f"🔐 Testing authentication for: {username}")
    print(f"🔑 Password: {password}")

    try:
        result = um.authenticate_user(username, password)
        print(f"🔍 Authentication result: {result}")

        if result:
            print("✅ AUTHENTICATION SUCCESSFUL!")
            print(f"👤 User ID: {result.get('id')}")
            print(f"👤 Username: {result.get('username')}")
            print(f"📧 Email: {result.get('email')}")
            print(f"🎭 Roles: {result.get('roles')}")
            print(f"📊 Status: {result.get('status')}")
            return True
        else:
            print("❌ AUTHENTICATION FAILED!")
            return False

    except Exception as e:
        print(f"❌ Error during authentication: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_full_authentication()
    print(f"\n{'='*60}")
    if success:
        print("🎉 FULL AUTHENTICATION TEST PASSED")
        print("✅ Ready to test Flask login endpoint")
    else:
        print("💔 FULL AUTHENTICATION TEST FAILED")
    print("=" * 60)
