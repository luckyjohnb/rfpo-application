#!/usr/bin/env python3
"""
Quick RFPO Creation Script
Create RFPOs easily and quickly using casahome2000@gmail.com
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

def get_user_by_email(email):
    """Find user by email"""
    return User.query.filter_by(email=email, active=True).first()

def list_consortiums():
    """List available consortiums"""
    consortiums = Consortium.query.filter_by(active=True).all()
    print("\n📋 Available Consortiums:")
    print("-" * 50)
    for i, consortium in enumerate(consortiums, 1):
        print(f"{i:2d}. {consortium.abbrev} - {consortium.name}")
    return consortiums

def list_projects_for_consortium(consortium_id):
    """List projects for a specific consortium"""
    projects = Project.query.filter(
        Project.consortium_ids.like(f'%{consortium_id}%'),
        Project.active == True
    ).all()
    
    if not projects:
        print(f"\n❌ No projects found for consortium {consortium_id}")
        return []
    
    print(f"\n📂 Projects for Consortium {consortium_id}:")
    print("-" * 60)
    for i, project in enumerate(projects, 1):
        print(f"{i:2d}. [{project.ref}] {project.name}")
        if project.description:
            print(f"    {project.description[:80]}{'...' if len(project.description) > 80 else ''}")
    return projects

def list_teams():
    """List available teams"""
    teams = Team.query.filter_by(active=True).all()
    print("\n👥 Available Teams:")
    print("-" * 50)
    for i, team in enumerate(teams, 1):
        consortium_info = f" ({team.consortium_consort_id})" if team.consortium_consort_id else ""
        print(f"{i:2d}. {team.abbrev} - {team.name}{consortium_info}")
    return teams

def list_vendors():
    """List available vendors"""
    vendors = Vendor.query.filter_by(active=True).all()
    print("\n🏢 Available Vendors:")
    print("-" * 60)
    for i, vendor in enumerate(vendors, 1):
        status_info = f" [{vendor.status.upper()}]" if vendor.status != 'live' else ""
        print(f"{i:2d}. {vendor.company_name}{status_info}")
    return vendors

def list_vendor_sites(vendor):
    """List sites for a specific vendor"""
    sites = vendor.sites
    if not sites:
        print(f"\n❌ No sites found for vendor {vendor.company_name}")
        return []
    
    print(f"\n📍 Sites for {vendor.company_name}:")
    print("-" * 60)
    for i, site in enumerate(sites, 1):
        print(f"{i:2d}. {site.contact_name} - {site.contact_city}, {site.contact_state}")
    return sites

def generate_rfpo_id(project_ref):
    """Generate RFPO ID based on project and date"""
    today = datetime.now()
    date_str = today.strftime('%Y-%m-%d')
    
    # Count existing RFPOs for today to generate sequence number
    existing_count = RFPO.query.filter(
        RFPO.rfpo_id.like(f'RFPO-{project_ref}-%{date_str}%')
    ).count()
    
    sequence = f"N{existing_count + 1:02d}"
    return f"RFPO-{project_ref}-{date_str}-{sequence}"

def add_line_item(rfpo, line_number):
    """Add a line item to the RFPO interactively"""
    print(f"\n➕ Adding Line Item #{line_number}")
    print("-" * 40)
    
    # Get basic line item info
    while True:
        try:
            quantity = int(input("Quantity: ") or "1")
            break
        except ValueError:
            print("❌ Please enter a valid number for quantity.")
    
    description = input("Description: ").strip()
    if not description:
        print("❌ Description is required!")
        return None
    
    while True:
        try:
            unit_price = float(input("Unit Price ($): ") or "0.00")
            break
        except ValueError:
            print("❌ Please enter a valid price.")
    
    # Create line item
    line_item = RFPOLineItem(
        rfpo_id=rfpo.id,
        line_number=line_number,
        quantity=quantity,
        description=description,
        unit_price=Decimal(str(unit_price))
    )
    line_item.calculate_total()
    
    # Ask about capital equipment
    is_capital = input("\nIs this capital equipment? (y/N): ").lower().startswith('y')
    if is_capital:
        line_item.is_capital_equipment = True
        line_item.capital_description = input("Capital Equipment Description: ").strip()
        line_item.capital_serial_id = input("Serial/ID Number: ").strip()
        line_item.capital_location = input("Location: ").strip()
        line_item.capital_condition = input("Condition: ").strip()
        
        # Optional acquisition date
        acq_date_str = input("Acquisition Date (YYYY-MM-DD, optional): ").strip()
        if acq_date_str:
            try:
                line_item.capital_acquisition_date = datetime.strptime(acq_date_str, '%Y-%m-%d').date()
            except ValueError:
                print("❌ Invalid date format, skipping acquisition date.")
        
        # Optional acquisition cost
        acq_cost_str = input("Acquisition Cost ($, optional): ").strip()
        if acq_cost_str:
            try:
                line_item.capital_acquisition_cost = Decimal(acq_cost_str)
            except ValueError:
                print("❌ Invalid cost format, skipping acquisition cost.")
    
    return line_item

def create_rfpo_interactive():
    """Create an RFPO interactively"""
    print("🚀 RFPO Quick Creation Tool")
    print("=" * 50)
    
    # Find the user
    user_email = "casahome2000@gmail.com"
    user = get_user_by_email(user_email)
    if not user:
        print(f"❌ User {user_email} not found! Please ensure this user exists in the system.")
        return None
    
    print(f"👤 Creating RFPO for: {user.get_display_name()} ({user_email})")
    
    # Step 1: Select Consortium
    consortiums = list_consortiums()
    if not consortiums:
        print("❌ No consortiums available!")
        return None
    
    while True:
        try:
            consortium_choice = int(input(f"\nSelect consortium (1-{len(consortiums)}): ")) - 1
            if 0 <= consortium_choice < len(consortiums):
                selected_consortium = consortiums[consortium_choice]
                break
            else:
                print("❌ Invalid choice!")
        except ValueError:
            print("❌ Please enter a valid number!")
    
    print(f"✅ Selected: {selected_consortium.abbrev} - {selected_consortium.name}")
    
    # Step 2: Select Project
    projects = list_projects_for_consortium(selected_consortium.consort_id)
    if not projects:
        print("❌ No projects available for this consortium!")
        return None
    
    while True:
        try:
            project_choice = int(input(f"\nSelect project (1-{len(projects)}): ")) - 1
            if 0 <= project_choice < len(projects):
                selected_project = projects[project_choice]
                break
            else:
                print("❌ Invalid choice!")
        except ValueError:
            print("❌ Please enter a valid number!")
    
    print(f"✅ Selected: [{selected_project.ref}] {selected_project.name}")
    
    # Step 3: Select Team
    teams = list_teams()
    if not teams:
        print("❌ No teams available!")
        return None
    
    while True:
        try:
            team_choice = int(input(f"\nSelect team (1-{len(teams)}): ")) - 1
            if 0 <= team_choice < len(teams):
                selected_team = teams[team_choice]
                break
            else:
                print("❌ Invalid choice!")
        except ValueError:
            print("❌ Please enter a valid number!")
    
    print(f"✅ Selected: {selected_team.abbrev} - {selected_team.name}")
    
    # Step 4: Basic RFPO Information
    print("\n📝 RFPO Details")
    print("-" * 30)
    
    title = input("RFPO Title: ").strip()
    if not title:
        title = f"RFPO for {selected_project.name}"
    
    description = input("RFPO Description (optional): ").strip()
    government_agreement = input("Government Agreement Number (optional): ").strip()
    
    # Generate RFPO ID
    rfpo_id = generate_rfpo_id(selected_project.ref)
    print(f"📄 Generated RFPO ID: {rfpo_id}")
    
    # Step 5: Requestor Information
    print("\n📞 Requestor Information")
    print("-" * 30)
    requestor_tel = input(f"Requestor Phone [{user.phone or 'N/A'}]: ").strip() or user.phone
    requestor_location = input("Requestor Location: ").strip() or "USCAR, MI"
    
    # Step 6: Shipping Information
    print("\n📦 Shipping Information")
    print("-" * 30)
    shipto_name = input(f"Ship to Name [{user.get_display_name()}]: ").strip() or user.get_display_name()
    shipto_tel = input("Ship to Phone: ").strip()
    shipto_address = input("Ship to Address: ").strip() or "USCAR, MI"
    
    # Default invoice address
    invoice_address = """United States Council for Automotive 
Research LLC
Attn: Accounts Payable
3000 Town Center Building, Suite 35
Southfield, MI  48075"""
    
    print(f"💰 Invoice Address: {invoice_address}")
    
    # Step 7: Delivery Information
    print("\n🚚 Delivery Information")
    print("-" * 30)
    
    # Delivery date
    delivery_date_str = input("Delivery Date (YYYY-MM-DD, optional): ").strip()
    delivery_date = None
    if delivery_date_str:
        try:
            delivery_date = datetime.strptime(delivery_date_str, '%Y-%m-%d').date()
        except ValueError:
            print("❌ Invalid date format, skipping delivery date.")
    
    # Delivery options
    print("\nDelivery Type:")
    print("1. FOB Seller's Plant")
    print("2. FOB Destination")
    delivery_type_choice = input("Select (1-2, default 2): ").strip() or "2"
    delivery_type = "FOB Destination" if delivery_type_choice == "2" else "FOB Seller's Plant"
    
    print("\nDelivery Payment:")
    print("1. Collect")
    print("2. Prepaid")
    delivery_payment_choice = input("Select (1-2, default 2): ").strip() or "2"
    delivery_payment = "Prepaid" if delivery_payment_choice == "2" else "Collect"
    
    print("\nDelivery Routing:")
    print("1. Buyer's traffic")
    print("2. Seller's traffic")
    delivery_routing_choice = input("Select (1-2, default 1): ").strip() or "1"
    delivery_routing = "Buyer's traffic" if delivery_routing_choice == "1" else "Seller's traffic"
    
    # Step 8: Vendor Selection (optional for now)
    print("\n🏢 Vendor Selection")
    print("-" * 30)
    select_vendor = input("Select a vendor now? (y/N): ").lower().startswith('y')
    
    selected_vendor = None
    selected_vendor_site = None
    
    if select_vendor:
        vendors = list_vendors()
        if vendors:
            while True:
                try:
                    vendor_choice = int(input(f"\nSelect vendor (1-{len(vendors)}): ")) - 1
                    if 0 <= vendor_choice < len(vendors):
                        selected_vendor = vendors[vendor_choice]
                        break
                    else:
                        print("❌ Invalid choice!")
                except ValueError:
                    print("❌ Please enter a valid number!")
            
            print(f"✅ Selected Vendor: {selected_vendor.company_name}")
            
            # Select vendor site
            sites = list_vendor_sites(selected_vendor)
            if sites:
                while True:
                    try:
                        site_choice = int(input(f"\nSelect vendor site (1-{len(sites)}): ")) - 1
                        if 0 <= site_choice < len(sites):
                            selected_vendor_site = sites[site_choice]
                            break
                        else:
                            print("❌ Invalid choice!")
                    except ValueError:
                        print("❌ Please enter a valid number!")
                
                print(f"✅ Selected Site: {selected_vendor_site.contact_name}")
    
    # Create the RFPO
    print("\n💾 Creating RFPO...")
    rfpo = RFPO(
        rfpo_id=rfpo_id,
        title=title,
        description=description,
        project_id=selected_project.project_id,
        consortium_id=selected_consortium.consort_id,
        team_id=selected_team.id,
        government_agreement_number=government_agreement,
        requestor_id=user.record_id,
        requestor_tel=requestor_tel,
        requestor_location=requestor_location,
        shipto_name=shipto_name,
        shipto_tel=shipto_tel,
        shipto_address=shipto_address,
        invoice_address=invoice_address,
        delivery_date=delivery_date,
        delivery_type=delivery_type,
        delivery_payment=delivery_payment,
        delivery_routing=delivery_routing,
        vendor_id=selected_vendor.id if selected_vendor else None,
        vendor_site_id=selected_vendor_site.id if selected_vendor_site else None,
        created_by=user.get_display_name()
    )
    
    try:
        db.session.add(rfpo)
        db.session.commit()
        print(f"✅ RFPO {rfpo.rfpo_id} created successfully!")
        
        # Step 9: Add Line Items
        print("\n📝 Line Items")
        print("-" * 30)
        line_number = 1
        
        while True:
            add_more = input(f"\nAdd line item #{line_number}? (Y/n): ").lower()
            if add_more == 'n':
                break
            
            line_item = add_line_item(rfpo, line_number)
            if line_item:
                db.session.add(line_item)
                db.session.commit()
                print(f"✅ Line item #{line_number} added: {line_item.quantity} x {line_item.description} @ ${line_item.unit_price} = ${line_item.total_price}")
                line_number += 1
        
        # Calculate totals
        total_amount = sum(Decimal(str(item.total_price)) for item in rfpo.line_items)
        rfpo.subtotal = total_amount
        rfpo.total_amount = total_amount
        
        # Cost sharing (optional)
        if total_amount > 0:
            print(f"\n💰 Financial Summary")
            print("-" * 30)
            print(f"Subtotal: ${total_amount}")
            
            cost_share = input("Vendor cost share amount (optional, $): ").strip()
            if cost_share:
                try:
                    cost_share_amount = Decimal(cost_share)
                    rfpo.cost_share_description = input("Cost share description: ").strip()
                    rfpo.cost_share_amount = cost_share_amount
                    rfpo.total_amount = total_amount - cost_share_amount
                    print(f"Cost Share: ${cost_share_amount}")
                    print(f"Net Total: ${rfpo.total_amount}")
                except ValueError:
                    print("❌ Invalid cost share amount, skipping.")
        
        # Optional comments
        comments = input("\nOptional comments (not included in RFPO): ").strip()
        if comments:
            rfpo.comments = comments
        
        db.session.commit()
        
        # Final summary
        print("\n🎉 RFPO Creation Complete!")
        print("=" * 50)
        print(f"RFPO ID: {rfpo.rfpo_id}")
        print(f"Title: {rfpo.title}")
        print(f"Project: [{selected_project.ref}] {selected_project.name}")
        print(f"Consortium: {selected_consortium.abbrev}")
        print(f"Team: {selected_team.name}")
        print(f"Line Items: {len(rfpo.line_items)}")
        print(f"Total Amount: ${rfpo.total_amount}")
        print(f"Status: {rfpo.status}")
        
        if selected_vendor:
            print(f"Vendor: {selected_vendor.company_name}")
            if selected_vendor_site:
                print(f"Contact: {selected_vendor_site.contact_name}")
        
        print(f"\n📋 Next Steps:")
        print("- Review and edit the RFPO if needed")
        print("- Upload required documents")
        print("- Submit for approval")
        
        return rfpo
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error creating RFPO: {str(e)}")
        return None

def main():
    """Main function"""
    app = create_app()
    
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
        
        try:
            rfpo = create_rfpo_interactive()
            if rfpo:
                print(f"\n✅ RFPO {rfpo.rfpo_id} created successfully!")
            else:
                print("\n❌ RFPO creation failed!")
        except KeyboardInterrupt:
            print("\n\n👋 RFPO creation cancelled by user.")
        except Exception as e:
            print(f"\n❌ Unexpected error: {str(e)}")

if __name__ == '__main__':
    main()
