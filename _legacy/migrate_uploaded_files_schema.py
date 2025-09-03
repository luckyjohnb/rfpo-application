#!/usr/bin/env python3
"""
Database Migration Script: Add document_type and description columns to uploaded_files table

This script adds the missing columns that were added to the UploadedFile model:
- document_type (VARCHAR(255)) - Document type classification
- description (TEXT) - Optional file description

Usage: python3 migrate_uploaded_files_schema.py
"""

import sqlite3
import os
from datetime import datetime

def migrate_database(db_path):
    """Add missing columns to uploaded_files table"""
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if uploaded_files table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='uploaded_files'")
        if not cursor.fetchone():
            print(f"❌ No uploaded_files table found in {db_path}")
            conn.close()
            return False
        
        # Get current columns
        cursor.execute('PRAGMA table_info(uploaded_files)')
        columns = [col[1] for col in cursor.fetchall()]
        
        migrations_applied = []
        
        # Add document_type column if missing
        if 'document_type' not in columns:
            cursor.execute('ALTER TABLE uploaded_files ADD COLUMN document_type VARCHAR(255)')
            migrations_applied.append('document_type')
        
        # Add description column if missing
        if 'description' not in columns:
            cursor.execute('ALTER TABLE uploaded_files ADD COLUMN description TEXT')
            migrations_applied.append('description')
        
        if migrations_applied:
            conn.commit()
            print(f"✅ Applied migrations to {db_path}: {', '.join(migrations_applied)}")
        else:
            print(f"ℹ️  No migrations needed for {db_path}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error migrating {db_path}: {e}")
        return False

def main():
    """Run migration on all database files"""
    print(f"🚀 Starting database migration at {datetime.now()}")
    print("=" * 60)
    
    # List of potential database files
    db_files = [
        './instance/rfpo_admin.db',
        './instance/app.db', 
        './rfpo_admin.db'
    ]
    
    success_count = 0
    for db_file in db_files:
        print(f"\n📁 Processing {db_file}...")
        if migrate_database(db_file):
            success_count += 1
    
    print("\n" + "=" * 60)
    print(f"✅ Migration completed! {success_count} databases processed successfully.")
    print("\nThe following columns were added to uploaded_files table:")
    print("  - document_type (VARCHAR(255)) - Document type classification")
    print("  - description (TEXT) - Optional file description")

if __name__ == '__main__':
    main()
