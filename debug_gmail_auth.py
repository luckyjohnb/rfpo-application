#!/usr/bin/env python3
"""
Debug script for Gmail authentication issues
"""
import os
import smtplib
from email.mime.text import MIMEText

def load_env_file(env_file='.env'):
    """Load environment variables from .env file"""
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    if key not in os.environ:
                        os.environ[key] = value

def debug_gmail_setup():
    """Debug Gmail authentication setup"""
    print("=" * 60)
    print("Gmail Authentication Debug")
    print("=" * 60)
    
    load_env_file()
    
    username = os.environ.get('MAIL_USERNAME')
    password = os.environ.get('MAIL_PASSWORD')
    
    print(f"\n📧 Gmail Account: {username}")
    print(f"🔐 App Password Length: {len(password) if password else 0} characters")
    print(f"🔐 App Password Format Check: {'✅ Correct (16 chars)' if password and len(password) == 16 else '❌ Should be 16 characters'}")
    
    if password:
        # Check for common formatting issues
        has_spaces = ' ' in password
        has_dashes = '-' in password
        is_alphanumeric = password.replace(' ', '').replace('-', '').isalnum()
        
        print(f"🔍 Contains spaces: {'❌ Remove spaces' if has_spaces else '✅ No spaces'}")
        print(f"🔍 Contains dashes: {'⚠️  Remove dashes' if has_dashes else '✅ No dashes'}")
        print(f"🔍 Alphanumeric only: {'✅ Good' if is_alphanumeric else '❌ Should be letters and numbers only'}")
    
    print(f"\n🔗 Troubleshooting Steps:")
    print(f"1. Verify 2-Factor Authentication is enabled on your Google account")
    print(f"2. Generate a new App Password:")
    print(f"   - Go to: https://myaccount.google.com/apppasswords")
    print(f"   - Select 'Mail' as the app")
    print(f"   - Copy the 16-character password (remove spaces)")
    print(f"3. Update MAIL_PASSWORD in your .env file")
    print(f"4. The app password should look like: abcdabcdabcdabcd (16 characters)")
    
    # Test basic SMTP connection
    print(f"\n🔌 Testing SMTP Connection...")
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        print("✅ SMTP server connection successful")
        
        # Test authentication
        print("🔐 Testing authentication...")
        server.login(username, password)
        print("✅ Gmail authentication successful!")
        server.quit()
        
        print(f"\n🎉 Gmail setup is working correctly!")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentication failed: {e}")
        print(f"\n🔧 Solutions:")
        print(f"   - Generate a new App Password")
        print(f"   - Ensure 2FA is enabled")
        print(f"   - Double-check the username and password")
        return False
        
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

if __name__ == '__main__':
    debug_gmail_setup()
