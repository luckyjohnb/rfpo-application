#!/usr/bin/env python3
"""
Comprehensive test suite for the Flask application
Tests user management, authentication, file upload, and API endpoints
"""
import unittest
import json
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
import sys

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app import app
    from user_management import UserManager, UserStatus
    from config import TestingConfig
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)

class TestUserManagement(unittest.TestCase):
    """Test user management functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.test_data_file = os.path.join(self.test_dir, 'test_users.json')
        self.user_manager = UserManager(self.test_data_file)
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir)
    
    def test_create_user_success(self):
        """Test successful user creation"""
        result = self.user_manager.create_user(
            username="testuser",
            email="test@example.com",
            password="TestPassword123!",
            display_name="Test User"
        )
        self.assertTrue(result["success"])
        self.assertIn("user_id", result)
    
    def test_create_user_weak_password(self):
        """Test user creation with weak password"""
        result = self.user_manager.create_user(
            username="testuser",
            email="test@example.com",
            password="weak",
            display_name="Test User"
        )
        self.assertFalse(result["success"])
        self.assertIn("Password must be at least", result["message"])
    
    def test_authenticate_user_success(self):
        """Test successful user authentication"""
        # Create user first
        self.user_manager.create_user(
            username="testuser",
            email="test@example.com",
            password="TestPassword123!",
            display_name="Test User"
        )
        
        # Test authentication
        user = self.user_manager.authenticate_user("testuser", "TestPassword123!")
        self.assertIsNotNone(user)
        self.assertEqual(user["username"], "testuser")
    
    def test_authenticate_user_failure(self):
        """Test failed user authentication"""
        # Create user first
        self.user_manager.create_user(
            username="testuser",
            email="test@example.com",
            password="TestPassword123!",
            display_name="Test User"
        )
        
        # Test wrong password
        user = self.user_manager.authenticate_user("testuser", "wrongpassword")
        self.assertIsNone(user)
    
    def test_duplicate_username(self):
        """Test creating user with duplicate username"""
        # Create first user
        self.user_manager.create_user(
            username="testuser",
            email="test1@example.com",
            password="TestPassword123!",
            display_name="Test User 1"
        )
        
        # Try to create second user with same username
        result = self.user_manager.create_user(
            username="testuser",
            email="test2@example.com",
            password="TestPassword123!",
            display_name="Test User 2"
        )
        self.assertFalse(result["success"])
        self.assertIn("Username already exists", result["message"])

class TestFlaskApp(unittest.TestCase):
    """Test Flask application endpoints"""
    
    def setUp(self):
        """Set up test client"""
        app.config.from_object(TestingConfig)
        self.app = app.test_client()
        self.app.testing = True
        
        # Create test directories
        self.test_dir = tempfile.mkdtemp()
        app.config['UPLOAD_FOLDER'] = self.test_dir
        
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_landing_page(self):
        """Test landing page loads"""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
    
    def test_app_page(self):
        """Test main app page loads"""
        response = self.app.get('/app')
        self.assertEqual(response.status_code, 200)
    
    def test_login_endpoint_missing_data(self):
        """Test login endpoint with missing data"""
        response = self.app.post('/api/auth/login',
                                json={},
                                content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data["success"])
    
    def test_register_endpoint_missing_data(self):
        """Test registration endpoint with missing data"""
        response = self.app.post('/api/auth/register',
                                json={"username": "test"},
                                content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data["success"])
    
    @patch('app.PANDAS_AVAILABLE', False)
    def test_upload_without_pandas(self):
        """Test file upload when pandas is not available"""
        data = {'file': (tempfile.NamedTemporaryFile(suffix='.csv'), 'test.csv')}
        response = self.app.post('/upload', data=data)
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertIn("pandas not installed", data["error"])

class TestSecurity(unittest.TestCase):
    """Test security features"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.test_data_file = os.path.join(self.test_dir, 'test_users.json')
        self.user_manager = UserManager(self.test_data_file)
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir)
    
    def test_password_hashing(self):
        """Test password is properly hashed"""
        result = self.user_manager.create_user(
            username="testuser",
            email="test@example.com",
            password="TestPassword123!",
            display_name="Test User"
        )
        
        # Get user data
        user = self.user_manager.get_user_by_username("testuser")
        
        # Password should be hashed, not stored in plain text
        self.assertNotEqual(user["password_hash"], "TestPassword123!")
        self.assertTrue(user["password_hash"].startswith("$2b$"))
    
    def test_account_lockout(self):
        """Test account lockout after multiple failed attempts"""
        # Create user
        self.user_manager.create_user(
            username="testuser",
            email="test@example.com",
            password="TestPassword123!",
            display_name="Test User"
        )
        
        # Attempt multiple failed logins
        for _ in range(6):  # More than max_login_attempts
            result = self.user_manager.authenticate_user("testuser", "wrongpassword")
            self.assertIsNone(result)
        
        # Even correct password should fail now due to lockout
        result = self.user_manager.authenticate_user("testuser", "TestPassword123!")
        self.assertIsNone(result)

class TestDataValidation(unittest.TestCase):
    """Test data validation"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.test_data_file = os.path.join(self.test_dir, 'test_users.json')
        self.user_manager = UserManager(self.test_data_file)
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir)
    
    def test_email_validation(self):
        """Test email format validation"""
        # Invalid email
        result = self.user_manager.create_user(
            username="testuser",
            email="invalid-email",
            password="TestPassword123!",
            display_name="Test User"
        )
        self.assertFalse(result["success"])
        self.assertIn("Invalid email format", result["message"])
        
        # Valid email
        result = self.user_manager.create_user(
            username="testuser",
            email="valid@example.com",
            password="TestPassword123!",
            display_name="Test User"
        )
        self.assertTrue(result["success"])
    
    def test_password_complexity(self):
        """Test password complexity requirements"""
        test_cases = [
            ("short", False, "Password must be at least"),
            ("nouppercase123!", False, "uppercase letter"),
            ("NOLOWERCASE123!", False, "lowercase letter"),
            ("NoNumbers!", False, "number"),
            ("NoSpecialChars123", False, "special character"),
            ("ValidPassword123!", True, ""),
        ]
        
        for password, should_succeed, error_contains in test_cases:
            result = self.user_manager.create_user(
                username=f"testuser_{password}",
                email=f"test_{password}@example.com",
                password=password,
                display_name="Test User"
            )
            
            if should_succeed:
                self.assertTrue(result["success"], f"Password '{password}' should be valid")
            else:
                self.assertFalse(result["success"], f"Password '{password}' should be invalid")
                self.assertIn(error_contains, result["message"])

def run_tests():
    """Run all tests"""
    print("Running comprehensive test suite...")
    print("=" * 60)
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestUserManagement,
        TestFlaskApp,
        TestSecurity,
        TestDataValidation
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback.split('AssertionError: ')[-1].split('\\n')[0]}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback.split('\\n')[-2]}")
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
