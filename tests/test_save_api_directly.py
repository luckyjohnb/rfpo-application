#!/usr/bin/env python3
"""
Test the save API directly to see if it's working
"""
import requests
import json


def test_save_api_directly():
    """Test saving positioning data directly via API"""
    print("🔍 TESTING SAVE API DIRECTLY")
    print("=" * 50)

    # Login first to get session
    session = requests.Session()

    print("📋 Step 1: Login...")
    login_data = {"email": "admin@rfpo.com", "password": "admin123"}

    login_response = session.post("http://localhost:5111/login", data=login_data)
    if login_response.status_code == 200:
        print("   ✅ Login successful")
    else:
        print(f"   ❌ Login failed: {login_response.status_code}")
        return False

    print("\n📋 Step 2: Test save API...")

    # Prepare test positioning data
    test_data = {
        "positioning_data": {
            "test_field": {
                "x": 450,
                "y": 100,
                "font_size": 16,
                "font_weight": "bold",
                "visible": True,
            }
        }
    }

    # Save to config ID 1 (USCAR)
    save_url = "http://localhost:5111/api/pdf-positioning/1"
    headers = {"Content-Type": "application/json"}

    print(f"   Sending data to: {save_url}")
    print(f"   Data: {json.dumps(test_data, indent=2)}")

    save_response = session.post(save_url, json=test_data, headers=headers)

    print(f"   Response status: {save_response.status_code}")
    print(f"   Response body: {save_response.text}")

    if save_response.status_code == 200:
        response_data = save_response.json()
        if response_data.get("success"):
            print("   ✅ Save API successful")
        else:
            print(f"   ❌ Save API returned error: {response_data.get('error')}")
            return False
    else:
        print(f"   ❌ Save API failed with status {save_response.status_code}")
        return False

    print("\n📋 Step 3: Verify data was saved...")

    # Get the data back
    get_response = session.get(save_url)
    if get_response.status_code == 200:
        config_data = get_response.json()
        positioning_data = config_data.get("positioning_data", {})

        if "test_field" in positioning_data:
            saved_field = positioning_data["test_field"]
            print(f"   ✅ Test field saved successfully:")
            print(
                f"      x={saved_field.get('x')}, y={saved_field.get('y')}, visible={saved_field.get('visible')}"
            )
            return True
        else:
            print(f"   ❌ Test field NOT found in saved data")
            print(f"   Available fields: {list(positioning_data.keys())}")
            return False
    else:
        print(f"   ❌ Failed to retrieve saved data: {get_response.status_code}")
        return False


if __name__ == "__main__":
    success = test_save_api_directly()
    if success:
        print(f"\n✅ SAVE API: WORKING")
    else:
        print(f"\n❌ SAVE API: BROKEN")
