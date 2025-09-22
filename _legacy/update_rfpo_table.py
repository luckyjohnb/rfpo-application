#!/usr/bin/env python3
"""
Update existing RFPO table to add new columns
Uses the same database connection as custom_admin.py
"""

import os
import sys
from datetime import datetime

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from custom_admin import create_app
from models import db

def add_missing_columns():
    """Add missing columns to the existing RFPO table"""
    app = create_app()
    
    with app.app_context():
        try:
            print("🔄 Checking and adding missing RFPO columns...")
            
            # List of columns to add with their SQL definitions
            new_columns = [
                "project_id VARCHAR(32) DEFAULT ''",
                "consortium_id VARCHAR(32) DEFAULT ''", 
                "government_agreement_number VARCHAR(255)",
                "requestor_id VARCHAR(32) DEFAULT ''",
                "requestor_tel VARCHAR(50)",
                "requestor_location TEXT",
                "shipto_name VARCHAR(255)",
                "shipto_tel VARCHAR(50)", 
                "shipto_address TEXT",
                "invoice_address TEXT",
                "delivery_date DATE",
                "delivery_type VARCHAR(100)",
                "delivery_payment VARCHAR(100)",
                "delivery_routing VARCHAR(100)",
                "payment_terms VARCHAR(100) DEFAULT 'Net 30'",
                "vendor_id INTEGER",
                "vendor_site_id INTEGER",
                "subtotal NUMERIC(12, 2) DEFAULT 0.00",
                "cost_share_description VARCHAR(255)",
                "cost_share_type VARCHAR(20) DEFAULT 'total'",
                "cost_share_amount NUMERIC(12, 2) DEFAULT 0.00",
                "total_amount NUMERIC(12, 2) DEFAULT 0.00",
                "comments TEXT"
            ]
            
            # Add each column if it doesn't exist
            for column_def in new_columns:
                column_name = column_def.split()[0]
                try:
                    db.session.execute(db.text(f"ALTER TABLE rfpos ADD COLUMN {column_def}"))
                    db.session.commit()
                    print(f"  ✅ Added column: {column_name}")
                except Exception as e:
                    if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                        print(f"  ⏭️  Column {column_name} already exists")
                    else:
                        print(f"  ❌ Failed to add {column_name}: {e}")
                    db.session.rollback()
            
            print("\n🔄 Creating RFPO line items table if it doesn't exist...")
            
            # Create the line items table
            create_line_items_sql = """
            CREATE TABLE IF NOT EXISTS rfpo_line_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rfpo_id INTEGER NOT NULL,
                line_number INTEGER NOT NULL,
                quantity INTEGER DEFAULT 0,
                description TEXT NOT NULL,
                unit_price NUMERIC(12, 2) DEFAULT 0.00,
                total_price NUMERIC(12, 2) DEFAULT 0.00,
                is_capital_equipment BOOLEAN DEFAULT 0,
                capital_description VARCHAR(255),
                capital_serial_id VARCHAR(100),
                capital_location VARCHAR(255),
                capital_acquisition_date DATE,
                capital_condition VARCHAR(255),
                capital_acquisition_cost NUMERIC(12, 2),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (rfpo_id) REFERENCES rfpos(id)
            )
            """
            
            db.session.execute(db.text(create_line_items_sql))
            db.session.commit()
            print("  ✅ RFPO line items table ready")
            
            print("\n🔄 Updating existing RFPOs with default values...")
            
            # Update existing RFPOs that have null/empty required fields
            update_sql = """
            UPDATE rfpos 
            SET 
                project_id = COALESCE(NULLIF(project_id, ''), '00000001'),
                consortium_id = COALESCE(NULLIF(consortium_id, ''), '00000001'),
                requestor_id = COALESCE(NULLIF(requestor_id, ''), '00000001'),
                requestor_location = COALESCE(requestor_location, 'USCAR, MI'),
                shipto_address = COALESCE(shipto_address, 'USCAR, MI'),
                invoice_address = COALESCE(invoice_address, 'United States Council for Automotive Research LLC
Attn: Accounts Payable
3000 Town Center Building, Suite 35
Southfield, MI  48075'),
                delivery_type = COALESCE(delivery_type, 'FOB Destination'),
                delivery_payment = COALESCE(delivery_payment, 'Prepaid'),
                delivery_routing = COALESCE(delivery_routing, 'Buyer''s traffic'),
                payment_terms = COALESCE(payment_terms, 'Net 30'),
                subtotal = COALESCE(subtotal, 0.00),
                cost_share_type = COALESCE(cost_share_type, 'total'),
                cost_share_amount = COALESCE(cost_share_amount, 0.00),
                total_amount = COALESCE(total_amount, 0.00)
            WHERE project_id IS NULL OR project_id = '' OR consortium_id IS NULL OR consortium_id = ''
            """
            
            db.session.execute(db.text(update_sql))
            db.session.commit()
            print(f"  ✅ Updated existing RFPOs")
            
            print("\n✅ Database update completed successfully!")
            print("🚀 You can now start the admin panel: python3 custom_admin.py")
            
        except Exception as e:
            print(f"❌ Error updating database: {e}")
            print("🔧 Try running this if the error persists:")
            print("   - Delete the database file and let the app recreate it")
            print("   - Or manually run: DROP TABLE rfpos; then restart the app")

if __name__ == '__main__':
    add_missing_columns()
