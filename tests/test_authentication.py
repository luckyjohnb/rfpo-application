#!/usr/bin/env python3
"""
Quick test script to verify authentication is working
"""

import requests
import json


def test_login():
    """Test the login functionality"""
    login_url = "http://127.0.0.1:5000/api/auth/login"

    # Admin credentials
    credentials = {"username": "admin", "password": "admin"}

    print("Testing authentication...")
    print(f"URL: {login_url}")
    print(f"Credentials: {credentials}")

    try:
        response = requests.post(
            login_url, json=credentials, headers={"Content-Type": "application/json"}
        )

        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body: {response.text}")

        if response.status_code == 200:
            print("✅ Authentication successful!")
            return True
        else:
            print("❌ Authentication failed!")
            return False

    except Exception as e:
        print(f"❌ Error during request: {e}")
        return False


if __name__ == "__main__":
    test_login()
