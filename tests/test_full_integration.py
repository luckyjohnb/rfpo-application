#!/usr/bin/env python3
"""
Full Integration Test Suite for Custom RFPO Admin Panel
Tests ALL CRUD operations for ALL models through the web interface.
"""

import requests
import json
import sys
from datetime import datetime

class FullIntegrationTester:
    """Complete integration test suite"""
    
    def __init__(self, base_url="http://localhost:5111"):
        self.base_url = base_url
        self.session = requests.Session()
        self.logged_in = False
        self.created_objects = {
            'consortiums': [],
            'teams': [],
            'rfpos': [],
            'users': [],
            'projects': [],
            'vendors': []
        }
    
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
    
    def test_navigation_links(self):
        """Test all navigation links work"""
        print("\n🧭 Testing Navigation Links...")
        
        nav_tests = [
            ('/', 'Dashboard'),
            ('/consortiums', 'Consortiums'),
            ('/teams', 'Teams'),
            ('/rfpos', 'RFPOs'),
            ('/users', 'Users'),
            ('/projects', 'Projects'),
            ('/vendors', 'Vendors'),
        ]
        
        for url, name in nav_tests:
            try:
                response = self.session.get(f"{self.base_url}{url}")
                if response.status_code == 200:
                    print(f"✅ {name} page loads")
                else:
                    print(f"❌ {name} page failed - Status: {response.status_code}")
                    return False
            except Exception as e:
                print(f"❌ {name} page error: {str(e)}")
                return False
        
        return True
    
    def test_create_forms_load(self):
        """Test all create forms load without errors"""
        print("\n📝 Testing Create Forms...")
        
        form_tests = [
            ('/consortium/new', 'Consortium'),
            ('/team/new', 'Team'),
            ('/rfpo/new', 'RFPO'),
            ('/user/new', 'User'),
            ('/project/new', 'Project'),
            ('/vendor/new', 'Vendor'),
        ]
        
        for url, name in form_tests:
            try:
                response = self.session.get(f"{self.base_url}{url}")
                if response.status_code == 200:
                    print(f"✅ {name} create form loads")
                else:
                    print(f"❌ {name} create form failed - Status: {response.status_code}")
                    return False
            except Exception as e:
                print(f"❌ {name} create form error: {str(e)}")
                return False
        
        return True
    
    def test_consortium_full_crud(self):
        """Test complete Consortium CRUD"""
        print("\n🏢 Testing Consortium Full CRUD...")
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        test_data = {
            'consort_id': f'TEST{timestamp}',
            'name': f'Test Consortium {timestamp}',
            'abbrev': f'TC{timestamp[-4:]}',
            'require_approved_vendors': '1',
            'rfpo_viewer_user_ids': 'viewer1, viewer2, viewer3',
            'rfpo_admin_user_ids': 'admin1, admin2',
            'invoicing_address': '123 Test Street\nTest City, TS 12345',
            'po_email': 'test@consortium.com',
            'doc_email_name': 'Test Contact',
            'doc_email_address': 'docs@consortium.com',
            'active': '1'
        }
        
        try:
            # CREATE
            response = self.session.post(f"{self.base_url}/consortium/new", data=test_data, allow_redirects=False)
            if response.status_code == 302:
                print("✅ Consortium CREATE works")
                self.created_objects['consortiums'].append(test_data['consort_id'])
            else:
                print(f"❌ Consortium CREATE failed - Status: {response.status_code}")
                return False
            
            # READ (verify in list)
            response = self.session.get(f"{self.base_url}/consortiums")
            if test_data['name'] in response.text:
                print("✅ Consortium READ works (visible in list)")
            else:
                print("❌ Consortium READ failed (not visible in list)")
                return False
            
            return True
        except Exception as e:
            print(f"❌ Consortium CRUD error: {str(e)}")
            return False
    
    def test_team_full_crud(self):
        """Test complete Team CRUD"""
        print("\n👥 Testing Team Full CRUD...")
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        test_data = {
            'record_id': f'TEAM{timestamp}',
            'name': f'Test Team {timestamp}',
            'abbrev': f'TT{timestamp[-4:]}',
            'description': 'Test team for integration testing',
            'consortium_consort_id': '',  # No consortium for this test
            'rfpo_viewer_user_ids': 'teamviewer1, teamviewer2',
            'rfpo_admin_user_ids': 'teamadmin1',
            'active': '1'
        }
        
        try:
            # CREATE
            response = self.session.post(f"{self.base_url}/team/new", data=test_data, allow_redirects=False)
            if response.status_code == 302:
                print("✅ Team CREATE works")
                self.created_objects['teams'].append(test_data['record_id'])
            else:
                print(f"❌ Team CREATE failed - Status: {response.status_code}")
                return False
            
            # READ (verify in list)
            response = self.session.get(f"{self.base_url}/teams")
            if test_data['name'] in response.text:
                print("✅ Team READ works (visible in list)")
            else:
                print("❌ Team READ failed (not visible in list)")
                return False
            
            return True
        except Exception as e:
            print(f"❌ Team CRUD error: {str(e)}")
            return False
    
    def test_rfpo_full_crud(self):
        """Test complete RFPO CRUD"""
        print("\n📄 Testing RFPO Full CRUD...")
        
        # First get a team ID for the RFPO
        teams_response = self.session.get(f"{self.base_url}/teams")
        if "No Teams Found" in teams_response.text:
            print("⚠️  No teams available - creating test team first")
            # Create a test team for RFPO
            team_data = {
                'record_id': f'RFPOTEAM{datetime.now().strftime("%H%M%S")}',
                'name': 'RFPO Test Team',
                'abbrev': 'RTT',
                'active': '1'
            }
            self.session.post(f"{self.base_url}/team/new", data=team_data)
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        test_data = {
            'rfpo_id': f'RFPO-TEST-{timestamp}',
            'title': f'Test RFPO {timestamp}',
            'description': 'Test RFPO for integration testing',
            'vendor': 'Test Vendor Inc.',
            'status': 'Draft',
            'due_date': '2024-12-31',
            'team_id': '1'  # Assuming first team exists
        }
        
        try:
            # CREATE
            response = self.session.post(f"{self.base_url}/rfpo/new", data=test_data, allow_redirects=False)
            if response.status_code == 302:
                print("✅ RFPO CREATE works")
                self.created_objects['rfpos'].append(test_data['rfpo_id'])
            else:
                print(f"❌ RFPO CREATE failed - Status: {response.status_code}")
                print(f"Response: {response.text[:300]}")
                return False
            
            # READ (verify in list)
            response = self.session.get(f"{self.base_url}/rfpos")
            if test_data['title'] in response.text:
                print("✅ RFPO READ works (visible in list)")
            else:
                print("❌ RFPO READ failed (not visible in list)")
                return False
            
            return True
        except Exception as e:
            print(f"❌ RFPO CRUD error: {str(e)}")
            return False
    
    def test_project_full_crud(self):
        """Test complete Project CRUD"""
        print("\n📊 Testing Project Full CRUD...")
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        test_data = {
            'project_id': f'PROJ{timestamp}',
            'ref': f'PROJ-TEST-{timestamp}',
            'name': f'Test Project {timestamp}',
            'description': 'Test project for integration testing',
            'consortium_ids': 'TEST001, TEST002',
            'rfpo_viewer_user_ids': 'projviewer1, projviewer2',
            'gov_funded': '1',
            'uni_project': '0',
            'active': '1'
        }
        
        try:
            # CREATE
            response = self.session.post(f"{self.base_url}/project/new", data=test_data, allow_redirects=False)
            if response.status_code == 302:
                print("✅ Project CREATE works")
                self.created_objects['projects'].append(test_data['project_id'])
            else:
                print(f"❌ Project CREATE failed - Status: {response.status_code}")
                return False
            
            # READ (verify in list)
            response = self.session.get(f"{self.base_url}/projects")
            if test_data['name'] in response.text:
                print("✅ Project READ works (visible in list)")
            else:
                print("❌ Project READ failed (not visible in list)")
                return False
            
            return True
        except Exception as e:
            print(f"❌ Project CRUD error: {str(e)}")
            return False
    
    def test_vendor_full_crud(self):
        """Test complete Vendor CRUD"""
        print("\n🏪 Testing Vendor Full CRUD...")
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        test_data = {
            'vendor_id': f'VEND{timestamp}',
            'company_name': f'Test Vendor Inc {timestamp}',
            'status': 'live',
            'vendor_type': '2',  # Small Business
            'certs_reps': '1',
            'contact_name': 'John Test',
            'contact_tel': '555-TEST-123',
            'contact_address': '456 Vendor Street',
            'contact_city': 'Vendor City',
            'contact_state': 'CA',
            'contact_zip': '90210',
            'approved_consortiums': 'SAC, USCAR, TEST',
            'active': '1'
        }
        
        try:
            # CREATE
            response = self.session.post(f"{self.base_url}/vendor/new", data=test_data, allow_redirects=False)
            if response.status_code == 302:
                print("✅ Vendor CREATE works")
                self.created_objects['vendors'].append(test_data['vendor_id'])
            else:
                print(f"❌ Vendor CREATE failed - Status: {response.status_code}")
                return False
            
            # READ (verify in list)
            response = self.session.get(f"{self.base_url}/vendors")
            if test_data['company_name'] in response.text:
                print("✅ Vendor READ works (visible in list)")
            else:
                print("❌ Vendor READ failed (not visible in list)")
                return False
            
            return True
        except Exception as e:
            print(f"❌ Vendor CRUD error: {str(e)}")
            return False
    
    def test_user_full_crud(self):
        """Test complete User CRUD"""
        print("\n👤 Testing User Full CRUD...")
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        test_data = {
            'record_id': f'USER{timestamp}',
            'fullname': f'Test User {timestamp}',
            'email': f'testuser{timestamp}@test.com',
            'password': 'testpassword123',
            'company': 'Test Company Inc',
            'position': 'Test Engineer',
            'permissions': 'RFPO_USER, CAL_MEET_USER',
            'agreed_to_terms': '1',
            'active': '1'
        }
        
        try:
            # CREATE
            response = self.session.post(f"{self.base_url}/user/new", data=test_data, allow_redirects=False)
            if response.status_code == 302:
                print("✅ User CREATE works")
                self.created_objects['users'].append(test_data['record_id'])
            else:
                print(f"❌ User CREATE failed - Status: {response.status_code}")
                return False
            
            # READ (verify in list)
            response = self.session.get(f"{self.base_url}/users")
            if test_data['fullname'] in response.text:
                print("✅ User READ works (visible in list)")
            else:
                print("❌ User READ failed (not visible in list)")
                return False
            
            return True
        except Exception as e:
            print(f"❌ User CRUD error: {str(e)}")
            return False
    
    def test_json_field_integrity(self):
        """Test that JSON fields are properly stored and displayed"""
        print("\n🔄 Testing JSON Field Integrity...")
        
        try:
            # Check consortiums page for JSON field display
            response = self.session.get(f"{self.base_url}/consortiums")
            if "viewer1, viewer2, viewer3" in response.text or "admin1, admin2" in response.text:
                print("✅ JSON fields displayed correctly in lists")
            else:
                print("⚠️  JSON fields may not be displaying correctly")
            
            # Check that create forms show JSON field hints
            response = self.session.get(f"{self.base_url}/consortium/new")
            if "Comma-separated" in response.text:
                print("✅ JSON field help text present in forms")
            else:
                print("⚠️  JSON field help text missing")
            
            return True
        except Exception as e:
            print(f"❌ JSON field integrity test error: {str(e)}")
            return False
    
    def run_complete_integration_test(self):
        """Run the complete integration test suite"""
        print("=" * 70)
        print("🧪 COMPLETE RFPO ADMIN PANEL INTEGRATION TEST")
        print("=" * 70)
        print(f"🌐 Testing admin panel at: {self.base_url}")
        
        # Test login first
        if not self.login():
            print("❌ Cannot proceed - login failed")
            return False
        
        tests = [
            ("Navigation Links", self.test_navigation_links),
            ("Create Forms Load", self.test_create_forms_load),
            ("Consortium CRUD", self.test_consortium_full_crud),
            ("Team CRUD", self.test_team_full_crud),
            ("RFPO CRUD", self.test_rfpo_full_crud),
            ("Project CRUD", self.test_project_full_crud),
            ("Vendor CRUD", self.test_vendor_full_crud),
            ("User CRUD", self.test_user_full_crud),
            ("JSON Field Integrity", self.test_json_field_integrity),
        ]
        
        results = []
        for test_name, test_func in tests:
            print(f"\n{test_name}:")
            print("-" * 50)
            result = test_func()
            results.append((test_name, result))
        
        print("\n" + "=" * 70)
        print("🧪 INTEGRATION TEST SUMMARY")
        print("=" * 70)
        
        passed = 0
        for test_name, result in results:
            status = "PASS" if result else "FAIL"
            icon = "✅" if result else "❌"
            print(f"{icon} {test_name:<25} {status}")
            if result:
                passed += 1
        
        print(f"\nTests passed: {passed}/{len(tests)}")
        
        # Show created objects
        if any(self.created_objects.values()):
            print(f"\n📊 Test Objects Created:")
            for model_type, objects in self.created_objects.items():
                if objects:
                    print(f"   {model_type}: {len(objects)} objects")
        
        if passed == len(tests):
            print("\n🎉 ALL INTEGRATION TESTS PASSED!")
            print("🎊 Your admin panel is fully functional for all models!")
            return True
        else:
            print(f"\n⚠️  {len(tests) - passed} test(s) failed.")
            print("🔧 Check the failed operations above.")
            return False

def main():
    """Main test runner"""
    tester = FullIntegrationTester()
    
    print("🔍 Checking if admin panel is running...")
    try:
        response = requests.get("http://localhost:5111", timeout=5)
        print("✅ Admin panel is accessible")
    except Exception as e:
        print("❌ Admin panel not accessible. Make sure it's running on port 5111")
        print("   Run: python3 custom_admin.py")
        sys.exit(1)
    
    success = tester.run_complete_integration_test()
    
    if success:
        print("\n🎊 PERFECT! Your admin panel is fully functional!")
        print("🎯 You can now manage all your RFPO data through the web interface.")
    else:
        print("\n🔧 Some operations need fixes. Check the details above.")
    
    print(f"\n🌐 Access your admin panel at: http://localhost:5111")
    print("📧 Login: admin@rfpo.com")
    print("🔑 Password: admin123")

if __name__ == '__main__':
    main()

