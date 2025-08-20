#!/usr/bin/env python3
"""
Test Flask login endpoint directly
"""

import requests
import json

def test_flask_login():
    """Test the Flask login endpoint"""
    print("=== FLASK LOGIN ENDPOINT TEST ===")

    login_url = "http://127.0.0.1:5000/api/auth/login"
    credentials = {
        "username": "admin",
        "password": "admin"
    }

    print(f"🌐 URL: {login_url}")
    print(f"🔑 Credentials: {credentials}")

    try:
        response = requests.post(
            login_url,
            json=credentials,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )

        print(f"📊 Status Code: {response.status_code}")
        print(f"📋 Headers: {dict(response.headers)}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ LOGIN SUCCESSFUL!")
            print(f"🎫 Token: {data.get('token', 'N/A')[:50]}...")
            print(f"👤 User: {data.get('user', {})}")
            return True
        else:
            print(f"❌ LOGIN FAILED!")
            print(f"📄 Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ Connection failed - Flask server not running or not accessible")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_flask_login()
    print(f"\n{'='*60}")
    if success:
        print("🎉 FLASK LOGIN TEST PASSED")
        print("✅ Authentication is working correctly!")
    else:
        print("💔 FLASK LOGIN TEST FAILED")
    print("="*60)
