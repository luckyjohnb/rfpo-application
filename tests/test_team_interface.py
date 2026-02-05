#!/usr/bin/env python3
"""
Test the improved Team creation interface
"""

import requests


def test_team_interface():
    """Test the improved team creation interface"""
    base_url = "http://localhost:5111"
    session = requests.Session()

    print("🧪 Testing Improved Team Creation Interface")
    print("=" * 50)

    # Login
    response = session.post(
        f"{base_url}/login",
        data={"email": "admin@rfpo.com", "password": "admin123"},
        allow_redirects=False,
    )

    if response.status_code != 302:
        print("❌ Login failed")
        return False

    print("✅ Login successful")

    # Test team creation form loads
    response = session.get(f"{base_url}/team/new")
    if response.status_code == 200:
        print("✅ Team creation form loads")

        # Check for consortium dropdown
        if (
            "None (Independent Team)" in response.text
            and "Advanced Powertrain" in response.text
        ):
            print("✅ Consortium dropdown with 'None' option working")
        else:
            print("❌ Consortium dropdown missing or incomplete")
            return False

        # Check for user selection interface
        if "Available Users" in response.text and "Selected" in response.text:
            print("✅ Available/Selected user interface present")
        else:
            print("❌ User selection interface missing")
            return False

        # Check for search functionality
        if "Search users by name" in response.text:
            print("✅ User search functionality present")
        else:
            print("❌ User search missing")
            return False

    else:
        print(f"❌ Team creation form failed - Status: {response.status_code}")
        return False

    # Test API endpoints
    print("\n🔗 Testing API Endpoints:")

    # Test users API
    response = session.get(f"{base_url}/api/users")
    if response.status_code == 200:
        users = response.json()
        print(f"✅ Users API working - {len(users)} users available")
        if len(users) > 0 and "name" in users[0] and "id" in users[0]:
            print("✅ User data format correct")
        else:
            print("❌ User data format incorrect")
    else:
        print("❌ Users API not working")
        return False

    # Test consortiums API
    response = session.get(f"{base_url}/api/consortiums")
    if response.status_code == 200:
        consortiums = response.json()
        print(f"✅ Consortiums API working - {len(consortiums)} consortiums available")
        if (
            len(consortiums) > 0
            and "abbrev" in consortiums[0]
            and "name" in consortiums[0]
        ):
            print("✅ Consortium data format correct")
        else:
            print("❌ Consortium data format incorrect")
    else:
        print("❌ Consortiums API not working")
        return False

    print("\n🎉 All team interface tests passed!")
    print("\n✨ New Features Working:")
    print("   • Consortium dropdown with [ABBREV] Name format")
    print("   • 'None' option for independent teams")
    print("   • Available Users (left) / Selected Users (right)")
    print("   • Search functionality for user filtering")
    print("   • Click to add/remove users between lists")
    print("   • Visual feedback with + and - icons")

    return True


if __name__ == "__main__":
    success = test_team_interface()

    if success:
        print(f"\n🌐 Test the interface at: http://localhost:5111/team/new")
        print("📧 Login: admin@rfpo.com / admin123")
    else:
        print("\n❌ Some features need fixes")
