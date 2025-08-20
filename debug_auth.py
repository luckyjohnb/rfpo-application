#!/usr/bin/env python3
import sys
import os
import json

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from user_management import UserManager

def debug_auth():
    print("=== AUTHENTICATION DEBUG ===")

    # Load the users.json file directly
    try:
        with open('config/users.json', 'r') as f:
            data = json.load(f)

        print(f"Users file loaded successfully")
        print(f"Number of users: {len(data.get('users', []))}")

        if data.get('users'):
            user = data['users'][0]
            print(f"First user username: {user.get('username')}")
            print(f"First user email: {user.get('email')}")
            print(f"First user status: {user.get('status')}")
            print(f"First user roles: {user.get('roles')}")
            print(f"Password hash starts with: {user.get('password_hash', '')[:20]}...")
            print(f"Login attempts: {user.get('login_attempts', 0)}")
            print(f"Locked until: {user.get('locked_until')}")
    except Exception as e:
        print(f"Error loading users.json: {e}")
        return

    # Test UserManager
    try:
        um = UserManager()
        print("\nUserManager created successfully")

        # Test authentication with different passwords
        test_passwords = ['admin', 'Administrator123!', 'password', 'test']

        for pwd in test_passwords:
            print(f"\nTesting password: '{pwd}'")
            result = um.authenticate_user('admin', pwd)
            print(f"Result: {result is not None}")
            if result:
                print(f"Authenticated user: {result.get('username')}")
                break

    except Exception as e:
        print(f"Error with UserManager: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_auth()
