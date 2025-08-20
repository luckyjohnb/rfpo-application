import bcrypt

password = "Administrator123!"
hash_bytes = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
hash_string = hash_bytes.decode('utf-8')

print(f"Password: {password}")
print(f"Hash: {hash_string}")

# Test verification
test = bcrypt.checkpw(password.encode('utf-8'), hash_string.encode('utf-8'))
print(f"Verification: {test}")
