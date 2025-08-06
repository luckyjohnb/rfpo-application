#!/usr/bin/env python3
"""
Quick environment test to verify dependencies
"""
import sys
import os

print("=" * 50)
print("🔍 ENVIRONMENT TEST")
print("=" * 50)

# Check Python version
print(f"Python Version: {sys.version}")
print(f"Python Executable: {sys.executable}")

# Check current directory
print(f"Current Directory: {os.getcwd()}")

# Test imports
dependencies = [
    'flask',
    'bcrypt', 
    'jwt',
    'pandas',
    'numpy',
    'user_management'
]

for dep in dependencies:
    try:
        __import__(dep)
        print(f"✅ {dep} - Available")
    except ImportError as e:
        print(f"❌ {dep} - Not available: {e}")

# Check if user data exists
users_file = os.path.join('config', 'users.json')
if os.path.exists(users_file):
    print(f"✅ User data file exists: {users_file}")
else:
    print(f"⚠️ User data file missing: {users_file}")

# Check directories
dirs = ['uploads', 'config', 'logs', 'templates', 'static']
for dir_name in dirs:
    if os.path.exists(dir_name):
        print(f"✅ Directory exists: {dir_name}")
    else:
        print(f"❌ Directory missing: {dir_name}")

print("=" * 50)
print("Environment test complete!")
