#!/usr/bin/env python3
"""
Add missing record_id and other columns to all tables
"""

import os
import sys

# Set the DATABASE_URL for Azure PostgreSQL
os.environ['DATABASE_URL'] = "postgresql://rfpoadmin:RfpoSecure123!@rfpo-db-5kn5bsg47vvac.postgres.database.azure.com:5432/rfpodb?sslmode=require"

from flask import Flask
from models import db
from sqlalchemy import text, inspect

def create_app():
    """Create Flask app with proper configuration"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app


def add_missing_columns(app):
    """Add all missing columns to tables"""
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            
            with db.engine.connect() as conn:
                # Fix teams table - add record_id
                print("\n🔍 Checking teams table...")
                teams_columns = [col['name'] for col in inspector.get_columns('teams')]
                
                if 'record_id' not in teams_columns:
                    print("  📝 Adding record_id to teams...")
                    conn.execute(text("""
                        ALTER TABLE teams 
                        ADD COLUMN record_id VARCHAR(32) UNIQUE
                    """))
                    conn.commit()
                    print("  ✅ Added record_id")
                    
                    # Update existing records with unique record_ids
                    print("  📝 Generating record_ids for existing teams...")
                    conn.execute(text("""
                        UPDATE teams 
                        SET record_id = LPAD(id::text, 8, '0')
                        WHERE record_id IS NULL
                    """))
                    conn.commit()
                    
                    # Make it NOT NULL after populating
                    conn.execute(text("""
                        ALTER TABLE teams 
                        ALTER COLUMN record_id SET NOT NULL
                    """))
                    conn.commit()
                    print("  ✅ Populated record_ids for existing teams")
                else:
                    print("  ✓ record_id exists")
                
                if 'abbrev' not in teams_columns:
                    print("  📝 Adding abbrev to teams...")
                    conn.execute(text("""
                        ALTER TABLE teams 
                        ADD COLUMN abbrev VARCHAR(20)
                    """))
                    conn.commit()
                    print("  ✅ Added abbrev")
                else:
                    print("  ✓ abbrev exists")
                
                if 'rfpo_viewer_user_ids' not in teams_columns:
                    print("  📝 Adding rfpo_viewer_user_ids to teams...")
                    conn.execute(text("""
                        ALTER TABLE teams 
                        ADD COLUMN rfpo_viewer_user_ids TEXT
                    """))
                    conn.commit()
                    print("  ✅ Added rfpo_viewer_user_ids")
                else:
                    print("  ✓ rfpo_viewer_user_ids exists")
                
                if 'rfpo_admin_user_ids' not in teams_columns:
                    print("  📝 Adding rfpo_admin_user_ids to teams...")
                    conn.execute(text("""
                        ALTER TABLE teams 
                        ADD COLUMN rfpo_admin_user_ids TEXT
                    """))
                    conn.commit()
                    print("  ✅ Added rfpo_admin_user_ids")
                else:
                    print("  ✓ rfpo_admin_user_ids exists")
                
                # Fix users table - add record_id if missing
                print("\n🔍 Checking users table...")
                users_columns = [col['name'] for col in inspector.get_columns('users')]
                
                if 'record_id' not in users_columns:
                    print("  📝 Adding record_id to users...")
                    conn.execute(text("""
                        ALTER TABLE users 
                        ADD COLUMN record_id VARCHAR(32) UNIQUE
                    """))
                    conn.commit()
                    print("  ✅ Added record_id")
                    
                    # Update existing records with unique record_ids
                    print("  📝 Generating record_ids for existing users...")
                    conn.execute(text("""
                        UPDATE users 
                        SET record_id = LPAD(id::text, 8, '0')
                        WHERE record_id IS NULL
                    """))
                    conn.commit()
                    
                    # Make it NOT NULL after populating
                    conn.execute(text("""
                        ALTER TABLE users 
                        ALTER COLUMN record_id SET NOT NULL
                    """))
                    conn.commit()
                    print("  ✅ Populated record_ids for existing users")
                else:
                    print("  ✓ record_id exists")
                
                # Fix projects table - add record_id if missing
                print("\n🔍 Checking projects table...")
                projects_columns = [col['name'] for col in inspector.get_columns('projects')]
                
                if 'record_id' not in projects_columns:
                    print("  📝 Adding record_id to projects...")
                    conn.execute(text("""
                        ALTER TABLE projects 
                        ADD COLUMN record_id VARCHAR(32) UNIQUE
                    """))
                    conn.commit()
                    print("  ✅ Added record_id")
                    
                    # Update existing records with unique record_ids
                    print("  📝 Generating record_ids for existing projects...")
                    conn.execute(text("""
                        UPDATE projects 
                        SET record_id = LPAD(id::text, 8, '0')
                        WHERE record_id IS NULL
                    """))
                    conn.commit()
                    
                    # Make it NOT NULL after populating
                    conn.execute(text("""
                        ALTER TABLE projects 
                        ALTER COLUMN record_id SET NOT NULL
                    """))
                    conn.commit()
                    print("  ✅ Populated record_ids for existing projects")
                else:
                    print("  ✓ record_id exists")
            
            print("\n✅ All missing columns added successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Error adding columns: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    print("🔧 Adding Missing Columns to Database")
    print("=" * 50)
    
    app = create_app()
    success = add_missing_columns(app)
    
    if success:
        print("\n✅ Database schema fix completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Database schema fix failed!")
        sys.exit(1)
