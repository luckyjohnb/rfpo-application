#!/usr/bin/env python3
"""
Test script for Application Settings API
"""
import urllib.request
import urllib.parse
import json
import sys


def test_get_settings():
    """Test getting application settings"""
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:5000/api/settings",
            headers={
                "Authorization": "Bearer test-token",  # Will fail, but test endpoint
                "Content-Type": "application/json",
            },
        )
        response = urllib.request.urlopen(req)
        data = json.loads(response.read().decode("utf-8"))
        print("✅ Settings API endpoint accessible")
        return True
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("✅ Settings API endpoint requires auth (expected)")
            return True
        else:
            print(f"❌ Settings API error: {e.code}")
            return False
    except Exception as e:
        print(f"❌ Settings API connection error: {e}")
        return False


def test_app_page():
    """Test main application page"""
    try:
        response = urllib.request.urlopen("http://127.0.0.1:5000/app")
        content = response.read().decode("utf-8")

        checks = [
            ("ACME App", "Application name"),
            ("Application Settings", "Settings menu"),
            ("Configuration", "Config menu"),
            ("loadApplicationSettings", "Settings JS function"),
        ]

        results = []
        for text, description in checks:
            found = text in content
            status = "✅" if found else "❌"
            print(f"{status} {description}: {'Found' if found else 'Missing'}")
            results.append(found)

        return all(results)
    except Exception as e:
        print(f"❌ App page error: {e}")
        return False


def main():
    """Run all tests"""
    print("🧪 Testing Application Settings Implementation\n")

    tests = [("Application Page", test_app_page), ("Settings API", test_get_settings)]

    results = []
    for name, test_func in tests:
        print(f"\n📋 Testing {name}:")
        result = test_func()
        results.append(result)

    print(f"\n📊 Test Results:")
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
