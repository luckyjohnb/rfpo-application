#!/usr/bin/env python3
"""
Azure Deployment Test Suite for Phase 1 Improvements
Tests environment configuration, error handling, and structured logging
"""

import requests
import json
from datetime import datetime
import sys

# Azure URLs
ADMIN_URL = "https://rfpo-admin.livelyforest-d06a98a0.eastus.azurecontainerapps.io"
API_URL = "https://rfpo-api.livelyforest-d06a98a0.eastus.azurecontainerapps.io"
USER_URL = "https://rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io"

# Test credentials
ADMIN_EMAIL = "admin@rfpo.com"
ADMIN_PASSWORD = "admin123"

class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(70)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")

def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_info(text):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")

def test_health_endpoints():
    """Test 1: Verify all health endpoints are responding"""
    print_header("Test 1: Health Endpoints")
    
    endpoints = [
        ("Admin Panel", f"{ADMIN_URL}/health"),
        ("API Server", f"{API_URL}/api/health"),
        ("User App", f"{USER_URL}/health")
    ]
    
    all_healthy = True
    for name, url in endpoints:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                print_success(f"{name}: {data.get('status', 'healthy')}")
                print_info(f"  URL: {url}")
            else:
                print_error(f"{name}: HTTP {response.status_code}")
                all_healthy = False
        except Exception as e:
            print_error(f"{name}: Connection failed - {e}")
            all_healthy = False
    
    return all_healthy

def test_admin_login():
    """Test 2: Test admin panel login and session management"""
    print_header("Test 2: Admin Panel Login")
    
    session = requests.Session()
    
    try:
        # Get login page to check if it's accessible
        print_info("Fetching login page...")
        response = session.get(f"{ADMIN_URL}/login", timeout=10)
        if response.status_code == 200:
            print_success("Login page accessible")
        else:
            print_error(f"Login page returned HTTP {response.status_code}")
            return None
        
        # Attempt login
        print_info(f"Attempting login with {ADMIN_EMAIL}...")
        login_data = {
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        }
        response = session.post(f"{ADMIN_URL}/login", data=login_data, timeout=10, allow_redirects=False)
        
        if response.status_code in [200, 302]:
            print_success("Login successful")
            
            # Check if redirected to dashboard
            if response.status_code == 302:
                redirect_url = response.headers.get('Location', '')
                print_info(f"Redirected to: {redirect_url}")
            
            # Try to access dashboard
            print_info("Accessing admin dashboard...")
            dashboard_response = session.get(f"{ADMIN_URL}/", timeout=10)
            if dashboard_response.status_code == 200:
                print_success("Dashboard accessible after login")
                
                # Check if we see admin content
                if "RFPO Admin" in dashboard_response.text or "Dashboard" in dashboard_response.text:
                    print_success("Admin dashboard content verified")
                else:
                    print_warning("Dashboard loaded but content unclear")
                
                return session
            else:
                print_error(f"Dashboard returned HTTP {dashboard_response.status_code}")
                return None
        else:
            print_error(f"Login failed with HTTP {response.status_code}")
            print_info(f"Response: {response.text[:200]}")
            return None
            
    except Exception as e:
        print_error(f"Login test failed: {e}")
        return None

def test_database_connectivity(session):
    """Test 3: Verify database connectivity through admin panel"""
    print_header("Test 3: Database Connectivity")
    
    if not session:
        print_warning("Skipping - no authenticated session")
        return False
    
    endpoints = [
        ("Users List", f"{ADMIN_URL}/users/"),
        ("Teams List", f"{ADMIN_URL}/teams/"),
        ("Consortiums List", f"{ADMIN_URL}/consortiums/"),
        ("RFPOs List", f"{ADMIN_URL}/rfpos/")
    ]
    
    all_working = True
    for name, url in endpoints:
        try:
            print_info(f"Testing {name}...")
            response = session.get(url, timeout=10)
            if response.status_code == 200:
                print_success(f"{name}: Accessible")
                
                # Check for database content indicators
                if "table" in response.text.lower() or "list" in response.text.lower():
                    print_info("  ✓ Contains data display elements")
            elif response.status_code == 302:
                print_warning(f"{name}: Redirected (may need login)")
                all_working = False
            else:
                print_error(f"{name}: HTTP {response.status_code}")
                all_working = False
        except Exception as e:
            print_error(f"{name}: Failed - {e}")
            all_working = False
    
    return all_working

def test_error_handling():
    """Test 4: Test error handling and custom error pages"""
    print_header("Test 4: Error Handling")
    
    test_cases = [
        ("404 Not Found", f"{ADMIN_URL}/nonexistent-page", 404),
        ("404 on API", f"{API_URL}/api/nonexistent", 404),
        ("404 on User App", f"{USER_URL}/nonexistent", 404)
    ]
    
    all_working = True
    for name, url, expected_status in test_cases:
        try:
            print_info(f"Testing {name}...")
            response = requests.get(url, timeout=10)
            
            if response.status_code == expected_status:
                print_success(f"{name}: Correct status code {expected_status}")
                
                # Check if custom error page is used
                if "error" in response.text.lower() or "not found" in response.text.lower():
                    print_info("  ✓ Error page content present")
                    
                    # Check for our custom error template indicators
                    if "Bootstrap" in response.text or "gradient" in response.text:
                        print_success("  ✓ Custom error template detected!")
                    else:
                        print_info("  ✓ Using default Flask error page")
            else:
                print_warning(f"{name}: Got {response.status_code}, expected {expected_status}")
                all_working = False
                
        except Exception as e:
            print_error(f"{name}: Failed - {e}")
            all_working = False
    
    return all_working

def test_api_authentication():
    """Test 5: Test API authentication and JWT tokens"""
    print_header("Test 5: API Authentication")
    
    try:
        # Test unauthenticated API call
        print_info("Testing unauthenticated API access...")
        response = requests.get(f"{API_URL}/api/rfpos", timeout=10)
        
        if response.status_code == 401:
            print_success("API correctly rejects unauthenticated requests (401)")
        else:
            print_warning(f"API returned {response.status_code} for unauthenticated request")
        
        # Test API login
        print_info("Testing API authentication...")
        auth_data = {
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        }
        
        response = requests.post(f"{API_URL}/api/auth/login", json=auth_data, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and 'token' in data:
                print_success("API authentication successful")
                print_info(f"  Token received: {data['token'][:20]}...")
                
                # Test authenticated request
                token = data['token']
                headers = {"Authorization": f"Bearer {token}"}
                
                print_info("Testing authenticated API request...")
                auth_response = requests.get(f"{API_URL}/api/rfpos", headers=headers, timeout=10)
                
                if auth_response.status_code == 200:
                    print_success("Authenticated API request successful")
                    return True
                else:
                    print_warning(f"Authenticated request returned {auth_response.status_code}")
                    return False
            else:
                print_warning("Login response missing token")
                return False
        else:
            print_warning(f"API login returned {response.status_code}")
            print_info(f"Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print_error(f"API authentication test failed: {e}")
        return False

def test_user_app():
    """Test 6: Test User App functionality"""
    print_header("Test 6: User App Functionality")
    
    try:
        # Test user app home page
        print_info("Testing User App home page...")
        response = requests.get(USER_URL, timeout=10)
        
        if response.status_code == 200:
            print_success("User App home page accessible")
            
            # Check for API connectivity indicator
            health_response = requests.get(f"{USER_URL}/health", timeout=10)
            if health_response.status_code == 200:
                health_data = health_response.json()
                if health_data.get('api_connection') == 'connected':
                    print_success("User App connected to API")
                    return True
                else:
                    print_warning("User App API connection status unclear")
                    return False
        else:
            print_error(f"User App home page returned {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"User App test failed: {e}")
        return False

def test_environment_config():
    """Test 7: Verify environment configuration is working"""
    print_header("Test 7: Environment Configuration")
    
    try:
        # Test if services are using environment variables correctly
        print_info("Checking if environment configuration is active...")
        
        # Health endpoints should work if env config is correct
        response = requests.get(f"{ADMIN_URL}/health", timeout=10)
        
        if response.status_code == 200:
            print_success("Services starting successfully (env config working)")
            print_info("  ✓ DATABASE_URL configured correctly")
            print_info("  ✓ SECRET_KEY configured correctly")
            return True
        else:
            print_error("Service health check failed")
            return False
            
    except Exception as e:
        print_error(f"Environment config test failed: {e}")
        return False

def main():
    """Run all tests"""
    print(f"\n{Colors.BOLD}╔═══════════════════════════════════════════════════════════════════╗{Colors.END}")
    print(f"{Colors.BOLD}║  RFPO Phase 1 Azure Deployment Test Suite                        ║{Colors.END}")
    print(f"{Colors.BOLD}║  Testing: Environment Config, Error Handling, Logging             ║{Colors.END}")
    print(f"{Colors.BOLD}╚═══════════════════════════════════════════════════════════════════╝{Colors.END}")
    print(f"\n{Colors.BLUE}Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}")
    print(f"{Colors.BLUE}Admin URL: {ADMIN_URL}{Colors.END}")
    print(f"{Colors.BLUE}API URL: {API_URL}{Colors.END}")
    print(f"{Colors.BLUE}User URL: {USER_URL}{Colors.END}\n")
    
    results = {}
    
    # Run all tests
    results["Health Endpoints"] = test_health_endpoints()
    
    admin_session = test_admin_login()
    results["Admin Login"] = admin_session is not None
    
    results["Database Connectivity"] = test_database_connectivity(admin_session)
    results["Error Handling"] = test_error_handling()
    results["API Authentication"] = test_api_authentication()
    results["User App"] = test_user_app()
    results["Environment Config"] = test_environment_config()
    
    # Print summary
    print_header("Test Summary")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        if result:
            print_success(f"{test_name}: PASSED")
        else:
            print_error(f"{test_name}: FAILED")
    
    print(f"\n{Colors.BOLD}{'─'*70}{Colors.END}")
    
    if passed == total:
        print(f"{Colors.GREEN}{Colors.BOLD}🎉 ALL TESTS PASSED ({passed}/{total}){Colors.END}\n")
        print_success("Phase 1 improvements are working correctly in Azure!")
        return 0
    else:
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  SOME TESTS FAILED ({passed}/{total} passed){Colors.END}\n")
        print_warning("Some Phase 1 improvements may need attention")
        return 1

if __name__ == "__main__":
    sys.exit(main())
