#!/usr/bin/env python3
"""
Simple test to isolate the exact error
"""
import json

def test_users_loading():
    print("=== Testing User Loading ===")
    
    try:
        # Load the JSON file
        with open('config/users.json', 'r') as f:
            users_data = json.load(f)
        
        print(f"✅ JSON loaded: {type(users_data)}")
        print(f"Keys: {list(users_data.keys())}")
        
        # Test converting to list (this is where the error might be)
        users_list = []
        for username, user_data in users_data.items():
            print(f"Processing: {username} -> {type(user_data)}")
            if isinstance(user_data, dict):
                users_list.append(user_data)
            else:
                print(f"❌ ERROR: Expected dict, got {type(user_data)}")
                print(f"Data: {user_data}")
        
        print(f"✅ Created list with {len(users_list)} users")
        
        # Test processing each user
        for i, user in enumerate(users_list):
            print(f"\nUser {i}:")
            print(f"  Type: {type(user)}")
            try:
                print(f"  Username: {user.get('username', 'MISSING')}")
                print(f"  Roles: {user.get('roles', 'MISSING')}")
                print(f"  Status: {user.get('status', 'MISSING')}")
            except Exception as e:
                print(f"  ❌ Error accessing user data: {e}")
                print(f"  Raw data: {user}")
        
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_users_loading()
