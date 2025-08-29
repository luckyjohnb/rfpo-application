#!/usr/bin/env python3
"""
Remove the unique constraint on approval_type_key per stage to allow multiple steps of the same type
"""

import sqlite3
import os
from datetime import datetime

def remove_constraint():
    """Remove the uq_stage_approval_type constraint from rfpo_approval_steps table"""
    
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
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='rfpo_approval_steps'")
        current_schema = cursor.fetchone()[0]
        print("Current schema:")
        print(current_schema)
        
        print("\n🔄 Recreating table without approval_type constraint...")
        
        # Start transaction
        cursor.execute("BEGIN TRANSACTION")
        
        # Create backup of existing data
        cursor.execute("""
            CREATE TEMPORARY TABLE rfpo_approval_steps_backup AS 
            SELECT * FROM rfpo_approval_steps
        """)
        
        # Drop the original table
        cursor.execute("DROP TABLE rfpo_approval_steps")
        
        # Recreate table without the approval_type constraint
        cursor.execute("""
            CREATE TABLE rfpo_approval_steps (
                id INTEGER NOT NULL, 
                step_id VARCHAR(32) NOT NULL, 
                step_name VARCHAR(255) NOT NULL, 
                step_order INTEGER NOT NULL, 
                description TEXT, 
                approval_type_key VARCHAR(255) NOT NULL, 
                approval_type_name VARCHAR(255) NOT NULL, 
                stage_id INTEGER NOT NULL, 
                primary_approver_id VARCHAR(32) NOT NULL, 
                backup_approver_id VARCHAR(32), 
                is_required BOOLEAN, 
                timeout_days INTEGER, 
                auto_escalate BOOLEAN, 
                created_at DATETIME, 
                updated_at DATETIME, 
                PRIMARY KEY (id), 
                UNIQUE (step_id), 
                UNIQUE (stage_id, step_order), 
                FOREIGN KEY(stage_id) REFERENCES rfpo_approval_stages (id)
            )
        """)
        
        # Restore data from backup
        cursor.execute("""
            INSERT INTO rfpo_approval_steps 
            SELECT * FROM rfpo_approval_steps_backup
        """)
        
        # Drop backup table
        cursor.execute("DROP TABLE rfpo_approval_steps_backup")
        
        # Commit transaction
        cursor.execute("COMMIT")
        
        print("✅ Successfully removed approval_type constraint!")
        print("✅ All existing data preserved!")
        
        # Verify the new structure
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='rfpo_approval_steps'")
        new_schema = cursor.fetchone()[0]
        print("\nNew schema:")
        print(new_schema)
        
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
    print("🚀 Removing approval type constraint...")
    print("This will allow multiple steps of the same approval type per stage")
    print("=" * 70)
    
    success = remove_constraint()
    
    print("=" * 70)
    if success:
        print("✅ Constraint removal completed successfully!")
        print("You can now add multiple steps of the same approval type to a stage.")
    else:
        print("❌ Constraint removal failed!")
        print("Please check the error messages above.")
