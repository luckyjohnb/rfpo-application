#!/usr/bin/env python3
"""
SQLAlchemy Database Initializer for Azure PostgreSQL
This script uses SQLAlchemy models to create tables properly
"""

import os
import sys
from werkzeug.security import generate_password_hash
from datetime import datetime
from env_config import get_database_url, validate_configuration

# Load DATABASE_URL from environment variables
os.environ['DATABASE_URL'] = get_database_url()

# Import Flask and SQLAlchemy models
from flask import Flask
from models import (
    db, User, Consortium, RFPO, RFPOLineItem, UploadedFile, DocumentChunk,
    Team, UserTeam, Project, Vendor, VendorSite, PDFPositioning, List,
    RFPOApprovalWorkflow, RFPOApprovalStage, RFPOApprovalStep,
    RFPOApprovalInstance, RFPOApprovalAction
)


def create_app():
    """Create Flask app with proper configuration"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    return app


def create_admin_user(app, force_recreate=False):
    """Create the admin user with proper SQLAlchemy model"""
    with app.app_context():
        # Check if admin user already exists
        existing_admin = User.query.filter_by(email='admin@rfpo.com').first()
        if existing_admin:
            if force_recreate:
                print("🔄 Deleting existing admin user to recreate with correct password hash...")
                db.session.delete(existing_admin)
                db.session.commit()
            else:
                print("👤 Admin user already exists")
                return existing_admin
        
        # Hash the password using Werkzeug (same as custom_admin.py)
        password = "admin123"
        password_hash = generate_password_hash(password)
        
        # Create admin user
        admin_user = User(
            record_id='ADM00000001',
            fullname='System Administrator',
            email='admin@rfpo.com',
            password_hash=password_hash,
            permissions='["GOD"]',
            global_admin=True,
            active=True,
            use_rfpo=True,
            agreed_to_terms=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.session.add(admin_user)
        db.session.commit()
        
        print("✅ Admin user created successfully")
        return admin_user


def test_database_connection(app):
    """Test database connection before initialization"""
    try:
        with app.app_context():
            # Test connection by running a simple query (SQLAlchemy 2.x compatible)
            from sqlalchemy import text
            with db.engine.connect() as conn:
                result = conn.execute(text('SELECT 1'))
                result.close()
            print("✅ Database connection successful")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def verify_tables_created(app):
    """Verify that all expected tables were created"""
    expected_tables = [
        'consortiums', 'rfpos', 'rfpo_line_items', 'uploaded_files', 
        'document_chunks', 'teams', 'users', 'user_teams', 'projects',
        'vendors', 'vendor_sites', 'pdf_positioning', 'lists',
        'rfpo_approval_workflows', 'rfpo_approval_stages', 
        'rfpo_approval_steps', 'rfpo_approval_instances', 
        'rfpo_approval_actions'
    ]
    
    try:
        with app.app_context():
            # Get list of existing tables
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            missing_tables = []
            for table in expected_tables:
                if table not in existing_tables:
                    missing_tables.append(table)
            
            if missing_tables:
                print(f"⚠️  Missing tables: {', '.join(missing_tables)}")
                return False
            else:
                print(f"✅ All {len(expected_tables)} expected tables created successfully")
                print(f"📋 Tables: {', '.join(sorted(existing_tables))}")
                return True
                
    except Exception as e:
        print(f"❌ Table verification failed: {e}")
        return False


def initialize_reference_data(app):
    """Initialize essential reference data"""
    with app.app_context():
        print("📋 Initializing reference data...")
        
        # Admin levels
        admin_levels = [
            ('GOD', 'Super Admin'),
            ('RFPO_ADMIN', 'RFPO Administrator'),
            ('RFPO_USER', 'RFPO User'),
            ('CAL_MEET_USER', 'Calendar Meeting User'),
            ('VROOM_ADMIN', 'Virtual Room Admin'),
            ('VROOM_USER', 'Virtual Room User')
        ]
        
        # Company codes
        company_codes = [
            ('BP', 'BP'),
            ('CHEV', 'Chevron'),
            ('DOE', 'Department of Energy'),
            ('EM', 'ExxonMobil'),
            ('FCA', 'FCA US LLC'),
            ('FRD', 'Ford Motor Company'),
            ('GM', 'General Motors'),
            ('Lab', 'Laboratory'),
            ('P66', 'Phillips 66'),
            ('SHL', 'Shell'),
            ('USC', 'University of Southern California'),
            ('xxx', 'Other')
        ]
        
        # Document types
        document_types = [
            ('quote', 'Quote/Estimate'),
            ('spec', 'Technical Specification'),
            ('drawing', 'Drawing/Blueprint'),
            ('manual', 'Manual/Documentation'),
            ('contract', 'Contract/Agreement'),
            ('invoice', 'Invoice'),
            ('receipt', 'Receipt'),
            ('warranty', 'Warranty Information'),
            ('certificate', 'Certificate'),
            ('other', 'Other Document')
        ]
        
        # RFPO Status values
        rfpo_status = [
            ('draft', 'Draft'),
            ('submitted', 'Submitted for Approval'),
            ('pending', 'Pending Approval'),
            ('approved', 'Approved'),
            ('conditional', 'Conditionally Approved'),
            ('refused', 'Refused'),
            ('cancelled', 'Cancelled'),
            ('completed', 'Completed')
        ]
        
        # RFPO Budget Brackets
        budget_brackets = [
            ('under_1k', 'Under $1,000'),
            ('1k_5k', '$1,000 - $5,000'),
            ('5k_25k', '$5,000 - $25,000'),
            ('25k_100k', '$25,000 - $100,000'),
            ('over_100k', 'Over $100,000')
        ]
        
        # RFPO Approval Types
        approval_types = [
            ('technical', 'Technical Review'),
            ('financial', 'Financial Review'),
            ('manager', 'Manager Approval'),
            ('director', 'Director Approval'),
            ('legal', 'Legal Review'),
            ('procurement', 'Procurement Review')
        ]
        
        # Initialize all reference data
        reference_data_sets = [
            ('adminlevel', admin_levels),
            ('company_code', company_codes),
            ('doc_types', document_types),
            ('RFPO_STATU', rfpo_status),
            ('RFPO_BRACK', budget_brackets),
            ('RFPO_APPRO', approval_types)
        ]
        
        created_count = 0
        for list_type, items in reference_data_sets:
            for key, value in items:
                # Check if item already exists
                existing_item = List.query.filter_by(
                    type=list_type, key=key
                ).first()
                
                if not existing_item:
                    # Generate a list_id
                    list_id = f"{created_count:010d}"
                    
                    new_item = List(
                        list_id=list_id,
                        type=list_type,
                        key=key,
                        value=value,
                        active=True,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.session.add(new_item)
                    created_count += 1
        
        if created_count > 0:
            db.session.commit()
            print(f"✅ Created {created_count} reference data items")
        else:
            print("✅ Reference data already exists")


def initialize_database():
    """Initialize PostgreSQL database with SQLAlchemy models"""
    try:
        print("🔌 Creating Flask app...")
        app = create_app()
        
        print("🔍 Testing database connection...")
        if not test_database_connection(app):
            return False
        
        print("🔧 Creating database tables...")
        with app.app_context():
            # Create all tables
            db.create_all()
            print("✅ Database tables creation command executed")
            
            # Verify tables were created
            if not verify_tables_created(app):
                print("❌ Table verification failed")
                return False
            
            # Create admin user (force recreate to fix password hash)
            create_admin_user(app, force_recreate=True)
            
            # Initialize reference data
            initialize_reference_data(app)
            
            print("✅ Database initialization completed successfully!")
            print("\n🎉 RFPO Database Ready!")
            print("📧 Admin Login: admin@rfpo.com")
            print("🔐 Admin Password: admin123")
            
            return True
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🚀 Starting SQLAlchemy Database Initialization")
    print("=" * 50)
    
    success = initialize_database()
    
    if success:
        print("\n✅ Database initialization completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Database initialization failed!")
        sys.exit(1)