#!/usr/bin/env python3
"""
Debug script for PO Proof generation
"""

import os
import sys
from flask import Flask

# Add the current directory to Python path
sys.path.insert(0, os.getcwd())

from models import db, RFPO, Project, Consortium, Vendor, VendorSite, User
from pdf_generator import RFPOPDFGenerator

def debug_po_proof():
    """Debug PO proof generation"""
    
    # Create a minimal Flask app context
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rfpo_admin.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        # Get a sample RFPO
        rfpo = RFPO.query.first()
        if not rfpo:
            print("❌ No RFPO found in database")
            return
        
        print(f"🔍 Testing PO Proof for RFPO: {rfpo.rfpo_id}")
        
        # Get related data
        project = Project.query.filter_by(project_id=rfpo.project_id).first()
        consortium = Consortium.query.filter_by(consort_id=rfpo.consortium_id).first()
        vendor = Vendor.query.get(rfpo.vendor_id) if rfpo.vendor_id else None
        vendor_site = VendorSite.query.get(rfpo.vendor_site_id) if rfpo.vendor_site_id else None
        
        print(f"📋 Project: {project.name if project else 'None'}")
        print(f"🏢 Consortium: {consortium.name if consortium else 'None'}")
        print(f"🏪 Vendor: {vendor.company_name if vendor else 'None'}")
        print(f"📍 Vendor Site: {vendor_site.contact_name if vendor_site else 'None'}")
        print(f"📝 Line Items: {len(rfpo.line_items)}")
        
        if not project or not consortium:
            print("❌ Missing required project or consortium data")
            return
        
        try:
            # Test PDF generation
            print("\n🔧 Testing PDF Generation...")
            pdf_generator = RFPOPDFGenerator(positioning_config=None)
            pdf_buffer = pdf_generator.generate_po_pdf(rfpo, consortium, project, vendor, vendor_site)
            
            print(f"✅ PDF Generated successfully! Size: {len(pdf_buffer.getvalue())} bytes")
            
            # Save for inspection
            output_path = "debug_po_proof_output.pdf"
            with open(output_path, 'wb') as f:
                f.write(pdf_buffer.getvalue())
            print(f"💾 Saved debug PDF to: {output_path}")
            
            # Test terms merging specifically
            print("\n🔧 Testing Terms Merging...")
            print(f"Consortium abbrev: '{consortium.abbrev}'")
            
            # Test _get_consortium_terms_file method
            terms_file = pdf_generator._get_consortium_terms_file(consortium.abbrev)
            print(f"Terms file mapping: {terms_file}")
            
            if terms_file:
                terms_path = os.path.join('static/po_files', terms_file)
                print(f"Terms path: {terms_path}")
                print(f"Terms exists: {os.path.exists(terms_path)}")
                
                if os.path.exists(terms_path):
                    from PyPDF2 import PdfReader
                    try:
                        terms_reader = PdfReader(terms_path)
                        print(f"Terms pages: {len(terms_reader.pages)}")
                    except Exception as e:
                        print(f"Terms read error: {e}")
            
        except Exception as e:
            print(f"❌ PDF Generation failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    debug_po_proof()
