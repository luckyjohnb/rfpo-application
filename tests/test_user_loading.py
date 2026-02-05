#!/usr/bin/env python3
"""
Quick test to verify user loading works
"""
import json
import sys
import os

# Add the current directory to the path so we can import from app_working
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_user_loading():
    print("Testing user loading...")
    
    # Test basic JSON loading
    try:
        with open('config/users.json', 'r') as f:
            users_data = json.load(f)
        print(f"✅ JSON loaded successfully: {type(users_data)}")
        print(f"   Keys: {list(users_data.keys())}")
        print(f"   Values: {users_data}")
    except Exception as e:
        print(f"❌ JSON loading failed: {e}")
        return
    
    # Test converting to list
    try:
        users_list = list(users_data.values())
        print(f"✅ Converted to list successfully: {len(users_list)} users")
        for i, user in enumerate(users_list):
            print(f"   User {i}: {type(user)} - {user.get('username', 'NO_USERNAME')}")
    except Exception as e:
        print(f"❌ List conversion failed: {e}")
        return
    
    # Test user processing
    try:
        for user in users_list:
            print(f"✅ Processing user: {user['username']}")
            print(f"   Roles: {user.get('roles', [])}")
            print(f"   Status: {user.get('status', 'unknown')}")
            print(f"   Email: {user.get('email', 'no email')}")
    except Exception as e:
        print(f"❌ User processing failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("✅ All tests passed!")

if __name__ == '__main__':
    test_user_loading()
