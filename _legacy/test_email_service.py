#!/usr/bin/env python3
"""
Test script for email service functionality
Run this to verify email configuration and template rendering
"""
import os
import sys
from email_service import EmailService, test_email_connection, send_welcome_email

def load_env_file(env_file='.env'):
    """Load environment variables from .env file"""
    if os.path.exists(env_file):
        print(f"📁 Loading environment variables from {env_file}")
        with open(env_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    try:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Remove quotes if present
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        
                        # Set environment variable if not already set
                        if key not in os.environ:
                            os.environ[key] = value
                            
                    except ValueError:
                        print(f"⚠️  Warning: Malformed line {line_num} in {env_file}: {line}")
        print("✅ Environment variables loaded")
    else:
        print(f"❌ .env file not found: {env_file}")

# Load .env file at startup
load_env_file()

def test_email_configuration():
    """Test email configuration and connection"""
    print("=" * 60)
    print("RFPO Email Service Test")
    print("=" * 60)
    
    # Check environment variables
    print("\n1. Checking Email Configuration:")
    print("-" * 40)
    
    config_items = [
        ('MAIL_SERVER', os.environ.get('MAIL_SERVER')),
        ('MAIL_PORT', os.environ.get('MAIL_PORT')),
        ('MAIL_USE_TLS', os.environ.get('MAIL_USE_TLS')),
        ('MAIL_USERNAME', os.environ.get('MAIL_USERNAME')),
        ('MAIL_PASSWORD', '***' if os.environ.get('MAIL_PASSWORD') else None),
        ('MAIL_DEFAULT_SENDER', os.environ.get('MAIL_DEFAULT_SENDER')),
    ]
    
    all_configured = True
    for key, value in config_items:
        status = "✅" if value else "❌"
        print(f"{status} {key}: {value or 'Not configured'}")
        if not value and key in ['MAIL_SERVER', 'MAIL_USERNAME', 'MAIL_PASSWORD']:
            all_configured = False
    
    if not all_configured:
        print("\n❌ Email service is not fully configured.")
        print("Please set the required environment variables:")
        print("  - MAIL_SERVER (e.g., smtp.gmail.com)")
        print("  - MAIL_USERNAME (your email address)")
        print("  - MAIL_PASSWORD (your email password or app password)")
        return False
    
    print("\n✅ Email configuration appears complete.")
    
    # Test connection
    print("\n2. Testing SMTP Connection:")
    print("-" * 40)
    
    try:
        if test_email_connection():
            print("✅ SMTP connection successful!")
        else:
            print("❌ SMTP connection failed!")
            return False
    except Exception as e:
        print(f"❌ SMTP connection error: {str(e)}")
        return False
    
    return True

def test_template_rendering():
    """Test email template rendering"""
    print("\n3. Testing Email Template Rendering:")
    print("-" * 40)
    
    try:
        email_service = EmailService()
        
        # Test welcome template
        template_data = {
            'user_name': 'John Doe',
            'user_email': 'john.doe@example.com',
            'temp_password': 'TempPass123',
            'login_url': 'http://localhost:5000/login',
            'support_email': 'support@rfpo.com'
        }
        
        template = email_service.jinja_env.get_template('welcome.html')
        rendered_html = template.render(**template_data)
        
        if 'John Doe' in rendered_html and 'TempPass123' in rendered_html:
            print("✅ Welcome template rendering successful!")
        else:
            print("❌ Welcome template rendering failed!")
            return False
            
    except Exception as e:
        print(f"❌ Template rendering error: {str(e)}")
        return False
    
    return True

def test_send_email():
    """Test sending actual email (optional)"""
    print("\n4. Email Sending Test:")
    print("-" * 40)
    
    test_email = input("Enter test email address (or press Enter to skip): ").strip()
    
    if not test_email:
        print("⏭️  Email sending test skipped.")
        return True
    
    print(f"Sending test welcome email to: {test_email}")
    
    try:
        success = send_welcome_email(
            user_email=test_email,
            user_name="Test User",
            temp_password="TestPassword123"
        )
        
        if success:
            print("✅ Test email sent successfully!")
            print(f"Check your inbox at {test_email}")
        else:
            print("❌ Test email sending failed!")
            return False
            
    except Exception as e:
        print(f"❌ Email sending error: {str(e)}")
        return False
    
    return True

def main():
    """Main test function"""
    try:
        # Test configuration
        if not test_email_configuration():
            return False
        
        # Test template rendering
        if not test_template_rendering():
            return False
        
        # Test email sending (optional)
        if not test_send_email():
            return False
        
        print("\n" + "=" * 60)
        print("🎉 All email service tests passed!")
        print("=" * 60)
        print("\nYour email service is ready to use.")
        print("Welcome emails will be sent automatically when users are created in the admin panel.")
        
        return True
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user.")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
