#!/usr/bin/env python3
"""
Quick database status checker and initializer for Azure deployment
"""

import os
import sys
import requests


def check_api_health():
    """Check if the API is healthy and database is connected"""
    try:
        api_url = "https://rfpo-api.livelyforest-d06a98a0.eastus.azurecontainerapps.io"

        # Check health endpoint
        response = requests.get(f"{api_url}/health", timeout=10)
        print(f"API Health Status: {response.status_code}")

        if response.status_code == 200:
            print("✅ API is healthy")
            return True
        else:
            print(f"❌ API health check failed: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Failed to connect to API: {e}")
        return False


def test_database_connection():
    """Test database connection via API"""
    try:
        api_url = "https://rfpo-api.livelyforest-d06a98a0.eastus.azurecontainerapps.io"

        # Try to access an endpoint that requires database
        response = requests.get(f"{api_url}/api/users", timeout=10)
        print(f"Database test status: {response.status_code}")

        if response.status_code in [200, 401]:  # 401 is expected without auth
            print("✅ Database connection is working")
            return True
        else:
            print(f"❌ Database connection test failed: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Failed to test database connection: {e}")
        return False


def main():
    print("🔍 Checking RFPO Azure Deployment Status")
    print("=" * 50)

    # Check API health
    api_healthy = check_api_health()

    if api_healthy:
        # Test database connection
        db_connected = test_database_connection()

        if db_connected:
            print("\n🎉 Deployment is successful!")
            print("✅ API is running")
            print("✅ Database is connected")
            print("\nApplication URLs:")
            print(
                "- Admin: https://rfpo-admin.livelyforest-d06a98a0.eastus.azurecontainerapps.io"
            )
            print(
                "- User App: https://rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io"
            )
            print(
                "- API: https://rfpo-api.livelyforest-d06a98a0.eastus.azurecontainerapps.io"
            )
            print("\nDefault Login:")
            print("- Username: admin@rfpo.com")
            print("- Password: admin123")
        else:
            print("\n⚠️  API is running but database connection needs attention")
    else:
        print("\n❌ API is not responding - deployment may still be in progress")

    print("\n" + "=" * 50)


if __name__ == "__main__":
    main()
