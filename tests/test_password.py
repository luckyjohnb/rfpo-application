#!/usr/bin/env python3
"""
Password verification test
"""

import bcrypt
import json


def test_password_hash():
    """Test if the stored password hash works with the expected password"""

    # Load users.json
    with open("config/users.json", "r") as f:
        data = json.load(f)

    # Get admin user
    admin_user = None
    for user in data["users"]:
        if user["username"] == "admin":
            admin_user = user
            break

    if not admin_user:
        print("❌ Admin user not found!")
        return False

    print("=== PASSWORD VERIFICATION TEST ===")
    print(f"Username: {admin_user['username']}")
    print(f"Stored hash: {admin_user['password_hash']}")

    # Test password
    test_password = "admin"
    print(f"Testing password: '{test_password}'")

    try:
        # Verify using bcrypt
        result = bcrypt.checkpw(
            test_password.encode("utf-8"), admin_user["password_hash"].encode("utf-8")
        )
        print(f"Verification result: {result}")

        if result:
            print("✅ Password verification SUCCESSFUL!")
            return True
        else:
            print("❌ Password verification FAILED!")
            return False

    except Exception as e:
        print(f"❌ Error during verification: {e}")
        return False


if __name__ == "__main__":
    test_password_hash()
