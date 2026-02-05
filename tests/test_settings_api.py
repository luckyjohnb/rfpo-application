#!/usr/bin/env python3
"""
Test script for Application Settings API
"""
import requests
import json

# Configuration
BASE_URL = "http://127.0.0.1:5000"
USERNAME = "admin"
PASSWORD = "Administrator123!"

def get_auth_token():
    """Get authentication token"""
    login_data = {
        "username": USERNAME,
        "password": PASSWORD
    }

    response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
    if response.status_code == 200:
        return response.json().get('token')
    else:
        print(f"Login failed: {response.text}")
        return None

def test_settings_api():
    """Test the settings API endpoints"""
    # Get auth token
    token = get_auth_token()
    if not token:
        print("❌ Failed to get authentication token")
        return

    headers = {'Authorization': f'Bearer {token}'}

    print("🔑 Authentication successful!")
    print(f"📱 Token: {token[:20]}...")
    print()

    # Test 1: Get all settings
    print("📋 Test 1: Getting all settings...")
    response = requests.get(f"{BASE_URL}/api/settings", headers=headers)
    if response.status_code == 200:
        data = response.json()
        print("✅ Settings retrieved successfully!")
        print(f"📊 Found {len(data.get('settings', {}))} settings")
        print(f"📂 Categories: {len(data.get('categories', {}))}")
        print()
    else:
        print(f"❌ Failed to get settings: {response.text}")
        return

    # Test 2: Get a specific setting
    print("📋 Test 2: Getting specific setting...")
    response = requests.get(f"{BASE_URL}/api/settings/application_name", headers=headers)
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Setting retrieved: {data.get('key')} = {data.get('value')}")
        print()
    else:
        print(f"❌ Failed to get specific setting: {response.text}")

    # Test 3: Update a setting
    print("📋 Test 3: Updating a setting...")
    update_data = {"value": "Test App Updated"}
    response = requests.put(f"{BASE_URL}/api/settings/application_name",
                          json=update_data, headers=headers)
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Setting updated: {data.get('key')} = {data.get('value')}")
        print()
    else:
        print(f"❌ Failed to update setting: {response.text}")

    # Test 4: Update multiple settings
    print("📋 Test 4: Updating multiple settings...")
    settings_update = {
        "settings": {
            "application_name": "ACME App",
            "theme_color": "#ff0000",
            "items_per_page": "25"
        }
    }
    response = requests.post(f"{BASE_URL}/api/settings",
                           json=settings_update, headers=headers)
    if response.status_code == 200:
        print("✅ Multiple settings updated successfully!")
        print()
    else:
        print(f"❌ Failed to update multiple settings: {response.text}")

    print("🎉 Settings API test completed!")

if __name__ == "__main__":
    print("🧪 Testing Application Settings API")
    print("=" * 50)
    test_settings_api()
