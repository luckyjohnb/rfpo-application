#!/usr/bin/env python3
"""
Fix admin password to use Administrator123!
"""

import bcrypt
import json

def fix_admin_password_to_correct():
    """Generate correct password hash and update users.json"""
    print("=== FIXING ADMIN PASSWORD TO Administrator123! ===")

    # Generate correct hash for "Administrator123!"
    password = "Administrator123!"
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
            print(f"🔐 Admin credentials are now:")
            print(f"   Username: admin")
            print(f"   Password: {password}")
            return True

        except Exception as e:
            print(f"❌ Error updating users.json: {e}")
            return False
    else:
        print("❌ Hash verification failed!")
        return False

if __name__ == "__main__":
    success = fix_admin_password_to_correct()
    print(f"\n{'='*60}")
    if success:
        print("🎉 ADMIN PASSWORD FIXED TO Administrator123!")
    else:
        print("💔 FAILED TO FIX PASSWORD")
    print("="*60)
