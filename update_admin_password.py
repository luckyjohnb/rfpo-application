#!/usr/bin/env python3
import sys
import os
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from user_management import UserManager

# Create UserManager instance
um = UserManager()

# Generate hash for Administrator123!
password = "Administrator123!"
new_hash = um._hash_password(password)

print(f"Password: {password}")
print(f"Generated hash: {new_hash}")

# Test verification
verification = um._verify_password(password, new_hash)
print(f"Verification result: {verification}")

if verification:
    # Update users.json
    with open('config/users.json', 'r') as f:
        data = json.load(f)

    # Update admin user
    for user in data['users']:
        if user['username'] == 'admin':
            user['password_hash'] = new_hash
            user['login_attempts'] = 0
            user['locked_until'] = None
            user['failed_login_attempts'] = 0
            break

    # Save updated data
    with open('config/users.json', 'w') as f:
        json.dump(data, f, indent=2)

    print("✅ Password updated successfully!")
    print("New credentials:")
    print("Username: admin")
    print("Password: Administrator123!")
else:
    print("❌ Verification failed!")
