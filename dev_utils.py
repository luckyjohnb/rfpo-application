#!/usr/bin/env python3
"""
Development utility script for Flask application
Provides helpful development commands and database operations
"""
import os
import sys
import json
import argparse
from datetime import datetime, timedelta

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from user_management import UserManager, UserRole, UserStatus
    from config import DevelopmentConfig, ProductionConfig
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)


def create_sample_users():
    """Create sample users for development"""
    user_manager = UserManager()

    sample_users = [
        {
            "username": "admin",
            "email": "admin@example.com",
            "password": "AdminPassword123!",
            "display_name": "System Administrator",
            "role": UserRole.ADMINISTRATOR.value,
        },
        {
            "username": "manager1",
            "email": "manager1@example.com",
            "password": "ManagerPassword123!",
            "display_name": "John Manager",
            "role": UserRole.MANAGER.value,
        },
        {
            "username": "user1",
            "email": "user1@example.com",
            "password": "UserPassword123!",
            "display_name": "Jane User",
            "role": UserRole.USER.value,
        },
        {
            "username": "testuser",
            "email": "test@example.com",
            "password": "TestPassword123!",
            "display_name": "Test User",
            "role": UserRole.USER.value,
        },
    ]

    print("Creating sample users...")
    for user_data in sample_users:
        result = user_manager.create_user(
            username=user_data["username"],
            email=user_data["email"],
            password=user_data["password"],
            display_name=user_data["display_name"],
            role=user_data["role"],
        )

        if result["success"]:
            print(f"✓ Created user: {user_data['username']} ({user_data['role']})")
        else:
            print(
                f"✗ Failed to create user {user_data['username']}: {result['message']}"
            )


def list_users():
    """List all users in the system"""
    user_manager = UserManager()
    users = user_manager.get_all_users()

    if not users:
        print("No users found in the system.")
        return

    print(f"Found {len(users)} users:")
    print("-" * 80)
    print(f"{'Username':<15} {'Email':<25} {'Role':<15} {'Status':<10} {'Created':<20}")
    print("-" * 80)

    for user in users:
        created_date = datetime.fromisoformat(user["created_at"]).strftime(
            "%Y-%m-%d %H:%M"
        )
        print(
            f"{user['username']:<15} {user['email']:<25} {user['role']:<15} {user['status']:<10} {created_date:<20}"
        )


def reset_user_password(username, new_password):
    """Reset a user's password"""
    user_manager = UserManager()

    # Check if user exists
    user = user_manager.get_user_by_username(username)
    if not user:
        print(f"User '{username}' not found.")
        return

    # Update password
    result = user_manager.update_user(user["id"], password=new_password)

    if result["success"]:
        print(f"✓ Password reset for user '{username}'")
    else:
        print(f"✗ Failed to reset password: {result['message']}")


def unlock_user_account(username):
    """Unlock a user account"""
    user_manager = UserManager()

    # Check if user exists
    user = user_manager.get_user_by_username(username)
    if not user:
        print(f"User '{username}' not found.")
        return

    # Reset failed login attempts and unlock
    users = user_manager._load_users()
    for u in users:
        if u["id"] == user["id"]:
            u["failed_login_attempts"] = 0
            u["account_locked_until"] = None
            u["status"] = UserStatus.ACTIVE.value
            break

    user_manager._save_users(users)
    print(f"✓ Account unlocked for user '{username}'")


def delete_user(username):
    """Delete a user account"""
    user_manager = UserManager()

    # Check if user exists
    user = user_manager.get_user_by_username(username)
    if not user:
        print(f"User '{username}' not found.")
        return

    # Confirm deletion
    confirm = input(f"Are you sure you want to delete user '{username}'? (yes/no): ")
    if confirm.lower() not in ["yes", "y"]:
        print("Deletion cancelled.")
        return

    result = user_manager.delete_user(user["id"])

    if result["success"]:
        print(f"✓ User '{username}' deleted successfully")
    else:
        print(f"✗ Failed to delete user: {result['message']}")


def cleanup_old_data():
    """Clean up old data and logs"""
    user_manager = UserManager()

    # Clean up old audit logs (older than 30 days)
    cutoff_date = datetime.now() - timedelta(days=30)

    users = user_manager._load_users()
    total_cleaned = 0

    for user in users:
        if "audit_log" in user:
            original_count = len(user["audit_log"])
            user["audit_log"] = [
                log
                for log in user["audit_log"]
                if datetime.fromisoformat(log["timestamp"]) > cutoff_date
            ]
            cleaned_count = original_count - len(user["audit_log"])
            total_cleaned += cleaned_count

    user_manager._save_users(users)
    print(f"✓ Cleaned up {total_cleaned} old audit log entries")

    # Clean up upload directory
    upload_dir = "uploads"
    if os.path.exists(upload_dir):
        old_files = []
        for filename in os.listdir(upload_dir):
            file_path = os.path.join(upload_dir, filename)
            if os.path.isfile(file_path):
                file_age = datetime.now() - datetime.fromtimestamp(
                    os.path.getmtime(file_path)
                )
                if file_age > timedelta(days=7):  # Files older than 7 days
                    old_files.append(file_path)

        if old_files:
            print(f"Found {len(old_files)} old files in uploads directory:")
            for file_path in old_files:
                print(f"  - {file_path}")

            confirm = input("Delete these old files? (yes/no): ")
            if confirm.lower() in ["yes", "y"]:
                for file_path in old_files:
                    try:
                        os.remove(file_path)
                        print(f"✓ Deleted {file_path}")
                    except OSError as e:
                        print(f"✗ Failed to delete {file_path}: {e}")
            else:
                print("File deletion cancelled.")
        else:
            print("No old files found in uploads directory.")


def check_system_health():
    """Check system health and configuration"""
    print("System Health Check")
    print("=" * 50)

    # Check user data file
    user_manager = UserManager()
    users = user_manager.get_all_users()
    print(f"✓ User data file accessible: {len(users)} users found")

    # Check admin user exists
    admin_users = [u for u in users if u["role"] == UserRole.ADMINISTRATOR.value]
    if admin_users:
        print(f"✓ Admin users found: {len(admin_users)}")
    else:
        print("⚠ WARNING: No admin users found!")

    # Check upload directory
    upload_dir = "uploads"
    if os.path.exists(upload_dir):
        print(f"✓ Upload directory exists: {upload_dir}")
    else:
        print(f"⚠ Upload directory missing: {upload_dir}")

    # Check configuration files
    config_files = [".env.example", "config.py", "requirements.txt"]
    for config_file in config_files:
        if os.path.exists(config_file):
            print(f"✓ Configuration file exists: {config_file}")
        else:
            print(f"⚠ Configuration file missing: {config_file}")

    # Check for locked accounts
    locked_users = [u for u in users if u.get("account_locked_until")]
    if locked_users:
        print(f"⚠ WARNING: {len(locked_users)} locked user accounts found")
        for user in locked_users:
            print(
                f"  - {user['username']} (locked until {user['account_locked_until']})"
            )
    else:
        print("✓ No locked user accounts")

    print("\nHealth check complete.")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Development utility for Flask application"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Create sample users command
    subparsers.add_parser("create-samples", help="Create sample users for development")

    # List users command
    subparsers.add_parser("list-users", help="List all users in the system")

    # Reset password command
    reset_parser = subparsers.add_parser("reset-password", help="Reset user password")
    reset_parser.add_argument("username", help="Username to reset password for")
    reset_parser.add_argument("password", help="New password")

    # Unlock account command
    unlock_parser = subparsers.add_parser("unlock-account", help="Unlock user account")
    unlock_parser.add_argument("username", help="Username to unlock")

    # Delete user command
    delete_parser = subparsers.add_parser("delete-user", help="Delete user account")
    delete_parser.add_argument("username", help="Username to delete")

    # Cleanup command
    subparsers.add_parser("cleanup", help="Clean up old data and logs")

    # Health check command
    subparsers.add_parser("health-check", help="Check system health")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "create-samples":
            create_sample_users()
        elif args.command == "list-users":
            list_users()
        elif args.command == "reset-password":
            reset_user_password(args.username, args.password)
        elif args.command == "unlock-account":
            unlock_user_account(args.username)
        elif args.command == "delete-user":
            delete_user(args.username)
        elif args.command == "cleanup":
            cleanup_old_data()
        elif args.command == "health-check":
            check_system_health()
    except Exception as e:
        print(f"Error executing command: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
