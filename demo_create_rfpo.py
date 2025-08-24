#!/usr/bin/env python3
"""
Demo RFPO Creation Script
Quick demo of RFPO creation with sample data
"""

import os
import sys
from datetime import datetime, date
from decimal import Decimal

# Add the current directory to the path to import models
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import db, RFPO, RFPOLineItem, User, Project, Team, Consortium, Vendor, VendorSite
from flask import Flask

def create_app():
    """Create Flask app with database configuration"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rfpo_admin.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app

def create_demo_rfpo():
    """Create a demo RFPO with sample data"""
    print("🚀 Creating Demo RFPO...")
    print("=" * 40)
    
    # Find or create the demo user
    user_email = "casahome2000@gmail.com"
    user = User.query.filter_by(email=user_email).first()
    
    if not user:
        print(f"❌ User {user_email} not found!")
        print("Creating demo user...")
        
        # Generate user record ID
        from custom_admin import generate_next_id
        user_record_id = generate_next_id(User, 'record_id', '', 8)
        
        user = User(
            record_id=user_record_id,
            fullname="Demo User",
            email=user_email,
            password_hash="demo_hash",  # Not for real use
            company="USCAR",
            position="Demo Position",
            phone="(248) 223-9000",
            active=True,
            agreed_to_terms=True
        )
        user.set_permissions(['RFPO_USER'])
        db.session.add(user)
        db.session.commit()
        print(f"✅ Created demo user: {user.get_display_name()}")
    
    # Find first available consortium, team, and project
    consortium = Consortium.query.filter_by(active=True).first()
    if not consortium:
        print("❌ No active consortiums found!")
        return None
    
    team = Team.query.filter_by(active=True).first()
    if not team:
        print("❌ No active teams found!")
        return None
    
    project = Project.query.filter_by(active=True).first()
    if not project:
        print("❌ No active projects found!")
        return None
    
    # Find a vendor (optional)
    vendor = Vendor.query.filter_by(active=True).first()
    vendor_site = None
    if vendor and vendor.sites:
        vendor_site = vendor.sites[0]
    
    print(f"👤 User: {user.get_display_name()} ({user.email})")
    print(f"🏢 Consortium: {consortium.abbrev} - {consortium.name}")
    print(f"👥 Team: {team.abbrev} - {team.name}")
    print(f"📂 Project: [{project.ref}] {project.name}")
    if vendor:
        print(f"🏪 Vendor: {vendor.company_name}")
        if vendor_site:
            print(f"📍 Contact: {vendor_site.contact_name}")
    
    # Generate RFPO ID
    today = datetime.now()
    date_str = today.strftime('%Y-%m-%d')
    existing_count = RFPO.query.filter(
        RFPO.rfpo_id.like(f'RFPO-{project.ref}-%{date_str}%')
    ).count()
    rfpo_id = f"RFPO-{project.ref}-{date_str}-N{existing_count + 1:02d}"
    
    # Create the RFPO
    rfpo = RFPO(
        rfpo_id=rfpo_id,
        title=f"Demo RFPO for {project.name}",
        description="This is a demonstration RFPO created by the quick creation script.",
        project_id=project.project_id,
        consortium_id=consortium.consort_id,
        team_id=team.id,
        government_agreement_number="DEMO-2024-001",
        requestor_id=user.record_id,
        requestor_tel=user.phone or "(248) 223-9000",
        requestor_location="USCAR, MI",
        shipto_name=user.get_display_name(),
        shipto_tel="(248) 223-9000",
        shipto_address="USCAR\n3000 Town Center Building, Suite 35\nSouthfield, MI 48075",
        invoice_address="""United States Council for Automotive 
Research LLC
Attn: Accounts Payable
3000 Town Center Building, Suite 35
Southfield, MI  48075""",
        delivery_date=date(2024, 12, 31),
        delivery_type="FOB Destination",
        delivery_payment="Prepaid",
        delivery_routing="Buyer's traffic",
        payment_terms="Net 30",
        vendor_id=vendor.id if vendor else None,
        vendor_site_id=vendor_site.id if vendor_site else None,
        comments="Demo RFPO created for testing purposes.",
        created_by=user.get_display_name()
    )
    
    try:
        db.session.add(rfpo)
        db.session.commit()
        print(f"\n✅ RFPO {rfpo.rfpo_id} created!")
        
        # Add some demo line items
        print("\n📝 Adding demo line items...")
        
        # Line Item 1 - Software License
        line1 = RFPOLineItem(
            rfpo_id=rfpo.id,
            line_number=1,
            quantity=1,
            description="Software License - Annual subscription for project management tool",
            unit_price=Decimal('1200.00')
        )
        line1.calculate_total()
        db.session.add(line1)
        
        # Line Item 2 - Consulting Services
        line2 = RFPOLineItem(
            rfpo_id=rfpo.id,
            line_number=2,
            quantity=40,
            description="Technical consulting services - Senior engineer at 40 hours",
            unit_price=Decimal('150.00')
        )
        line2.calculate_total()
        db.session.add(line2)
        
        # Line Item 3 - Equipment (Capital)
        line3 = RFPOLineItem(
            rfpo_id=rfpo.id,
            line_number=3,
            quantity=1,
            description="Testing Equipment - High-precision measurement device",
            unit_price=Decimal('15000.00'),
            is_capital_equipment=True,
            capital_description="Precision measurement device for automotive testing",
            capital_location="USCAR Lab Facility",
            capital_condition="New",
            capital_acquisition_date=date.today(),
            capital_acquisition_cost=Decimal('15000.00')
        )
        line3.calculate_total()
        db.session.add(line3)
        
        db.session.commit()
        
        # Calculate totals
        total_amount = sum(item.total_price for item in rfpo.line_items)
        rfpo.subtotal = total_amount
        
        # Add cost sharing
        cost_share = Decimal('2000.00')
        rfpo.cost_share_description = "Vendor contribution towards project"
        rfpo.cost_share_type = "total"
        rfpo.cost_share_amount = cost_share
        rfpo.total_amount = total_amount - cost_share
        
        db.session.commit()
        
        # Print summary
        print("\n🎉 Demo RFPO Created Successfully!")
        print("=" * 50)
        print(f"RFPO ID: {rfpo.rfpo_id}")
        print(f"Title: {rfpo.title}")
        print(f"Project: [{project.ref}] {project.name}")
        print(f"Consortium: {consortium.abbrev}")
        print(f"Team: {team.name}")
        print(f"Requestor: {user.get_display_name()}")
        if vendor:
            print(f"Vendor: {vendor.company_name}")
        
        print(f"\n💰 Financial Summary:")
        print(f"Line Items: {len(rfpo.line_items)}")
        for item in rfpo.line_items:
            capital_flag = " [CAPITAL]" if item.is_capital_equipment else ""
            print(f"  {item.line_number}. {item.quantity} x {item.description[:40]}... @ ${item.unit_price} = ${item.total_price}{capital_flag}")
        
        print(f"\nSubtotal: ${rfpo.subtotal}")
        print(f"Cost Share: ${rfpo.cost_share_amount} ({rfpo.cost_share_description})")
        print(f"Net Total: ${rfpo.total_amount}")
        
        print(f"\n📋 Status: {rfpo.status}")
        print(f"📅 Created: {rfpo.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return rfpo
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error creating demo RFPO: {str(e)}")
        return None

def list_recent_rfpos():
    """List recent RFPOs"""
    rfpos = RFPO.query.order_by(RFPO.created_at.desc()).limit(5).all()
    
    if not rfpos:
        print("\n📋 No RFPOs found in database.")
        return
    
    print(f"\n📋 Recent RFPOs:")
    print("-" * 80)
    for rfpo in rfpos:
        vendor_info = f" | {rfpo.vendor.company_name}" if rfpo.vendor else ""
        print(f"{rfpo.rfpo_id} | {rfpo.title[:40]:<40} | ${rfpo.total_amount:>10} | {rfpo.status}{vendor_info}")

def main():
    """Main function"""
    app = create_app()
    
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
        
        print("🚀 RFPO Demo Creation Tool")
        print("=" * 50)
        
        # Show recent RFPOs first
        list_recent_rfpos()
        
        # Ask if user wants to create a demo
        print("\nThis will create a demonstration RFPO with sample data.")
        create_demo = input("Create demo RFPO? (Y/n): ").lower()
        
        if create_demo == 'n':
            print("👋 Demo cancelled.")
            return
        
        try:
            rfpo = create_demo_rfpo()
            if rfpo:
                print(f"\n✅ Demo RFPO {rfpo.rfpo_id} created successfully!")
                print("\n📋 You can now:")
                print("- View this RFPO in the admin panel")
                print("- Use it as a template for real RFPOs")
                print("- Test the RFPO workflow and approval process")
            else:
                print("\n❌ Demo RFPO creation failed!")
        except KeyboardInterrupt:
            print("\n\n👋 Demo creation cancelled by user.")
        except Exception as e:
            print(f"\n❌ Unexpected error: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    main()
