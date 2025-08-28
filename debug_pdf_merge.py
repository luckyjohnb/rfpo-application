#!/usr/bin/env python3
"""
Debug PDF merge process specifically
"""

import os
import io
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

def test_pdf_merge():
    """Test the PDF merge process step by step"""
    print("🔍 Testing PDF merge process...")
    
    # Step 1: Create a simple overlay with text
    print("1. Creating overlay PDF with test text...")
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    # Draw some test text at known positions
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, 700, "TEST OVERLAY TEXT - This should be visible")
    c.setFont("Helvetica", 10)
    c.drawString(100, 680, "PO Number: TEST-PO-12345")
    c.drawString(100, 660, "Date: 08/27/2025")
    c.drawString(100, 640, "Vendor: Test Vendor Corp")
    
    c.save()
    buffer.seek(0)
    
    # Step 2: Load template PDF
    print("2. Loading template PDF...")
    template_path = "static/po_files/po.pdf"
    if not os.path.exists(template_path):
        print(f"❌ Template not found: {template_path}")
        return
    
    template_reader = PdfReader(template_path)
    print(f"Template pages: {len(template_reader.pages)}")
    
    # Step 3: Load overlay PDF
    print("3. Loading overlay PDF...")
    overlay_reader = PdfReader(buffer)
    print(f"Overlay pages: {len(overlay_reader.pages)}")
    
    # Step 4: Test merge methods
    print("4. Testing merge...")
    
    # Method 1: Standard merge_page
    print("4a. Testing merge_page...")
    try:
        output1 = PdfWriter()
        template_page = template_reader.pages[0]
        overlay_page = overlay_reader.pages[0]
        
        # Try merging overlay ON TOP of template
        template_page.merge_page(overlay_page)
        output1.add_page(template_page)
        
        # Save test result
        with open("debug_merge_test1.pdf", "wb") as f:
            output1.write(f)
        print("✅ Saved debug_merge_test1.pdf")
        
        # Check result
        test_reader = PdfReader("debug_merge_test1.pdf")
        test_text = test_reader.pages[0].extract_text()
        print(f"Result text length: {len(test_text)}")
        print(f"Contains 'TEST OVERLAY': {'TEST OVERLAY' in test_text}")
        print(f"Contains template text: {'DELIVERY:' in test_text}")
        
    except Exception as e:
        print(f"❌ merge_page failed: {e}")
    
    # Method 2: Reverse merge (template on overlay)
    print("4b. Testing reverse merge...")
    try:
        # Reload pages (since merge_page modifies the original)
        template_reader = PdfReader(template_path)
        overlay_reader = PdfReader(buffer)
        
        output2 = PdfWriter()
        template_page = template_reader.pages[0]
        overlay_page = overlay_reader.pages[0]
        
        # Try merging template ON TOP of overlay
        overlay_page.merge_page(template_page)
        output2.add_page(overlay_page)
        
        # Save test result
        with open("debug_merge_test2.pdf", "wb") as f:
            output2.write(f)
        print("✅ Saved debug_merge_test2.pdf")
        
        # Check result
        test_reader = PdfReader("debug_merge_test2.pdf")
        test_text = test_reader.pages[0].extract_text()
        print(f"Result text length: {len(test_text)}")
        print(f"Contains 'TEST OVERLAY': {'TEST OVERLAY' in test_text}")
        print(f"Contains template text: {'DELIVERY:' in test_text}")
        
    except Exception as e:
        print(f"❌ reverse merge failed: {e}")

if __name__ == "__main__":
    test_pdf_merge()
