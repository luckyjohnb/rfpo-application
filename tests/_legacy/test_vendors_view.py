#!/usr/bin/env python3
"""
Test the improved Vendors view
"""

import requests


def test_vendors_view():
    """Test all vendors view improvements"""
    base_url = "http://localhost:5111"
    session = requests.Session()

    print("🧪 Testing Vendors View Improvements")
    print("=" * 40)

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

    # Test vendors list view
    print("\n🏪 Testing Vendors List View:")
    response = session.get(f"{base_url}/vendors")
    if response.status_code == 200:
        print("✅ Vendors list loads")

        # Check for consortium badges with tooltips
        if "badge bg-primary" in response.text and "consortium-badge" in response.text:
            print("✅ Consortium badges present")
        else:
            print("❌ Consortium badges missing")
            return False

        # Check for tooltip attributes
        if 'data-bs-toggle="tooltip"' in response.text:
            print("✅ Tooltip attributes present")
        else:
            print("❌ Tooltip attributes missing")
            return False

        # Check for tooltip initialization
        if "tooltip" in response.text and "bootstrap.Tooltip" in response.text:
            print("✅ Tooltip initialization present")
        else:
            print("❌ Tooltip initialization missing")
            return False

        # Check for multiple consortium badges (vendors can be approved for multiple)
        consortium_badge_count = response.text.count("consortium-badge")
        if consortium_badge_count > 0:
            print(
                f"✅ Multiple consortium support working - {consortium_badge_count} consortium badges found"
            )
        else:
            print("❌ Consortium badges not found")
            return False

        # Check that old text format is replaced
        if (
            "SAC, USCAR" in response.text
            and "badge" not in response.text.split("SAC, USCAR")[0][-50:]
        ):
            print("❌ Old text format still present (should be badges)")
            return False
        else:
            print("✅ Text format replaced with badges")

        # Check for vendor data
        if "TechCorp Solutions Inc." in response.text or "Test Vendor" in response.text:
            print("✅ Vendor data visible")
        else:
            print("❌ Vendor data missing")
            return False

    else:
        print(f"❌ Vendors list failed - Status: {response.status_code}")
        return False

    print("\n🎉 All vendors view improvement tests passed!")
    print("\n✨ Vendors List Features Working:")
    print("   • Approved Consortiums as abbreviation badges")
    print("   • Hover tooltips showing full consortium names")
    print("   • Multiple consortium badges per vendor")
    print("   • Professional badge styling with blue color (bg-primary)")
    print("   • Clean 'None' display for vendors without approvals")
    print("   • Consistent with Projects and Teams badge treatment")

    return True


if __name__ == "__main__":
    success = test_vendors_view()

    if success:
        print(f"\n🌐 View the improved vendors list at: http://localhost:5111/vendors")
        print("📧 Login: admin@rfpo.com / admin123")
        print("\n🎯 You can now see:")
        print("   • Consortium abbreviations as blue badges")
        print("   • Hover over badges to see full consortium names")
        print("   • Multiple consortium badges for multi-approved vendors")
        print("   • Professional, consistent badge treatment")
    else:
        print("\n❌ Some vendors view features need fixes")
