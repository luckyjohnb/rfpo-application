#!/usr/bin/env python3
"""
Direct test of user management API
"""
import requests
import json

def test_user_api():
    print("Testing User Management API...")
    
    # First, test login
    print("\n1. Testing login...")
    login_response = requests.post('http://127.0.0.1:5000/api/auth/login', 
                                   json={'username': 'admin', 'password': 'Administrator123!'})
    
    if login_response.status_code != 200:
        print(f"❌ Login failed with status {login_response.status_code}")
        print(f"   Response: {login_response.text}")
        return
    
    login_data = login_response.json()
    if not login_data.get('success'):
        print(f"❌ Login failed: {login_data.get('message')}")
        return
    
    token = login_data.get('token')
    print(f"✅ Login successful, token: {token[:20]}...")
    
    # Test get users API
    print("\n2. Testing get users API...")
    headers = {'Authorization': f'Bearer {token}'}
    users_response = requests.get('http://127.0.0.1:5000/api/users', headers=headers)
    
    print(f"   Status code: {users_response.status_code}")
    print(f"   Response text: {users_response.text}")
    
    if users_response.status_code == 200:
        try:
            users_data = users_response.json()
            print(f"✅ Users API successful")
            print(f"   Success: {users_data.get('success')}")
            if users_data.get('success'):
                users = users_data.get('users', [])
                print(f"   Found {len(users)} users:")
                for user in users:
                    print(f"     - {user.get('username')} ({user.get('roles')})")
            else:
                print(f"   Error: {users_data.get('message')}")
        except Exception as e:
            print(f"❌ Failed to parse JSON: {e}")
    else:
        print(f"❌ Users API failed")

if __name__ == '__main__':
    print("Make sure Flask app is running first!")
    print("Run: python app_working.py")
    print("=" * 50)
    try:
        test_user_api()
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Flask app. Is it running?")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
