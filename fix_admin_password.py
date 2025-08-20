#!/usr/bin/env python3
"""
Generate correct password hash for admin
"""

import bcrypt
import json

def fix_admin_password():
    """Generate correct password hash and update users.json"""
    print("=== FIXING ADMIN PASSWORD ===")

    # Generate correct hash for "admin"
    password = "admin"
    correct_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    correct_hash_str = correct_hash.decode('utf-8')

    print(f"🔑 Password: {password}")
    print(f"🔐 New hash: {correct_hash_str}")

    # Verify the new hash works
    verification = bcrypt.checkpw(password.encode('utf-8'), correct_hash)
    print(f"✅ Verification test: {verification}")

    if verification:
        print("✅ New hash verified successfully!")

        # Load and update users.json
        try:
            with open('config/users.json', 'r') as f:
                data = json.load(f)

            # Update admin user password hash
            for user in data['users']:
                if user['username'] == 'admin':
                    user['password_hash'] = correct_hash_str
                    user['login_attempts'] = 0
                    user['locked_until'] = None
                    user['failed_login_attempts'] = 0
                    break

            # Save updated file
            with open('config/users.json', 'w') as f:
                json.dump(data, f, indent=2)

            print("✅ users.json updated successfully!")
            return True

        except Exception as e:
            print(f"❌ Error updating users.json: {e}")
            return False
    else:
        print("❌ Hash verification failed!")
        return False

if __name__ == "__main__":
    success = fix_admin_password()
    print(f"\n{'='*50}")
    if success:
        print("🎉 ADMIN PASSWORD FIXED!")
    else:
        print("💔 FAILED TO FIX PASSWORD")
    print("="*50)
