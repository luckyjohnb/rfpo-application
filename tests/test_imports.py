#!/usr/bin/env python3
"""
Quick test to check what's failing in app.py
"""
import sys
import os

print("Testing Flask app imports...")

try:
    print("✅ Testing basic imports...")
    from flask import Flask, render_template, request, jsonify, send_file

    print("✅ Flask imports successful")
except Exception as e:
    print(f"❌ Flask import failed: {e}")
    sys.exit(1)

try:
    print("✅ Testing user_management import...")
    from user_management import UserManager

    print("✅ UserManager import successful")
except Exception as e:
    print(f"❌ UserManager import failed: {e}")
    print("This might be why your app isn't working!")

try:
    print("✅ Testing app.py import...")
    import app

    print("✅ app.py import successful")
    print(f"App routes: {[rule.rule for rule in app.app.url_map.iter_rules()]}")
except Exception as e:
    print(f"❌ app.py import failed: {e}")
    print("This is the main issue!")

print("\nDone testing.")
