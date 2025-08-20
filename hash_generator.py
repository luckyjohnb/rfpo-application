#!/usr/bin/env python3
"""
Generate a new bcrypt hash for admin password
"""

import bcrypt

password = "admin"
# Generate hash using the same method as UserManager
salt = bcrypt.gensalt()
hash_bytes = bcrypt.hashpw(password.encode('utf-8'), salt)
hash_string = hash_bytes.decode('utf-8')

print(f"Password: {password}")
print(f"New hash: {hash_string}")

# Test verification
test_result = bcrypt.checkpw(password.encode('utf-8'), hash_string.encode('utf-8'))
print(f"Verification test: {test_result}")
