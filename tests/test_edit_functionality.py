#!/usr/bin/env python3
"""
Test all edit functionality in the admin panel
"""

import requests
import re

def test_edit_functionality():
    """Test all edit operations"""
    base_url = "http://localhost:5111"
    session = requests.Session()
    
    print("🧪 Testing Edit Functionality")
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
    
    # Test each model's edit functionality
    models_to_test = [
        ('consortiums', 'Consortium'),
        ('teams', 'Team'),
        ('users', 'User'),
        ('vendors', 'Vendor'),
        ('projects', 'Project'),
        ('rfpos', 'RFPO'),
    ]
    
    for model_url, model_name in models_to_test:
        print(f"\n🔍 Testing {model_name} Edit:")
        
        # Get the list page
        response = session.get(f"{base_url}/{model_url}")
        if response.status_code != 200:
            print(f"❌ {model_name} list page failed")
            continue
        
        # Look for edit links in the HTML
        edit_links = re.findall(r'href="[^"]*edit[^"]*"', response.text)
        if edit_links:
            print(f"✅ {model_name} edit links found: {len(edit_links)}")
            
            # Extract the first edit URL
            first_edit_url = edit_links[0].replace('href="', '').replace('"', '')
            
            # Test the edit form loads
            edit_response = session.get(f"{base_url}{first_edit_url}")
            if edit_response.status_code == 200:
                if "hasattr" in edit_response.text:
                    print(f"❌ {model_name} edit form has hasattr error")
                else:
                    print(f"✅ {model_name} edit form loads without errors")
            elif edit_response.status_code == 404:
                print(f"⚠️  {model_name} edit form - record not found")
            else:
                print(f"❌ {model_name} edit form failed - Status: {edit_response.status_code}")
        else:
            print(f"❌ {model_name} edit links not found")
    
    return True

if __name__ == '__main__':
    test_edit_functionality()

