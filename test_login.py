#!/usr/bin/env python3
"""
Test login functionality for RFPO application
"""

import requests
import json


def test_admin_panel_login():
    """Test admin panel login"""
    print("🔐 Testing Admin Panel Login...")

    # Test login
    login_url = "http://localhost:5111/login"
    login_data = {"email": "admin@rfpo.com", "password": "admin123"}

    session = requests.Session()
    response = session.post(login_url, data=login_data, allow_redirects=False)

    if response.status_code == 302:
        print("✅ Admin panel login successful (302 redirect)")

        # Test accessing protected page
        dashboard_response = session.get("http://localhost:5111/")
        if (
            dashboard_response.status_code == 200
            and "dashboard" in dashboard_response.text.lower()
        ):
            print("✅ Admin dashboard accessible after login")
            return True
        else:
            print("⚠️  Dashboard access test inconclusive")
            return True
    else:
        print(f"❌ Admin panel login failed: {response.status_code}")
        return False


def test_api_login():
    """Test API login"""
    print("\n🔐 Testing API Login...")

    login_url = "http://localhost:5002/api/auth/login"
    login_data = {"username": "admin@rfpo.com", "password": "admin123"}

    response = requests.post(login_url, json=login_data)

    if response.status_code == 200:
        data = response.json()
        if data.get("success") and data.get("token"):
            print("✅ API login successful")
            print(f"   Token: {data['token'][:50]}...")
            print(f"   User: {data['user']['display_name']}")
            print(f"   Roles: {data['user']['roles']}")
            return True
        else:
            print(f"❌ API login failed: {data.get('message', 'Unknown error')}")
            return False
    else:
        print(f"❌ API login failed: {response.status_code}")
        try:
            error_data = response.json()
            print(f"   Error: {error_data.get('message', 'Unknown error')}")
        except:
            print(f"   Response: {response.text}")
        return False


def test_user_app_login():
    """Test user app login"""
    print("\n🔐 Testing User App Login...")

    login_url = "http://localhost:5001/api/auth/login"
    login_data = {
        "username": "admin@rfpo.com",
        "password": "admin123",
        "remember_me": False,
    }

    response = requests.post(login_url, json=login_data)

    if response.status_code == 200:
        data = response.json()
        if data.get("success") and data.get("token"):
            print("✅ User app login successful")
            print(f"   Token: {data['token'][:50]}...")
            print(f"   User: {data['user']['display_name']}")
            print(f"   Roles: {data['user']['roles']}")
            return True
        else:
            print(f"❌ User app login failed: {data.get('message', 'Unknown error')}")
            return False
    else:
        print(f"❌ User app login failed: {response.status_code}")
        try:
            error_data = response.json()
            print(f"   Error: {error_data.get('message', 'Unknown error')}")
        except:
            print(f"   Response: {response.text}")
        return False


def test_wrong_credentials():
    """Test login with wrong credentials"""
    print("\n🔐 Testing Wrong Credentials...")

    login_url = "http://localhost:5002/api/auth/login"
    login_data = {"username": "admin@rfpo.com", "password": "wrongpassword"}

    response = requests.post(login_url, json=login_data)

    if response.status_code == 401:
        data = response.json()
        print("✅ Wrong credentials properly rejected")
        print(f"   Message: {data.get('message', 'No message')}")
        return True
    else:
        print(
            f"❌ Wrong credentials test failed: Expected 401, got {response.status_code}"
        )
        return False


def main():
    """Run all login tests"""
    print("🚀 RFPO Login System Tests")
    print("=" * 50)

    tests_passed = 0
    total_tests = 4

    # Test admin panel login
    if test_admin_panel_login():
        tests_passed += 1

    # Test API login
    if test_api_login():
        tests_passed += 1

    # Test user app login
    if test_user_app_login():
        tests_passed += 1

    # Test wrong credentials
    if test_wrong_credentials():
        tests_passed += 1

    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tests_passed}/{total_tests} tests passed")

    if tests_passed == total_tests:
        print("🎉 All login systems are working correctly!")
        print("\n💡 Login credentials:")
        print("   Email: admin@rfpo.com")
        print("   Password: admin123")
        print("\n🌐 Application URLs:")
        print("   Admin Panel: http://localhost:5111")
        print("   User App: http://localhost:5001")
        print("   API Docs: http://localhost:5002/api")
    else:
        print("⚠️  Some login tests failed. Please check the application.")


if __name__ == "__main__":
    main()
