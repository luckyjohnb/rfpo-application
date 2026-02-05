#!/usr/bin/env python3
"""
Fix Consortium table schema by adding missing columns
"""

import os
import sys
from env_config import get_database_url

# Load DATABASE_URL from environment variables
os.environ['DATABASE_URL'] = get_database_url()

from flask import Flask
from models import db
from sqlalchemy import text

def create_app():
    """Create Flask app with proper configuration"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app


def fix_consortium_schema(app):
    """Add missing columns to consortiums table"""
    with app.app_context():
        try:
            # Check if created_by column exists
            with db.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'consortiums' 
                    AND column_name = 'created_by'
                """))
                
                if result.fetchone() is None:
                    print("📝 Adding created_by column to consortiums table...")
                    conn.execute(text("""
                        ALTER TABLE consortiums 
                        ADD COLUMN created_by VARCHAR(64)
                    """))
                    conn.commit()
                    print("✅ Added created_by column")
                else:
                    print("✓ created_by column already exists")
                
                # Check if updated_by column exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'consortiums' 
                    AND column_name = 'updated_by'
                """))
                
                if result.fetchone() is None:
                    print("📝 Adding updated_by column to consortiums table...")
                    conn.execute(text("""
                        ALTER TABLE consortiums 
                        ADD COLUMN updated_by VARCHAR(64)
                    """))
                    conn.commit()
                    print("✅ Added updated_by column")
                else:
                    print("✓ updated_by column already exists")
            
            print("\n✅ Consortium table schema fixed!")
            return True
            
        except Exception as e:
            print(f"❌ Error fixing schema: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    print("🔧 Fixing Consortium Table Schema")
    print("=" * 50)
    
    app = create_app()
    success = fix_consortium_schema(app)
    
    if success:
        print("\n✅ Schema fix completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Schema fix failed!")
        sys.exit(1)
