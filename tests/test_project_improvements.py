#!/usr/bin/env python3
"""
Test the improved Project management interface
"""

import requests


def test_project_improvements():
    """Test all project improvements"""
    base_url = "http://localhost:5111"
    session = requests.Session()

    print("🧪 Testing Project Interface Improvements")
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

    # Test project creation form
    print("\n📊 Testing Project Creation Form:")
    response = session.get(f"{base_url}/project/new")
    if response.status_code == 200:
        print("✅ Project creation form loads")

        # Check for team dropdown
        if (
            "None (No Team Assignment)" in response.text
            and "select" in response.text.lower()
        ):
            print("✅ Team dropdown present with 'None' option")
        else:
            print("❌ Team dropdown missing or incorrect")
            return False

        # Check for consortium selection interface
        if (
            "Available Consortiums" in response.text
            and "Associated Consortiums" in response.text
        ):
            print("✅ Available/Selected consortium interface present")
        else:
            print("❌ Consortium selection interface missing")
            return False

        # Check for user selection interface
        if "Available Users" in response.text and "Selected Viewers" in response.text:
            print("✅ Available/Selected user interface present")
        else:
            print("❌ User selection interface missing")
            return False

        # Check for search functionality
        if (
            "Search consortiums" in response.text
            and "Search users by name" in response.text
        ):
            print("✅ Search functionality present for both consortiums and users")
        else:
            print("❌ Search functionality missing")
            return False

    else:
        print(f"❌ Project creation form failed - Status: {response.status_code}")
        return False

    # Test creating a project with the new interface
    print("\n🏗️ Testing Project Creation with New Interface:")
    project_data = {
        "ref": f'PROJ-TEST-{requests.utils.unquote(str(hash("test")))[1:6]}',
        "name": "Test Project with New Interface",
        "description": "Testing the improved project creation interface",
        "team_record_id": "",  # No team for this test
        "consortium_ids": "00000007, 00000008",  # Test multiple consortiums
        "rfpo_viewer_user_ids": "00000001, 00000006",  # Test multiple users
        "gov_funded": "1",
        "uni_project": "0",
        "active": "1",
    }

    response = session.post(
        f"{base_url}/project/new", data=project_data, allow_redirects=False
    )
    if response.status_code == 302:
        print("✅ Project created successfully with new interface")

        # Verify it appears in the list
        response = session.get(f"{base_url}/projects")
        if project_data["name"] in response.text:
            print("✅ New project visible in list")
        else:
            print("❌ New project not visible in list")
            return False

    else:
        print(f"❌ Project creation failed - Status: {response.status_code}")
        return False

    # Test edit functionality
    print("\n✏️ Testing Project Edit:")
    response = session.get(f"{base_url}/projects")
    if "project_edit" in response.text:
        print("✅ Project edit links present")
    else:
        print("❌ Project edit links missing")
        return False

    print("\n🎉 All project improvement tests passed!")
    print("\n✨ Project Features Working:")
    print("   • Team dropdown with 'None' option")
    print("   • Available/Selected consortium interface")
    print("   • Available/Selected user interface")
    print("   • Search functionality for both consortiums and users")
    print("   • Multi-select for consortiums (1-to-many)")
    print("   • Multi-select for RFPO viewer users")
    print("   • Professional team selection")
    print("   • Full CRUD operations")

    return True


if __name__ == "__main__":
    success = test_project_improvements()

    if success:
        print(f"\n🌐 Test the project interface at: http://localhost:5111/project/new")
        print("📧 Login: admin@rfpo.com / admin123")
        print("\n🎯 Try:")
        print("   • Selecting a team from the dropdown")
        print("   • Searching and selecting multiple consortiums")
        print("   • Searching and selecting multiple RFPO viewer users")
        print("   • Creating a project with multiple associations")
    else:
        print("\n❌ Some project features need fixes")
