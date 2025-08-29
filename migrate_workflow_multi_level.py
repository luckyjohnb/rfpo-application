#!/usr/bin/env python3
"""
Migrate rfpo_approval_workflows table to support Team and Project workflows
"""

import sqlite3
import os
from datetime import datetime

def migrate_workflow_table():
    """Add workflow_type, team_id, and project_id columns to rfpo_approval_workflows"""
    
    # Database path
    db_path = 'instance/rfpo_admin.db'
    
    if not os.path.exists(db_path):
        print(f"❌ Database file {db_path} not found!")
        return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔍 Checking current table structure...")
        
        # Get current table schema
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='rfpo_approval_workflows'")
        current_schema = cursor.fetchone()[0]
        print("Current schema:")
        print(current_schema)
        
        # Check if new columns already exist
        cursor.execute("PRAGMA table_info(rfpo_approval_workflows)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'workflow_type' in columns:
            print("✅ Migration already completed - workflow_type column exists")
            return True
        
        print("\n🔄 Adding new columns for multi-level workflows...")
        
        # Start transaction
        cursor.execute("BEGIN TRANSACTION")
        
        # Add new columns
        cursor.execute("ALTER TABLE rfpo_approval_workflows ADD COLUMN workflow_type VARCHAR(20) DEFAULT 'consortium'")
        cursor.execute("ALTER TABLE rfpo_approval_workflows ADD COLUMN team_id INTEGER")
        cursor.execute("ALTER TABLE rfpo_approval_workflows ADD COLUMN project_id VARCHAR(32)")
        
        # Update existing records to have workflow_type = 'consortium'
        cursor.execute("UPDATE rfpo_approval_workflows SET workflow_type = 'consortium' WHERE workflow_type IS NULL")
        
        # Make consortium_id nullable for team/project workflows
        print("🔄 Recreating table with updated constraints...")
        
        # Create backup of existing data
        cursor.execute("""
            CREATE TEMPORARY TABLE rfpo_approval_workflows_backup AS 
            SELECT * FROM rfpo_approval_workflows
        """)
        
        # Drop the original table
        cursor.execute("DROP TABLE rfpo_approval_workflows")
        
        # Recreate table with updated schema
        cursor.execute("""
            CREATE TABLE rfpo_approval_workflows (
                id INTEGER NOT NULL, 
                workflow_id VARCHAR(32) NOT NULL, 
                name VARCHAR(255) NOT NULL, 
                description TEXT, 
                version VARCHAR(20), 
                workflow_type VARCHAR(20) NOT NULL DEFAULT 'consortium',
                consortium_id VARCHAR(32), 
                team_id INTEGER,
                project_id VARCHAR(32),
                is_active BOOLEAN, 
                is_template BOOLEAN, 
                created_at DATETIME, 
                updated_at DATETIME, 
                created_by VARCHAR(64), 
                updated_by VARCHAR(64), 
                PRIMARY KEY (id), 
                UNIQUE (workflow_id),
                FOREIGN KEY(team_id) REFERENCES teams (id)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX idx_consortium_type_active ON rfpo_approval_workflows (consortium_id, workflow_type, is_active)")
        cursor.execute("CREATE INDEX idx_team_type_active ON rfpo_approval_workflows (team_id, workflow_type, is_active)")
        cursor.execute("CREATE INDEX idx_project_type_active ON rfpo_approval_workflows (project_id, workflow_type, is_active)")
        
        # Restore data from backup
        cursor.execute("""
            INSERT INTO rfpo_approval_workflows 
            SELECT * FROM rfpo_approval_workflows_backup
        """)
        
        # Drop backup table
        cursor.execute("DROP TABLE rfpo_approval_workflows_backup")
        
        # Commit transaction
        cursor.execute("COMMIT")
        
        print("✅ Successfully added multi-level workflow support!")
        print("✅ All existing data preserved!")
        
        # Verify the new structure
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='rfpo_approval_workflows'")
        new_schema = cursor.fetchone()[0]
        print("\nNew schema:")
        print(new_schema)
        
        # Show indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='rfpo_approval_workflows'")
        indexes = cursor.fetchall()
        print("\nIndexes:")
        for index in indexes:
            print(f"  - {index[0]}")
        
        # Close connection
        conn.close()
        
        print(f"\n🎉 Migration completed successfully at {datetime.now()}")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        try:
            cursor.execute("ROLLBACK")
            conn.close()
        except:
            pass
        return False

if __name__ == '__main__':
    print("🚀 Migrating approval workflows for multi-level support...")
    print("This will add Team and Project workflow capabilities")
    print("=" * 70)
    
    success = migrate_workflow_table()
    
    print("=" * 70)
    if success:
        print("✅ Migration completed successfully!")
        print("You can now create Team and Project approval workflows.")
    else:
        print("❌ Migration failed!")
        print("Please check the error messages above.")
