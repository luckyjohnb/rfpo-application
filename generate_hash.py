import bcrypt
password = "Administrator123!"
hash_val = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
print(f"Password hash: {hash_val}")
