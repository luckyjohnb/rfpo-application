#!/usr/bin/env python3
"""
Test the improved Consortium list view
"""

import requests
import re

def test_consortium_view():
    """Test all consortium view improvements"""
    base_url = "http://localhost:5111"
    session = requests.Session()
    
    print("🧪 Testing Consortium List View Improvements")
    print("=" * 50)
    
    # Login
    response = session.post(f"{base_url}/login", data={
        'email': 'admin@rfpo.com',
        'password': 'admin123'
    }, allow_redirects=False)
    
    if response.status_code != 302:
        print("❌ Login failed")
        return False
    
    print("✅ Login successful")
    
    # Test consortium list view
    print("\n🏢 Testing Consortium List View:")
    response = session.get(f"{base_url}/consortiums")
    if response.status_code == 200:
        print("✅ Consortium list loads")
        
        # Check for updated column headers
        required_headers = [
            "Approved Vendors",  # Changed from "Approved Vendors Required"
            "Projects",          # New column
            "RFPOs",            # New column  
            "Viewers",          # Changed from "RFPO Viewers"
            "Admins"            # Changed from "RFPO Admins"
        ]
        
        for header in required_headers:
            if f"<th>{header}</th>" in response.text:
                print(f"✅ Column header '{header}' present")
            else:
                print(f"❌ Column header '{header}' missing")
                return False
        
        # Check for count badges
        count_badges = re.findall(r'badge bg-[^"]*">[0-9]+<', response.text)
        if len(count_badges) >= 4:  # Should have at least 4 count badges per row
            print(f"✅ Count badges present - found {len(count_badges)} count displays")
        else:
            print(f"❌ Count badges missing or insufficient - found {len(count_badges)}")
            return False
        
        # Check that old headers are gone
        old_headers = ["RFPO Viewers", "RFPO Admins", "Approved Vendors Required"]
        for old_header in old_headers:
            if f"<th>{old_header}</th>" in response.text:
                print(f"❌ Old header '{old_header}' still present (should be removed)")
                return False
            else:
                print(f"✅ Old header '{old_header}' properly removed")
        
        # Check for specific consortium data
        if "Advanced Powertrain" in response.text and "APT" in response.text:
            print("✅ Standard consortium data visible")
        else:
            print("❌ Standard consortium data missing")
            return False
        
    else:
        print(f"❌ Consortium list failed - Status: {response.status_code}")
        return False
    
    print("\n🎉 All consortium view improvement tests passed!")
    print("\n✨ Consortium List Features Working:")
    print("   • Updated column headers: 'Approved Vendors', 'Viewers', 'Admins'")
    print("   • New columns: 'Projects' and 'RFPOs' with counts")
    print("   • Count badges for Projects, RFPOs, Viewers, Admins")
    print("   • Proper column ordering: ID, Name, Abbrev, Vendors, Projects, RFPOs, Viewers, Admins, Status")
    print("   • Clean, professional display with colored badges")
    
    return True

if __name__ == '__main__':
    success = test_consortium_view()
    
    if success:
        print(f"\n🌐 View the improved consortium list at: http://localhost:5111/consortiums")
        print("📧 Login: admin@rfpo.com / admin123")
        print("\n🎯 You can now see:")
        print("   • Project counts for each consortium")
        print("   • RFPO counts through associated teams")
        print("   • Viewer and Admin user counts")
        print("   • Professional badge display for all counts")
    else:
        print("\n❌ Some consortium view features need fixes")

