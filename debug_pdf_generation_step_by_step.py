#!/usr/bin/env python3
"""
Step-by-step debugging of PDF generation pipeline
Find exactly where it's breaking
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from custom_admin import create_app
from models import PDFPositioning, RFPO, Consortium, Project, Vendor, VendorSite
from pdf_generator import RFPOPDFGenerator
import json

def debug_pdf_generation_step_by_step():
    """Debug each step of PDF generation"""
    app = create_app()
    
    with app.app_context():
        print("🔍 STEP-BY-STEP PDF GENERATION DEBUG")
        print("=" * 60)
        
        # STEP 1: Check positioning config exists and has data
        print("\n📋 STEP 1: Check positioning configuration...")
        config = PDFPositioning.query.filter_by(
            consortium_id="00000014",
            template_name='po_template',
            active=True
        ).first()
        
        if not config:
            print("   ❌ No positioning config found")
            return False
        
        print(f"   ✅ Found config ID {config.id}")
        
        # Check positioning data
        positioning_data = config.get_positioning_data()
        print(f"   Positioning data fields: {len(positioning_data)}")
        
        # Look for our test field
        if 'test_field' in positioning_data:
            test_data = positioning_data['test_field']
            print(f"   ✅ Test field found: x={test_data.get('x')}, y={test_data.get('y')}, visible={test_data.get('visible')}")
        else:
            print(f"   ❌ Test field NOT found in positioning data")
            print(f"   Available fields: {list(positioning_data.keys())}")
            return False
        
        # STEP 2: Get sample data for PDF generation
        print("\n📋 STEP 2: Get sample data...")
        sample_rfpo = RFPO.query.first()
        if not sample_rfpo:
            print("   ❌ No RFPO found")
            return False
        
        consortium = Consortium.query.filter_by(consort_id="00000014").first()
        if not consortium:
            print("   ❌ No consortium found")
            return False
        
        project = Project.query.filter_by(project_id=sample_rfpo.project_id).first()
        vendor = Vendor.query.get(sample_rfpo.vendor_id) if sample_rfpo.vendor_id else None
        
        print(f"   ✅ Sample RFPO: {sample_rfpo.rfpo_id}")
        print(f"   ✅ Consortium: {consortium.abbrev}")
        print(f"   ✅ Project: {project.project_id if project else 'None'}")
        print(f"   ✅ Vendor: {vendor.company_name if vendor else 'None'}")
        
        # STEP 3: Initialize PDF generator with positioning config
        print("\n📋 STEP 3: Initialize PDF generator...")
        try:
            pdf_generator = RFPOPDFGenerator(positioning_config=config)
            print("   ✅ PDF generator initialized")
        except Exception as e:
            print(f"   ❌ PDF generator initialization failed: {e}")
            return False
        
        # STEP 4: Test _get_field_position method directly
        print("\n📋 STEP 4: Test field position retrieval...")
        try:
            result = pdf_generator._get_field_position('test_field', 0, 0)
            if result[0] is None:
                print(f"   ❌ Field position returned None (field hidden or missing)")
                return False
            else:
                x, y, font_size, font_weight = result
                print(f"   ✅ Field position: x={x}, y={y}, font_size={font_size}, font_weight={font_weight}")
        except Exception as e:
            print(f"   ❌ Error getting field position: {e}")
            return False
        
        # STEP 5: Test _draw_text_with_positioning method
        print("\n📋 STEP 5: Test text drawing...")
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            import io
            
            # Create test canvas
            buffer = io.BytesIO()
            test_canvas = canvas.Canvas(buffer, pagesize=letter)
            
            # Try to draw the test field
            pdf_generator._draw_text_with_positioning(test_canvas, 'test_field', 'TEST CONTENT', 0, 0)
            
            test_canvas.save()
            buffer.seek(0)
            
            if len(buffer.getvalue()) > 1000:  # PDF has content
                print(f"   ✅ Text drawing succeeded, PDF size: {len(buffer.getvalue())} bytes")
            else:
                print(f"   ❌ Text drawing failed, PDF too small: {len(buffer.getvalue())} bytes")
                return False
                
        except Exception as e:
            print(f"   ❌ Error drawing text: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # STEP 6: Test full PDF generation
        print("\n📋 STEP 6: Test full PDF generation...")
        try:
            pdf_buffer = pdf_generator.generate_po_pdf(sample_rfpo, consortium, project, vendor, None)
            
            if pdf_buffer and len(pdf_buffer.getvalue()) > 10000:
                print(f"   ✅ Full PDF generation succeeded, size: {len(pdf_buffer.getvalue())} bytes")
                
                # Save test PDF for inspection
                with open("debug_test.pdf", "wb") as f:
                    f.write(pdf_buffer.getvalue())
                print(f"   📄 Test PDF saved as: debug_test.pdf")
                
            else:
                print(f"   ❌ Full PDF generation failed or too small")
                return False
                
        except Exception as e:
            print(f"   ❌ Error generating full PDF: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        print(f"\n🎯 ALL STEPS PASSED")
        print(f"   PDF generation pipeline is working")
        print(f"   Check debug_test.pdf for test field content")
        return True

if __name__ == "__main__":
    success = debug_pdf_generation_step_by_step()
    if success:
        print(f"\n✅ PDF GENERATION PIPELINE: WORKING")
    else:
        print(f"\n❌ PDF GENERATION PIPELINE: BROKEN")
