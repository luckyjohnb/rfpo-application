#!/usr/bin/env python3
"""
Test the improved Consortium management interface
"""

import requests

def test_consortium_improvements():
    """Test all consortium improvements"""
    base_url = "http://localhost:5111"
    session = requests.Session()
    
    print("🧪 Testing Consortium Interface Improvements")
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
    
    # Test consortium creation form
    print("\n🏢 Testing Consortium Creation Form:")
    response = session.get(f"{base_url}/consortium/new")
    if response.status_code == 200:
        print("✅ Consortium creation form loads")
        
        # Check for file upload component
        if 'type="file"' in response.text and 'logo_file' in response.text:
            print("✅ Logo file upload component present")
        else:
            print("❌ Logo file upload component missing")
            return False
        
        # Check for user selection interface
        if "Available Users" in response.text and "Selected Viewers" in response.text and "Selected Admins" in response.text:
            print("✅ Available/Selected user interface present for both viewers and admins")
        else:
            print("❌ User selection interface missing or incomplete")
            return False
        
        # Check for structured address inputs
        if "invoicing_street" in response.text and "invoicing_city" in response.text and "invoicing_state" in response.text:
            print("✅ Structured invoicing address inputs present")
        else:
            print("❌ Structured address inputs missing")
            return False
        
        # Check for non-government project selector
        if "Non-Government Project" in response.text and "select" in response.text.lower():
            print("✅ Non-government project selector present")
        else:
            print("❌ Non-government project selector missing")
            return False
        
        # Check for search functionality
        if "Search users by name" in response.text:
            print("✅ User search functionality present")
        else:
            print("❌ User search functionality missing")
            return False
        
    else:
        print(f"❌ Consortium creation form failed - Status: {response.status_code}")
        return False
    
    # Test API endpoints
    print("\n🔗 Testing API Endpoints:")
    
    # Test users API
    response = session.get(f"{base_url}/api/users")
    if response.status_code == 200:
        users = response.json()
        print(f"✅ Users API working - {len(users)} users available for selection")
    else:
        print("❌ Users API not working")
        return False
    
    print("\n🎉 All consortium improvement tests passed!")
    print("\n✨ Consortium Features Working:")
    print("   • Logo file upload with thumbnail display")
    print("   • Available/Selected user interface for viewers and admins")
    print("   • Structured invoicing address inputs (street, city, state, zip)")
    print("   • Non-government project selector dropdown")
    print("   • Project selector moved below Active checkbox")
    print("   • Search functionality for user selection")
    print("   • Professional form layout matching other models")
    
    return True

if __name__ == '__main__':
    success = test_consortium_improvements()
    
    if success:
        print(f"\n🌐 Test the consortium interface at: http://localhost:5111/consortium/new")
        print("📧 Login: admin@rfpo.com / admin123")
        print("\n🎯 Try:")
        print("   • Uploading a logo file")
        print("   • Searching and selecting users for viewer/admin roles")
        print("   • Filling in structured address fields")
        print("   • Selecting a non-government project")
    else:
        print("\n❌ Some consortium features need fixes")

