#!/usr/bin/env python3
"""
Simple script to reset admin password to Administrator123!
"""

import sys
import os
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from user_management import UserManager

print("🔧 Resetting admin password to Administrator123!")

# Create UserManager
um = UserManager()

# Load current data
data = um._load_data()

# Generate the correct hash
correct_password = "Administrator123!"
correct_hash = um._hash_password(correct_password)

print(f"Generated hash: {correct_hash}")

# Update admin user
for user in data['users']:
    if user['username'] == 'admin':
        user['password_hash'] = correct_hash
        user['login_attempts'] = 0
        user['locked_until'] = None
        user['failed_login_attempts'] = 0
        break

# Save data
um._save_data(data)

# Test authentication
result = um.authenticate_user('admin', correct_password)
if result:
    print("✅ SUCCESS! Admin password is now Administrator123!")
else:
    print("❌ Failed to authenticate with new password")

print("\n" + "="*50)
print("LOGIN CREDENTIALS:")
print("Username: admin")
print("Password: Administrator123!")
print("="*50)
