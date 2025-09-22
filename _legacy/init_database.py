#!/usr/bin/env python3
"""
Initialize the database by importing and running the custom admin app
"""

def init_db():
    """Initialize database using the existing app structure"""
    try:
        # Import the custom admin app
        from custom_admin import create_app
        
        print("🚀 Creating Flask app...")
        app = create_app()
        
        with app.app_context():
            from models import db
            
            print("🔨 Creating all database tables...")
            db.create_all()
            
            print("✅ Database tables created successfully!")
            
            # Verify tables were created
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            
            print(f"📋 Created {len(tables)} tables:")
            for table in sorted(tables):
                print(f"  - {table}")
            
            # Check for our specific table and column
            if 'rfpo_approval_stages' in tables:
                print("✅ rfpo_approval_stages table created!")
                
                # Check the table structure
                columns = inspector.get_columns('rfpo_approval_stages')
                column_names = [col['name'] for col in columns]
                
                if 'required_document_types' in column_names:
                    print("✅ required_document_types column is present!")
                else:
                    print("❌ required_document_types column is missing!")
                    print("Available columns:", column_names)
            
            return True
            
    except Exception as e:
        print(f"❌ Error initializing database: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("🚀 Initializing RFPO Admin Database...")
    print("=" * 60)
    
    success = init_db()
    
    print("=" * 60)
    if success:
        print("✅ Database initialization completed!")
        print("The application should now work properly.")
    else:
        print("❌ Database initialization failed!")
