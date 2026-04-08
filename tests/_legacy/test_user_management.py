#!/usr/bin/env python3
"""
Test script to verify user management functionality
"""
import requests
import json

# Base URL for the Flask app
BASE_URL = "http://127.0.0.1:5000"


def test_login():
    """Test login functionality"""
    print("Testing login...")
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "Administrator123!"},
    )

    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            print("✅ Login successful!")
            return data.get("token")
        else:
            print("❌ Login failed:", data.get("message"))
            return None
    else:
        print("❌ Login request failed:", response.status_code)
        return None


def test_get_users(token):
    """Test getting users list"""
    print("\nTesting get users...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/users", headers=headers)

    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            print("✅ Get users successful!")
            print(f"Found {len(data.get('users', []))} users:")
            for user in data.get("users", []):
                print(
                    f"  - {user.get('username')} ({user.get('display_name', 'No display name')})"
                )
        else:
            print("❌ Get users failed:", data.get("message"))
    else:
        print("❌ Get users request failed:", response.status_code)


def test_create_user(token):
    """Test creating a new user"""
    print("\nTesting create user...")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    user_data = {
        "username": "testuser",
        "password": "TestPassword123!",
        "display_name": "Test User",
        "email": "test@example.com",
        "roles": ["user"],
    }

    response = requests.post(f"{BASE_URL}/api/users", headers=headers, json=user_data)

    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            print("✅ Create user successful!")
        else:
            print("❌ Create user failed:", data.get("message"))
    else:
        print("❌ Create user request failed:", response.status_code)


def main():
    print("=" * 50)
    print("User Management Test")
    print("=" * 50)
    print("Make sure the Flask app is running first!")
    print("Run: python app_working.py")
    print("=" * 50)

    # Test login
    token = test_login()
    if not token:
        print("Cannot proceed without login token")
        return

    # Test getting users
    test_get_users(token)

    # Test creating user
    test_create_user(token)

    # Test getting users again to see the new user
    test_get_users(token)

    print("\n" + "=" * 50)
    print("Test completed!")
    print("You can now test the web interface at:")
    print("http://127.0.0.1:5000/app")
    print("=" * 50)


if __name__ == "__main__":
    main()
