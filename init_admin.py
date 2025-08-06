#!/usr/bin/env python3
"""
Initialize admin user for Flask application
Creates a default administrator account
"""
import os
import sys
from user_management import UserManager

def create_admin_user():
    """Create the default admin user"""
    print("🔧 Initializing Admin User...")
    print("=" * 50)
    
    try:
        # Initialize user manager
        user_manager = UserManager()
        
        # Check if admin already exists
        existing_admin = user_manager.get_user_by_username('admin')
        if existing_admin:
            print("✅ Admin user already exists!")
            print(f"   Username: admin")
            print(f"   Email: {existing_admin.get('email', 'admin@example.com')}")
            print(f"   Status: {existing_admin.get('status', 'unknown')}")
            print(f"   Roles: {', '.join(existing_admin.get('roles', []))}")
            return True
        
        # Create admin user
        print("📝 Creating admin user...")
        result = user_manager.create_user(
            username="admin",
            email="admin@example.com",
            password="Administrator123!",
            display_name="System Administrator",
            roles=["Administrator"],
            status="active"
        )
        
        if result["success"]:
            print("✅ Admin user created successfully!")
            print("=" * 50)
            print("📋 LOGIN CREDENTIALS:")
            print("   Username: admin")
            print("   Password: Administrator123!")
            print("   Email: admin@example.com")
            print("=" * 50)
            print("🌐 You can now login to the application!")
            return True
        else:
            print(f"❌ Failed to create admin user: {result['message']}")
            return False
            
    except Exception as e:
        print(f"❌ Error creating admin user: {str(e)}")
        return False

def main():
    """Main function"""
    print("🚀 Flask Application - Admin User Setup")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists('user_management.py'):
        print("❌ Error: user_management.py not found!")
        print("   Make sure you're running this from the project directory.")
        sys.exit(1)
    
    # Create config directory if it doesn't exist
    os.makedirs('config', exist_ok=True)
    
    # Create admin user
    success = create_admin_user()
    
    if success:
        print("\n🎉 Setup completed successfully!")
        print("You can now run: python app.py")
    else:
        print("\n❌ Setup failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()
