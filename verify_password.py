#!/usr/bin/env python3
"""
Simple password verification test
"""

import bcrypt
import json
import sys
import os

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_password_verification():
    """Test password verification directly"""
    print("=== PASSWORD VERIFICATION TEST ===")

    # Load users.json
    try:
        with open('config/users.json', 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Error loading users.json: {e}")
        return False

    # Find admin user
    admin_user = None
    for user in data['users']:
        if user['username'] == 'admin':
            admin_user = user
            break

    if not admin_user:
        print("❌ Admin user not found!")
        return False

    print(f"✅ Admin user found: {admin_user['username']}")
    print(f"📧 Email: {admin_user['email']}")
    print(f"🔑 Password hash: {admin_user['password_hash']}")
    print(f"🎭 Roles: {admin_user['roles']}")
    print(f"📊 Status: {admin_user['status']}")
    print(f"🔢 Login attempts: {admin_user.get('login_attempts', 0)}")

    # Test password verification
    test_password = "admin"
    print(f"\n🔍 Testing password: '{test_password}'")

    try:
        # Direct bcrypt verification
        result = bcrypt.checkpw(
            test_password.encode('utf-8'),
            admin_user['password_hash'].encode('utf-8')
        )
        print(f"🔐 Direct bcrypt verification: {result}")

        if result:
            print("✅ Password verification SUCCESSFUL!")
            return True
        else:
            print("❌ Password verification FAILED!")

            # Try generating a new hash for comparison
            print("\n🔧 Generating new hash for comparison...")
            new_hash = bcrypt.hashpw(test_password.encode('utf-8'), bcrypt.gensalt())
            print(f"🆕 New hash: {new_hash.decode('utf-8')}")

            # Test the new hash
            new_result = bcrypt.checkpw(test_password.encode('utf-8'), new_hash)
            print(f"🧪 New hash verification: {new_result}")

            return False

    except Exception as e:
        print(f"❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_password_verification()
    print(f"\n{'='*50}")
    if success:
        print("🎉 PASSWORD TEST PASSED")
    else:
        print("💔 PASSWORD TEST FAILED")
    print("="*50)
