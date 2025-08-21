#!/usr/bin/env python3
"""
Direct test of teams API
"""
import requests
import json

def test_teams_api():
    print("Testing Teams API...")

    # Test without authentication first
    print("\n1. Testing teams API without authentication...")
    teams_response = requests.get('http://127.0.0.1:5001/api/teams')

    print(f"   Status code: {teams_response.status_code}")
    print(f"   Response text: {teams_response.text}")

    if teams_response.status_code == 200:
        try:
            teams_data = teams_response.json()
            print(f"✅ Teams API successful")
            print(f"   Found {len(teams_data)} teams:")
            for team in teams_data:
                print(f"     - {team.get('name')} ({team.get('abbrev')})")
        except Exception as e:
            print(f"❌ Failed to parse JSON: {e}")

    # Test creating a team
    print("\n2. Testing create team...")
    team_data = {
        "name": "Test Team",
        "abbrev": "TT",
        "consortium_id": 1,
        "active": True,
        "description": "A test team for verification"
    }

    create_response = requests.post('http://127.0.0.1:5001/api/teams',
                                   json=team_data)

    print(f"   Status code: {create_response.status_code}")
    print(f"   Response text: {create_response.text}")

    if create_response.status_code == 201:
        print("✅ Team created successfully")
        created_team = create_response.json()

        # Test getting all teams again
        print("\n3. Testing teams API after creation...")
        teams_response = requests.get('http://127.0.0.1:5001/api/teams')

        if teams_response.status_code == 200:
            teams_data = teams_response.json()
            print(f"✅ Teams API successful")
            print(f"   Found {len(teams_data)} teams:")
            for team in teams_data:
                print(f"     - {team.get('name')} ({team.get('abbrev')})")
    else:
        print(f"❌ Team creation failed")

if __name__ == "__main__":
    test_teams_api()
