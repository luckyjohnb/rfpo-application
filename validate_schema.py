#!/usr/bin/env python3
"""
Non-Destructive Database Schema Validator
Checks all SQLAlchemy models against actual PostgreSQL schema WITHOUT dropping data
"""

import os
import sys
from env_config import get_database_url

# Load DATABASE_URL from environment variables
os.environ['DATABASE_URL'] = get_database_url()

from flask import Flask
from models import (
    db, User, Consortium, RFPO, RFPOLineItem, UploadedFile, DocumentChunk,
    Team, UserTeam, Project, Vendor, VendorSite, PDFPositioning, List,
    RFPOApprovalWorkflow, RFPOApprovalStage, RFPOApprovalStep,
    RFPOApprovalInstance, RFPOApprovalAction
)
from sqlalchemy import inspect, text


def create_app():
    """Create Flask app with proper configuration"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app


def get_model_columns(model):
    """Extract column definitions from SQLAlchemy model"""
    columns = {}
    mapper = inspect(model)
    
    for column in mapper.columns:
        col_info = {
            'type': str(column.type),
            'nullable': column.nullable,
            'primary_key': column.primary_key,
        }
        columns[column.name] = col_info
    
    return columns


def validate_all_schemas(app):
    """Validate all models against database schema"""
    
    models_to_check = [
        (User, 'users'),
        (Consortium, 'consortiums'),
        (RFPO, 'rfpos'),
        (RFPOLineItem, 'rfpo_line_items'),
        (UploadedFile, 'uploaded_files'),
        (DocumentChunk, 'document_chunks'),
        (Team, 'teams'),
        (UserTeam, 'user_teams'),
        (Project, 'projects'),
        (Vendor, 'vendors'),
        (VendorSite, 'vendor_sites'),
        (PDFPositioning, 'pdf_positioning'),
        (List, 'lists'),
        (RFPOApprovalWorkflow, 'rfpo_approval_workflows'),
        (RFPOApprovalStage, 'rfpo_approval_stages'),
        (RFPOApprovalStep, 'rfpo_approval_steps'),
        (RFPOApprovalInstance, 'rfpo_approval_instances'),
        (RFPOApprovalAction, 'rfpo_approval_actions'),
    ]
    
    print("\n🔍 COMPREHENSIVE SCHEMA VALIDATION (NON-DESTRUCTIVE)")
    print("=" * 80)
    
    with app.app_context():
        inspector = inspect(db.engine)
        db_tables = inspector.get_table_names()
        
        all_missing = {}
        tables_ok = 0
        
        for model, table_name in models_to_check:
            print(f"\n📋 {table_name:30} ", end='')
            
            if table_name not in db_tables:
                print(f"❌ TABLE MISSING!")
                all_missing[table_name] = ['ENTIRE TABLE MISSING']
                continue
            
            model_columns = get_model_columns(model)
            db_columns = {col['name']: col for col in inspector.get_columns(table_name)}
            
            missing_cols = []
            for col_name in model_columns:
                if col_name not in db_columns:
                    missing_cols.append(col_name)
            
            if missing_cols:
                print(f"⚠️  Missing {len(missing_cols)} column(s)")
                all_missing[table_name] = missing_cols
            else:
                print(f"✅ OK ({len(model_columns)} columns)")
                tables_ok += 1
    
    print("\n" + "=" * 80)
    print(f"\n📊 SUMMARY:")
    print(f"  ✅ Tables OK: {tables_ok}/{len(models_to_check)}")
    print(f"  ⚠️  Tables with issues: {len(all_missing)}")
    
    if all_missing:
        print(f"\n⚠️  MISSING COLUMNS DETECTED:")
        for table, cols in all_missing.items():
            print(f"\n  📋 {table}:")
            for col in cols:
                print(f"     • {col}")
        return all_missing
    else:
        print(f"\n✅ ALL SCHEMAS MATCH PERFECTLY!")
        return {}


def fix_missing_columns(app, missing_columns):
    """Add missing columns without dropping data"""
    print("\n\n🔧 FIXING MISSING COLUMNS (NO DATA LOSS)")
    print("=" * 80)
    
    models_map = {
        'users': User,
        'consortiums': Consortium,
        'teams': Team,
        'projects': Project,
        'vendors': Vendor,
        'vendor_sites': VendorSite,
        'rfpos': RFPO,
        'rfpo_line_items': RFPOLineItem,
        'uploaded_files': UploadedFile,
        'document_chunks': DocumentChunk,
        'user_teams': UserTeam,
        'lists': List,
        'pdf_positioning': PDFPositioning,
        'rfpo_approval_workflows': RFPOApprovalWorkflow,
        'rfpo_approval_stages': RFPOApprovalStage,
        'rfpo_approval_steps': RFPOApprovalStep,
        'rfpo_approval_instances': RFPOApprovalInstance,
        'rfpo_approval_actions': RFPOApprovalAction,
    }
    
    with app.app_context():
        fixes_applied = 0
        fixes_failed = 0
        
        with db.engine.connect() as conn:
            for table_name, cols in missing_columns.items():
                if table_name not in models_map:
                    print(f"\n⚠️  Skipping {table_name} - no model mapping")
                    continue
                
                if cols == ['ENTIRE TABLE MISSING']:
                    print(f"\n⚠️  Skipping {table_name} - entire table missing, use db.create_all()")
                    continue
                
                model = models_map[table_name]
                model_columns = get_model_columns(model)
                
                print(f"\n📋 Fixing {table_name}:")
                
                for col_name in cols:
                    if col_name not in model_columns:
                        continue
                    
                    col_info = model_columns[col_name]
                    col_type = col_info['type']
                    
                    # Map SQLAlchemy types to PostgreSQL types
                    sql_type = 'TEXT'
                    if 'VARCHAR' in col_type:
                        sql_type = col_type
                    elif 'INTEGER' in col_type:
                        sql_type = 'INTEGER'
                    elif 'BOOLEAN' in col_type:
                        sql_type = 'BOOLEAN'
                    elif 'TIMESTAMP' in col_type or 'DATETIME' in col_type:
                        sql_type = 'TIMESTAMP'
                    elif 'DATE' in col_type:
                        sql_type = 'DATE'
                    elif 'NUMERIC' in col_type:
                        sql_type = 'NUMERIC(12,2)'
                    
                    try:
                        # Add column as nullable first
                        print(f"  📝 Adding {col_name} ({sql_type})...", end=' ')
                        conn.execute(text(f"""
                            ALTER TABLE {table_name}
                            ADD COLUMN {col_name} {sql_type}
                        """))
                        conn.commit()
                        
                        # Set defaults for specific columns
                        if col_name == 'record_id':
                            conn.execute(text(f"""
                                UPDATE {table_name}
                                SET {col_name} = LPAD(id::text, 8, '0')
                                WHERE {col_name} IS NULL
                            """))
                            conn.commit()
                        elif sql_type == 'BOOLEAN':
                            default_val = 'TRUE' if col_name == 'active' else 'FALSE'
                            conn.execute(text(f"""
                                UPDATE {table_name}
                                SET {col_name} = {default_val}
                                WHERE {col_name} IS NULL
                            """))
                            conn.commit()
                        
                        # Make NOT NULL if required (except password_hash)
                        if not col_info['nullable'] and col_name != 'password_hash':
                            try:
                                conn.execute(text(f"""
                                    ALTER TABLE {table_name}
                                    ALTER COLUMN {col_name} SET NOT NULL
                                """))
                                conn.commit()
                            except:
                                pass
                        
                        print("✅")
                        fixes_applied += 1
                        
                    except Exception as e:
                        print(f"❌ {str(e)[:60]}")
                        fixes_failed += 1
        
        print(f"\n{'=' * 80}")
        print(f"✅ Successfully added: {fixes_applied} columns")
        if fixes_failed > 0:
            print(f"❌ Failed to add: {fixes_failed} columns")
        
        return fixes_applied > 0


if __name__ == "__main__":
    print("🚀 Non-Destructive Database Schema Validator")
    print("=" * 80)
    print("This tool will check your database schema and optionally add missing columns")
    print("WITHOUT dropping any existing data.")
    print("=" * 80)
    
    app = create_app()
    
    # Validate schemas
    missing = validate_all_schemas(app)
    
    if missing:
        print("\n" + "=" * 80)
        response = input("\n❓ Apply fixes? This will ADD missing columns without losing data (y/N): ")
        
        if response.lower() == 'y':
            fixed = fix_missing_columns(app, missing)
            
            if fixed:
                print("\n" + "=" * 80)
                print("🔄 Re-validating schema...")
                missing = validate_all_schemas(app)
                
                if not missing:
                    print("\n✅ All issues resolved!")
        else:
            print("\n⚠️  Skipping fixes - manual intervention required")
            sys.exit(1)
    
    print("\n" + "=" * 80)
    if not missing:
        print("✅ Database schema is valid and application-ready!")
        sys.exit(0)
    else:
        print("❌ Database schema still has issues")
        sys.exit(1)
