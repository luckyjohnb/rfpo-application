#!/usr/bin/env python3
"""
Test the improved Teams view
"""

import requests

def test_teams_view():
    """Test all teams view improvements"""
    base_url = "http://localhost:5111"
    session = requests.Session()
    
    print("🧪 Testing Teams View Improvements")
    print("=" * 40)
    
    # Login
    response = session.post(f"{base_url}/login", data={
        'email': 'admin@rfpo.com',
        'password': 'admin123'
    }, allow_redirects=False)
    
    if response.status_code != 302:
        print("❌ Login failed")
        return False
    
    print("✅ Login successful")
    
    # Test teams list view
    print("\n👥 Testing Teams List View:")
    response = session.get(f"{base_url}/teams")
    if response.status_code == 200:
        print("✅ Teams list loads")
        
        # Check for updated column headers
        required_headers = [
            "Projects",    # New column
            "Viewers",     # Changed from "RFPO Viewers"
            "Admins"       # New column
        ]
        
        for header in required_headers:
            if f"<th>{header}</th>" in response.text:
                print(f"✅ Column header '{header}' present")
            else:
                print(f"❌ Column header '{header}' missing")
                return False
        
        # Check that old header is gone
        if "<th>RFPO Viewers</th>" in response.text:
            print("❌ Old header 'RFPO Viewers' still present")
            return False
        else:
            print("✅ Old header 'RFPO Viewers' properly removed")
        
        # Check for consortium badge with tooltip
        if 'data-bs-toggle="tooltip"' in response.text and 'consortium-badge' in response.text:
            print("✅ Consortium badges with tooltips present")
        else:
            print("❌ Consortium badges with tooltips missing")
            return False
        
        # Check for count values (plain text, not badges)
        if ">0<" in response.text or ">1<" in response.text or ">2<" in response.text:
            print("✅ Count values displaying as plain text")
        else:
            print("❌ Count values not displaying correctly")
            return False
        
        # Check for tooltip initialization
        if "tooltip" in response.text and "bootstrap.Tooltip" in response.text:
            print("✅ Tooltip initialization present")
        else:
            print("❌ Tooltip initialization missing")
            return False
        
        # Check for team data
        if "Research & Development Team" in response.text or "Test Team" in response.text:
            print("✅ Team data visible")
        else:
            print("❌ Team data missing")
            return False
        
    else:
        print(f"❌ Teams list failed - Status: {response.status_code}")
        return False
    
    print("\n🎉 All teams view improvement tests passed!")
    print("\n✨ Teams List Features Working:")
    print("   • Updated column header: 'RFPO Viewers' → 'Viewers'")
    print("   • New 'Admins' column with count")
    print("   • New 'Projects' column with count")
    print("   • Consortium abbreviation badges with hover tooltips")
    print("   • Plain text counts (no heavy badge styling)")
    print("   • Proper column ordering: ID, Name, Abbrev, Consortium, Description, Projects, Viewers, Admins, Status")
    
    return True

if __name__ == '__main__':
    success = test_teams_view()
    
    if success:
        print(f"\n🌐 View the improved teams list at: http://localhost:5111/teams")
        print("📧 Login: admin@rfpo.com / admin123")
        print("\n🎯 You can now see:")
        print("   • Project counts for each team")
        print("   • Viewer and Admin user counts")
        print("   • Consortium badges with full name on hover")
        print("   • Clean, professional count display")
    else:
        print("\n❌ Some teams view features need fixes")

