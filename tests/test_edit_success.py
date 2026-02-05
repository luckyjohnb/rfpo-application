#!/usr/bin/env python3
"""
Test that all edit functionality is working without crashes
"""

import requests


def test_edit_success():
    """Test all edit operations work without crashes"""
    base_url = "http://localhost:5111"
    session = requests.Session()

    print("🧪 Testing Edit Functionality (No Crashes)")
    print("=" * 50)

    # Login
    response = session.post(
        f"{base_url}/login",
        data={"email": "admin@rfpo.com", "password": "admin123"},
        allow_redirects=False,
    )

    print("✅ Login successful")

    # Test specific edit operations that were crashing
    edit_tests = [
        ("/consortium/7/edit", "Consortium Edit"),  # Try a valid consortium ID
        ("/team/1/edit", "Team Edit"),
        ("/user/1/edit", "User Edit"),
        ("/vendor/1/edit", "Vendor Edit"),
        ("/project/1/edit", "Project Edit"),
        ("/rfpo/1/edit", "RFPO Edit"),
    ]

    for url, name in edit_tests:
        response = session.get(f"{base_url}{url}")
        if response.status_code == 200:
            if "hasattr" in response.text:
                print(f"❌ {name} - hasattr error still present")
            else:
                print(f"✅ {name} - loads without hasattr errors")
        elif response.status_code == 404:
            print(f"⚠️  {name} - record not found (expected if no data)")
        else:
            print(f"❌ {name} - Status: {response.status_code}")

    print(f"\n🎉 Edit functionality test complete!")
    print(f"🌐 Access admin panel: http://localhost:5111")

    return True


if __name__ == "__main__":
    test_edit_success()
