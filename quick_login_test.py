#!/usr/bin/env python3
"""
Quick login test to identify the exact error
"""

import requests
import json

def main():
    print("🔐 Quick Login Test")
    print("=" * 30)
    
    # Test admin panel
    print("Testing Admin Panel...")
    try:
        response = requests.get("http://localhost:5111/login", timeout=5)
        print(f"✅ Admin Panel Status: {response.status_code}")
    except Exception as e:
        print(f"❌ Admin Panel Error: {e}")
    
    # Test user app
    print("Testing User App...")
    try:
        response = requests.get("http://localhost:5001/login", timeout=5)
        print(f"✅ User App Status: {response.status_code}")
    except Exception as e:
        print(f"❌ User App Error: {e}")
    
    # Test login API
    print("Testing Login API...")
    try:
        login_data = {
            "username": "admin@rfpo.com",
            "password": "admin123",
            "remember_me": False
        }
        response = requests.post("http://localhost:5001/api/auth/login", json=login_data, timeout=5)
        result = response.json()
        
        if result.get('success'):
            print("✅ Login API Working!")
            print(f"   User: {result['user']['display_name']}")
        else:
            print(f"❌ Login Failed: {result.get('message')}")
    except Exception as e:
        print(f"❌ Login API Error: {e}")

if __name__ == '__main__':
    main()