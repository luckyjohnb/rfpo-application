#!/usr/bin/env python3
"""
Database migration to add required_document_types column to rfpo_approval_stages table
"""

import sqlite3
import os
from datetime import datetime

def migrate_database():
    """Add required_document_types column to rfpo_approval_stages table"""
    
    # Database path
    db_path = 'rfpo_admin.db'
    
    if not os.path.exists(db_path):
        print(f"❌ Database file {db_path} not found!")
        print("Make sure you're running this from the correct directory.")
        return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔍 Checking current table structure...")
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(rfpo_approval_stages)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'required_document_types' in column_names:
            print("✅ Column 'required_document_types' already exists!")
            conn.close()
            return True
        
        print("📋 Current columns:", column_names)
        
        # Add the new column
        print("➕ Adding required_document_types column...")
        cursor.execute("""
            ALTER TABLE rfpo_approval_stages 
            ADD COLUMN required_document_types TEXT
        """)
        
        # Commit the changes
        conn.commit()
        
        # Verify the column was added
        cursor.execute("PRAGMA table_info(rfpo_approval_stages)")
        columns = cursor.fetchall()
        new_column_names = [col[1] for col in columns]
        
        if 'required_document_types' in new_column_names:
            print("✅ Successfully added required_document_types column!")
            print("📋 Updated columns:", new_column_names)
        else:
            print("❌ Failed to add column!")
            return False
        
        # Close connection
        conn.close()
        
        print(f"🎉 Migration completed successfully at {datetime.now()}")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == '__main__':
    print("🚀 Starting database migration...")
    print("Adding required_document_types column to rfpo_approval_stages table")
    print("=" * 60)
    
    success = migrate_database()
    
    if success:
        print("=" * 60)
        print("✅ Migration completed successfully!")
        print("You can now restart your application.")
    else:
        print("=" * 60)
        print("❌ Migration failed!")
        print("Please check the error messages above.")
