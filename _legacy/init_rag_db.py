#!/usr/bin/env python3
"""
Initialize RAG database tables
Run this script to create the new RFPO, UploadedFile, and DocumentChunk tables
"""
import os
import sys
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Team, RFPO, UploadedFile, DocumentChunk

def init_rag_database():
    """Initialize the RAG database with new tables"""
    
    print("🚀 Initializing RAG Database...")
    
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            print("✅ Database tables created successfully")
            
            # Check if we have any teams (required for RFPOs)
            team_count = Team.query.count()
            if team_count == 0:
                print("⚠️  No teams found. Creating default team...")
                
                # Create a default team
                default_team = Team(
                    name="Default Team",
                    description="Default team for RFPO management",
                    abbrev="DEFAULT",
                    consortium_id=1,
                    active=True,
                    created_by="system",
                    updated_by="system"
                )
                
                db.session.add(default_team)
                db.session.commit()
                print(f"✅ Created default team with ID: {default_team.id}")
            else:
                print(f"✅ Found {team_count} existing teams")
            
            # Check existing RFPOs
            rfpo_count = RFPO.query.count()
            print(f"📋 Current RFPO count: {rfpo_count}")
            
            if rfpo_count == 0:
                print("💡 Consider creating some sample RFPOs using the web interface or API")
            
            # Check uploaded files
            file_count = UploadedFile.query.count()
            chunk_count = DocumentChunk.query.count()
            
            print(f"📁 Current uploaded files: {file_count}")
            print(f"🧩 Current document chunks: {chunk_count}")
            
            print("\n🎉 RAG Database initialization completed successfully!")
            print("\n📖 Next steps:")
            print("1. Install required dependencies: pip install -r requirements.txt")
            print("2. Create RFPOs using the web interface or API")
            print("3. Upload files to RFPOs for RAG processing")
            print("4. Test the RAG search functionality")
            
            return True
            
        except Exception as e:
            print(f"❌ Error initializing database: {str(e)}")
            return False

def show_database_info():
    """Show current database information"""
    
    print("\n📊 Database Information:")
    print("=" * 50)
    
    with app.app_context():
        try:
            # Teams
            teams = Team.query.all()
            print(f"Teams ({len(teams)}):")
            for team in teams:
                print(f"  - {team.name} ({team.abbrev}) - ID: {team.id}")
            
            # RFPOs
            rfpos = RFPO.query.all()
            print(f"\nRFPOs ({len(rfpos)}):")
            for rfpo in rfpos:
                print(f"  - {rfpo.rfpo_id}: {rfpo.title} (Team: {rfpo.team_id}, Status: {rfpo.status})")
            
            # Files
            files = UploadedFile.query.all()
            print(f"\nUploaded Files ({len(files)}):")
            for file in files[:10]:  # Show first 10
                print(f"  - {file.original_filename} (RFPO: {file.rfpo_id}, Status: {file.processing_status})")
            
            if len(files) > 10:
                print(f"  ... and {len(files) - 10} more files")
            
            # Chunks
            chunk_count = DocumentChunk.query.count()
            print(f"\nDocument Chunks: {chunk_count}")
            
        except Exception as e:
            print(f"Error getting database info: {str(e)}")

def create_sample_rfpo():
    """Create a sample RFPO for testing"""
    
    with app.app_context():
        try:
            # Get first team
            team = Team.query.first()
            if not team:
                print("❌ No teams available. Create a team first.")
                return False
            
            # Check if sample RFPO already exists
            existing = RFPO.query.filter_by(rfpo_id="RFPO-SAMPLE").first()
            if existing:
                print("⚠️  Sample RFPO already exists")
                return True
            
            # Create sample RFPO
            sample_rfpo = RFPO(
                rfpo_id="RFPO-SAMPLE",
                title="Sample RFPO for Testing",
                description="This is a sample RFPO created for testing the RAG functionality",
                vendor="Sample Vendor Corp",
                status="Draft",
                team_id=team.id,
                created_by="system"
            )
            
            db.session.add(sample_rfpo)
            db.session.commit()
            
            print(f"✅ Created sample RFPO: {sample_rfpo.rfpo_id} (ID: {sample_rfpo.id})")
            return True
            
        except Exception as e:
            print(f"❌ Error creating sample RFPO: {str(e)}")
            return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Initialize RAG Database")
    parser.add_argument("--info", action="store_true", help="Show database information")
    parser.add_argument("--sample", action="store_true", help="Create sample RFPO")
    parser.add_argument("--init", action="store_true", help="Initialize database tables")
    
    args = parser.parse_args()
    
    if args.info:
        show_database_info()
    elif args.sample:
        create_sample_rfpo()
    elif args.init or len(sys.argv) == 1:
        # Default action is to initialize
        success = init_rag_database()
        if success and len(sys.argv) == 1:
            # If run without arguments, also show info
            show_database_info()
    else:
        parser.print_help()
