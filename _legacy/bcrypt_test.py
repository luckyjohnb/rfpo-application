import bcrypt

password = "Administrator123!"
print(f"Testing bcrypt with password: {password}")

# Generate hash
hash_val = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
hash_str = hash_val.decode('utf-8')
print(f"Generated hash: {hash_str}")

# Test verification
check = bcrypt.checkpw(password.encode('utf-8'), hash_val)
print(f"Hash verification: {check}")

print(f"Hash length: {len(hash_str)}")
print(f"Hash starts with $2b$: {hash_str.startswith('$2b$')}")
