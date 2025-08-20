from user_management import UserManager

# Create UserManager instance
um = UserManager()

# Create admin user
print("Creating admin user...")
result = um.create_user(
    username="admin",
    email="admin@example.com",
    password="Administrator123!",
    display_name="System Administrator",
    roles=["Administrator"],
    status="active"
)

print(f"Create result: {result}")

# Test authentication
print("\nTesting authentication...")
auth_result = um.authenticate_user("admin", "Administrator123!")
print(f"Auth result: {auth_result is not None}")

if auth_result:
    print(f"Authenticated user: {auth_result.get('username')}")
else:
    print("Authentication failed")
