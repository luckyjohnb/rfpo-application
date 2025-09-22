#!/usr/bin/env python3
"""
Test team API with authentication
"""
import requests
import json

def test_authentication_and_teams():
    base_url = 'http://127.0.0.1:5000'

    print("🔐 Testing Team API Authentication...")
    print("=" * 50)

    # Step 1: Login to get token
    print("\n1. Logging in...")
    login_data = {
        'username': 'admin',
        'password': 'Administrator123!'
    }

    try:
        login_response = requests.post(f'{base_url}/api/auth/login',
                                     json=login_data,
                                     timeout=10)

        if login_response.status_code == 200:
            login_result = login_response.json()
            if login_result.get('success'):
                token = login_result.get('token')
                print(f"✅ Login successful, token received")

                # Step 2: Test teams API with authentication
                print("\n2. Testing teams API with authentication...")
                headers = {
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                }

                teams_response = requests.get(f'{base_url}/api/teams',
                                            headers=headers,
                                            timeout=10)

                print(f"   Status Code: {teams_response.status_code}")
                print(f"   Response: {teams_response.text}")

                if teams_response.status_code == 200:
                    teams = teams_response.json()
                    print(f"✅ Teams API working! Found {len(teams)} teams")

                    # Step 3: Test creating a team
                    print("\n3. Testing team creation...")
                    test_team = {
                        'name': 'Test Team API',
                        'abbrev': 'TTA',
                        'consortium_id': 1,
                        'active': True,
                        'description': 'Test team created via API'
                    }

                    create_response = requests.post(f'{base_url}/api/teams',
                                                  json=test_team,
                                                  headers=headers,
                                                  timeout=10)

                    print(f"   Create Status: {create_response.status_code}")
                    print(f"   Create Response: {create_response.text}")

                    if create_response.status_code == 201:
                        print("✅ Team creation successful!")

                        # Test getting teams again
                        teams_response = requests.get(f'{base_url}/api/teams',
                                                    headers=headers,
                                                    timeout=10)
                        if teams_response.status_code == 200:
                            teams = teams_response.json()
                            print(f"✅ Now have {len(teams)} teams total")
                    else:
                        print("❌ Team creation failed")

                else:
                    print("❌ Teams API failed")
            else:
                print(f"❌ Login failed: {login_result.get('message')}")
        else:
            print(f"❌ Login request failed with status {login_response.status_code}")
            print(f"   Response: {login_response.text}")

    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    test_authentication_and_teams()
