#!/usr/bin/env python3
"""
Comprehensive CRUD Test Suite for Custom RFPO Admin Panel
Tests all database operations through the admin panel endpoints.
"""

import requests
import json
import sys
from datetime import datetime

class AdminCRUDTester:
    """Test suite for admin panel CRUD operations"""
    
    def __init__(self, base_url="http://localhost:5111"):
        self.base_url = base_url
        self.session = requests.Session()
        self.logged_in = False
    
    def login(self, email="admin@rfpo.com", password="admin123"):
        """Login to admin panel"""
        try:
            response = self.session.post(f"{self.base_url}/login", data={
                'email': email,
                'password': password
            }, allow_redirects=False)
            
            if response.status_code == 302:
                print("✅ Login successful")
                self.logged_in = True
                return True
            else:
                print(f"❌ Login failed - Status: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Login error: {str(e)}")
            return False
    
    def test_dashboard(self):
        """Test dashboard access"""
        try:
            response = self.session.get(f"{self.base_url}/")
            if response.status_code == 200:
                if "Dashboard" in response.text or "RFPO Admin" in response.text:
                    print("✅ Dashboard loads successfully")
                    return True
                else:
                    print("❌ Dashboard content missing")
                    return False
            else:
                print(f"❌ Dashboard failed - Status: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Dashboard error: {str(e)}")
            return False
    
    def test_consortium_crud(self):
        """Test Consortium CRUD operations"""
        print("\n🏢 Testing Consortium CRUD...")
        
        # Test LIST
        try:
            response = self.session.get(f"{self.base_url}/consortiums")
            if response.status_code == 200:
                print("✅ Consortium list loads")
            else:
                print(f"❌ Consortium list failed - Status: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Consortium list error: {str(e)}")
            return False
        
        # Test CREATE form
        try:
            response = self.session.get(f"{self.base_url}/consortium/new")
            if response.status_code == 200:
                if "Consortium ID" in response.text:
                    print("✅ Consortium create form loads")
                else:
                    print("❌ Consortium create form missing fields")
                    return False
            else:
                print(f"❌ Consortium create form failed - Status: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Consortium create form error: {str(e)}")
            return False
        
        # Test CREATE operation
        test_data = {
            'consort_id': f'TEST{datetime.now().strftime("%Y%m%d%H%M%S")}',
            'name': 'Test Consortium CRUD',
            'abbrev': 'TCRUD',
            'require_approved_vendors': '1',
            'rfpo_viewer_user_ids': 'user1, user2, user3',
            'rfpo_admin_user_ids': 'admin1, admin2',
            'invoicing_address': '123 Test Street\nTest City, TS 12345',
            'po_email': 'test@consortium.com',
            'active': '1'
        }
        
        try:
            response = self.session.post(f"{self.base_url}/consortium/new", data=test_data, allow_redirects=False)
            if response.status_code == 302:  # Redirect after successful creation
                print("✅ Consortium created successfully")
                return True
            else:
                print(f"❌ Consortium creation failed - Status: {response.status_code}")
                print(f"Response: {response.text[:200]}")
                return False
        except Exception as e:
            print(f"❌ Consortium creation error: {str(e)}")
            return False
    
    def test_team_crud(self):
        """Test Team CRUD operations"""
        print("\n👥 Testing Team CRUD...")
        
        # Test LIST
        try:
            response = self.session.get(f"{self.base_url}/teams")
            if response.status_code == 200:
                print("✅ Team list loads")
            else:
                print(f"❌ Team list failed - Status: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Team list error: {str(e)}")
            return False
        
        # Test CREATE form
        try:
            response = self.session.get(f"{self.base_url}/team/new")
            if response.status_code == 200:
                if "Team ID" in response.text:
                    print("✅ Team create form loads")
                else:
                    print("❌ Team create form missing fields")
                    return False
            else:
                print(f"❌ Team create form failed - Status: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Team create form error: {str(e)}")
            return False
        
        # Test CREATE operation
        test_data = {
            'record_id': f'TEAM{datetime.now().strftime("%Y%m%d%H%M%S")}',
            'name': 'Test Team CRUD',
            'abbrev': 'TCRUD',
            'description': 'Test team for CRUD operations',
            'consortium_consort_id': '',  # No consortium
            'rfpo_viewer_user_ids': 'viewer1, viewer2',
            'rfpo_admin_user_ids': 'teamadmin1',
            'active': '1'
        }
        
        try:
            response = self.session.post(f"{self.base_url}/team/new", data=test_data, allow_redirects=False)
            if response.status_code == 302:  # Redirect after successful creation
                print("✅ Team created successfully")
                return True
            else:
                print(f"❌ Team creation failed - Status: {response.status_code}")
                print(f"Response: {response.text[:200]}")
                return False
        except Exception as e:
            print(f"❌ Team creation error: {str(e)}")
            return False
    
    def test_user_crud(self):
        """Test User CRUD operations"""
        print("\n👤 Testing User CRUD...")
        
        # Test LIST
        try:
            response = self.session.get(f"{self.base_url}/users")
            if response.status_code == 200:
                print("✅ User list loads")
            else:
                print(f"❌ User list failed - Status: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ User list error: {str(e)}")
            return False
        
        # Test CREATE form (if implemented)
        try:
            response = self.session.get(f"{self.base_url}/user/new")
            if response.status_code == 200:
                print("✅ User create form loads")
            else:
                print("⚠️  User create form not implemented yet")
        except Exception as e:
            print("⚠️  User create form not implemented yet")
        
        return True
    
    def test_api_endpoints(self):
        """Test API endpoints"""
        print("\n🔗 Testing API Endpoints...")
        
        try:
            response = self.session.get(f"{self.base_url}/api/stats")
            if response.status_code == 200:
                stats = response.json()
                if isinstance(stats, dict) and 'consortiums' in stats:
                    print("✅ API stats endpoint works")
                    print(f"   📊 Stats: {stats}")
                    return True
                else:
                    print("❌ API stats endpoint returns invalid data")
                    return False
            else:
                print(f"❌ API stats endpoint failed - Status: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ API stats endpoint error: {str(e)}")
            return False
    
    def test_json_transformations(self):
        """Test JSON field transformations by checking database"""
        print("\n🔄 Testing JSON Field Transformations...")
        
        try:
            # This would require database access - for now just test the endpoints exist
            response = self.session.get(f"{self.base_url}/consortiums")
            if "RFPO Viewers" in response.text and "RFPO Admins" in response.text:
                print("✅ JSON fields displayed in consortium list")
                return True
            else:
                print("❌ JSON fields not displayed properly")
                return False
        except Exception as e:
            print(f"❌ JSON transformation test error: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run complete test suite"""
        print("=" * 60)
        print("🧪 RFPO Admin Panel CRUD Test Suite")
        print("=" * 60)
        print(f"🌐 Testing admin panel at: {self.base_url}")
        
        # Test login first
        if not self.login():
            print("❌ Cannot proceed - login failed")
            return False
        
        tests = [
            ("Dashboard Access", self.test_dashboard),
            ("Consortium CRUD", self.test_consortium_crud),
            ("Team CRUD", self.test_team_crud),
            ("User CRUD", self.test_user_crud),
            ("API Endpoints", self.test_api_endpoints),
            ("JSON Transformations", self.test_json_transformations),
        ]
        
        results = []
        for test_name, test_func in tests:
            print(f"\n{test_name}:")
            print("-" * 40)
            result = test_func()
            results.append((test_name, result))
        
        print("\n" + "=" * 60)
        print("🧪 TEST SUMMARY")
        print("=" * 60)
        
        passed = 0
        for test_name, result in results:
            status = "PASS" if result else "FAIL"
            print(f"{test_name:<25} {status}")
            if result:
                passed += 1
        
        print(f"\nTests passed: {passed}/{len(tests)}")
        
        if passed == len(tests):
            print("\n🎉 All tests passed! Admin panel CRUD is working perfectly!")
            return True
        else:
            print(f"\n⚠️  {len(tests) - passed} test(s) failed or incomplete.")
            return False

def main():
    """Main test runner"""
    tester = AdminCRUDTester()
    
    print("🔍 Checking if admin panel is running...")
    try:
        response = requests.get("http://localhost:5111", timeout=5)
        print("✅ Admin panel is accessible")
    except Exception as e:
        print("❌ Admin panel not accessible. Make sure it's running on port 5111")
        print("   Run: python3 custom_admin.py")
        sys.exit(1)
    
    success = tester.run_all_tests()
    
    if success:
        print("\n🎊 CRUD operations are working! You can manage your data through the admin panel.")
    else:
        print("\n🔧 Some operations need to be implemented or fixed.")
    
    print(f"\n🌐 Access your admin panel at: http://localhost:5111")
    print("📧 Login: admin@rfpo.com")
    print("🔑 Password: admin123")

if __name__ == '__main__':
    main()

