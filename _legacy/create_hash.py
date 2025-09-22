import bcrypt

# Create hash for "Administrator123!"
password = "Administrator123!"
salt = bcrypt.gensalt()
hash_bytes = bcrypt.hashpw(password.encode('utf-8'), salt)
hash_string = hash_bytes.decode('utf-8')

print(f"Password: {password}")
print(f"Hash: {hash_string}")

# Verify it works
verification = bcrypt.checkpw(password.encode('utf-8'), hash_bytes)
print(f"Verification: {verification}")

# Write to a file so we can see it
with open('correct_hash.txt', 'w') as f:
    f.write(hash_string)
