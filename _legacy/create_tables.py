#!/usr/bin/env python3
"""
Create all database tables for the RFPO application
"""

from flask import Flask
from models import db

def create_all_tables():
    """Create all database tables"""
    
    # Create Flask app with same config as custom_admin.py
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rfpo_admin.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database
    db.init_app(app)
    
    with app.app_context():
        print("🔨 Creating all database tables...")
        
        try:
            # Create all tables
            db.create_all()
            
            print("✅ All tables created successfully!")
            
            # List created tables
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            
            print(f"📋 Created {len(tables)} tables:")
            for table in sorted(tables):
                print(f"  - {table}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error creating tables: {str(e)}")
            return False

if __name__ == '__main__':
    print("🚀 Initializing RFPO database...")
    print("=" * 50)
    
    success = create_all_tables()
    
    print("=" * 50)
    if success:
        print("✅ Database initialization completed!")
        print("You can now start the application.")
    else:
        print("❌ Database initialization failed!")
