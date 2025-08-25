#!/usr/bin/env python3
"""
Test authentication directly with requests module
"""

import requests
import json

def test_endpoints():
    """Test various endpoints to see which ones work"""
    base_url = "http://127.0.0.1:5000"

    endpoints = [
        "/hello",
        "/test-auth",
        "/app",
        "/api/auth/login"
    ]

    print("=== ENDPOINT CONNECTIVITY TEST ===")

    for endpoint in endpoints:
        url = f"{base_url}{endpoint}"
        try:
            print(f"\n🌐 Testing: {url}")

            if endpoint == "/api/auth/login":
                # POST request for login
                response = requests.post(
                    url,
                    json={"username": "admin", "password": "admin"},
                    headers={'Content-Type': 'application/json'},
                    timeout=5
                )
            else:
                # GET request for other endpoints
                response = requests.get(url, timeout=5)

            print(f"📊 Status: {response.status_code}")
            print(f"📄 Content Length: {len(response.text)}")

            if response.status_code == 200:
                print("✅ SUCCESS")
                if endpoint == "/api/auth/login":
                    data = response.json()
                    print(f"🎫 Token received: {bool(data.get('token'))}")
            else:
                print(f"❌ FAILED: {response.text[:200]}")

        except requests.exceptions.ConnectionError:
            print("❌ CONNECTION FAILED - Server not reachable")
        except Exception as e:
            print(f"❌ ERROR: {e}")

    print(f"\n{'='*50}")

if __name__ == "__main__":
    test_endpoints()
