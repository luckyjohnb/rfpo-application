#!/usr/bin/env python3
"""
DEBUG PDF GENERATION
Check what's happening in the PDF generator when element is positioned
"""
import requests
import tempfile
import os

def debug_pdf_generation():
    print("🔍 DEBUG PDF GENERATION")
    print("="*60)
    
    session = requests.Session()
    
    # Login
    print("📋 Step 1: Login...")
    login_data = {'email': 'admin@rfpo.com', 'password': 'admin123'}
    login_response = session.post('http://localhost:5111/login', data=login_data)
    
    if login_response.status_code != 200:
        print("❌ Login failed")
        return False
    
    print("✅ Login successful")
    
    # Set up positioning data for po_number field
    print("📋 Step 2: Set positioning data...")
    positioning_data = {
        "po_number": {
            "x": 450,       # PDF X coordinate
            "y": 742,       # PDF Y coordinate (near top)
            "font_size": 14,
            "font_weight": "bold",
            "visible": True
        }
    }
    
    save_response = session.post(
        "http://localhost:5111/api/pdf-positioning/1",
        json={"positioning_data": positioning_data},
        headers={'Content-Type': 'application/json'}
    )
    
    if save_response.status_code == 200:
        print("✅ Positioning data saved")
        print(f"   Data: {positioning_data}")
    else:
        print(f"❌ Failed to save positioning data: {save_response.status_code}")
        return False
    
    # Verify positioning data was saved
    print("📋 Step 3: Verify positioning data...")
    verify_response = session.get("http://localhost:5111/api/pdf-positioning/1")
    
    if verify_response.status_code == 200:
        verify_data = verify_response.json()
        stored_data = verify_data.get('positioning_data', {})
        po_number_data = stored_data.get('po_number', {})
        
        print("✅ Positioning data verified")
        print(f"   Stored po_number data: {po_number_data}")
        
        if po_number_data.get('visible', False):
            print("   ✅ po_number field is marked as visible")
        else:
            print("   ❌ po_number field is not visible!")
            return False
    else:
        print(f"❌ Failed to verify positioning data: {verify_response.status_code}")
        return False
    
    # Generate PDF with debug output
    print("📋 Step 4: Generate PDF with positioning...")
    
    # The PDF generation should now use our positioning data
    pdf_response = session.get("http://localhost:5111/api/pdf-positioning/preview/1")
    
    if pdf_response.status_code == 200:
        print(f"✅ PDF generated: {len(pdf_response.content)} bytes")
        
        # Save PDF for inspection
        with open("debug_positioned_pdf.pdf", "wb") as f:
            f.write(pdf_response.content)
        print("📄 PDF saved: debug_positioned_pdf.pdf")
        
        # Analyze PDF content
        pdf_text = pdf_response.content.decode('latin-1', errors='ignore')
        
        # Look for RFPO ID content (what gets drawn for po_number field)
        rfpo_indicators = ['RFPO', 'PO NUMBER', '00000014']  # Common RFPO identifiers
        found_indicators = [ind for ind in rfpo_indicators if ind in pdf_text.upper()]
        
        print(f"   RFPO indicators found in PDF: {found_indicators}")
        
        if found_indicators:
            print("   ✅ RFPO content found in PDF")
            
            # Check approximate position by looking at text layout
            lines = pdf_text.split('\n')
            for i, line in enumerate(lines[:20]):  # Check first 20 lines
                for indicator in found_indicators:
                    if indicator in line.upper():
                        print(f"   📍 Found '{indicator}' in line {i}: {line.strip()}")
            
            return True
        else:
            print("   ❌ No RFPO content found in PDF")
            
            # Debug: show first 500 characters of PDF text
            print(f"   First 500 chars of PDF: {pdf_text[:500]}")
            return False
    else:
        print(f"❌ PDF generation failed: {pdf_response.status_code}")
        print(f"   Response: {pdf_response.text}")
        return False

if __name__ == "__main__":
    success = debug_pdf_generation()
    
    print(f"\n" + "="*60)
    print("🏆 PDF GENERATION DEBUG RESULTS")
    print("="*60)
    
    if success:
        print("✅ PDF generation is working")
        print("   po_number field appears in PDF")
        print("   Check debug_positioned_pdf.pdf for visual verification")
    else:
        print("❌ PDF generation has issues")
        print("   po_number field not appearing as expected")
    
    print("="*60)
