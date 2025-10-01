#!/usr/bin/env python3
"""
Fix Database Schema
Adds missing columns to match SQLAlchemy models
"""

import os
import sys
import psycopg2
import psycopg2.extras

# Database connection string
DATABASE_URL = "postgresql://rfpoadmin:RfpoSecure123!@rfpo-db-5kn5bsg47vvac.postgres.database.azure.com:5432/rfpodb?sslmode=require"

def fix_database_schema():
    """Add missing columns to existing tables"""
    try:
        print("� Connecting to PostgreSQL...")
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        print("✅ Connected to PostgreSQL database")
        
        # Fix Consortiums table - add missing columns
        print("🔧 Adding missing columns to consortiums table...")
        try:
            cursor.execute("ALTER TABLE consortiums ADD COLUMN IF NOT EXISTS created_by VARCHAR(64)")
            cursor.execute("ALTER TABLE consortiums ADD COLUMN IF NOT EXISTS updated_by VARCHAR(64)")
            print("✅ Consortiums table updated")
        except Exception as e:
            print(f"⚠️ Consortiums table update: {e}")
        
        # Fix Teams table - add missing columns
        print("🔧 Adding missing columns to teams table...")
        try:
            cursor.execute("ALTER TABLE teams ADD COLUMN IF NOT EXISTS created_by VARCHAR(64)")
            cursor.execute("ALTER TABLE teams ADD COLUMN IF NOT EXISTS updated_by VARCHAR(64)")
            print("✅ Teams table updated")
        except Exception as e:
            print(f"⚠️ Teams table update: {e}")
        
        # Fix Projects table - add missing columns
        print("� Adding missing columns to projects table...")
        try:
            cursor.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS created_by VARCHAR(64)")
            cursor.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS updated_by VARCHAR(64)")
            print("✅ Projects table updated")
        except Exception as e:
            print(f"⚠️ Projects table update: {e}")
        
        # Create other essential tables that might be missing
        print("🔧 Creating additional tables...")
        
        # Uploaded Files table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id SERIAL PRIMARY KEY,
                file_id VARCHAR(32) UNIQUE NOT NULL,
                original_filename VARCHAR(255) NOT NULL,
                stored_filename VARCHAR(255) NOT NULL,
                file_path VARCHAR(500) NOT NULL,
                file_size INTEGER,
                mime_type VARCHAR(100),
                uploaded_by_user_id INTEGER,
                    processing_error TEXT,
                    rfpo_id INTEGER,
                    uploaded_by INTEGER,
                    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    processed_at DATETIME,
                    FOREIGN KEY (rfpo_id) REFERENCES rfpos(id),
                    FOREIGN KEY (uploaded_by) REFERENCES users(id)
                )
            """)
            print("✅ Created uploaded_files table")
        else:
            print("✅ uploaded_files table exists")
            
            # Check for missing columns
            cursor.execute("PRAGMA table_info(uploaded_files)")
            columns = [row[1] for row in cursor.fetchall()]
            
            required_columns = [
                ('document_type', 'VARCHAR(255)'),
                ('description', 'TEXT'),
                ('processing_status', 'VARCHAR(50) DEFAULT "pending"'),
                ('text_extracted', 'TEXT'),
                ('embeddings_created', 'BOOLEAN DEFAULT 0'),
                ('chunk_count', 'INTEGER DEFAULT 0'),
                ('processing_error', 'TEXT')
            ]
            
            for col_name, col_type in required_columns:
                if col_name not in columns:
                    print(f"📝 Adding missing column: {col_name}")
                    cursor.execute(f"ALTER TABLE uploaded_files ADD COLUMN {col_name} {col_type}")
                    print(f"✅ Added column: {col_name}")
        
        # Check if rfpo_approval_stages table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='rfpo_approval_stages'
        """)
        
        if not cursor.fetchone():
            print("📝 Creating rfpo_approval_stages table...")
            cursor.execute("""
                CREATE TABLE rfpo_approval_stages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rfpo_id INTEGER NOT NULL,
                    stage_number INTEGER NOT NULL,
                    stage_name VARCHAR(255) NOT NULL,
                    approver_id INTEGER,
                    status VARCHAR(50) DEFAULT 'pending',
                    required_document_types TEXT,
                    comments TEXT,
                    approved_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (rfpo_id) REFERENCES rfpos(id),
                    FOREIGN KEY (approver_id) REFERENCES users(id)
                )
            """)
            print("✅ Created rfpo_approval_stages table")
        else:
            print("✅ rfpo_approval_stages table exists")
            
            # Check for required_document_types column
            cursor.execute("PRAGMA table_info(rfpo_approval_stages)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'required_document_types' not in columns:
                print("📝 Adding required_document_types column...")
                cursor.execute("ALTER TABLE rfpo_approval_stages ADD COLUMN required_document_types TEXT")
                print("✅ Added required_document_types column")
        
        conn.commit()
        conn.close()
        
        print("✅ Database schema fixed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing database schema: {str(e)}")
        return False

def main():
    """Main function"""
    print("🚀 RFPO Admin Panel - Database Schema Fix")
    print("=" * 60)
    
    if fix_database_schema():
        print("\n🎉 Schema fix completed successfully!")
        print("💡 You can now try logging into the admin panel again.")
        print("🌐 Admin Panel: http://localhost:5111")
        print("🔐 Login: admin@rfpo.com / admin123")
    else:
        print("\n❌ Schema fix failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()