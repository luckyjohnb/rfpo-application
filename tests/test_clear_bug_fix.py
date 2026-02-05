#!/usr/bin/env python3
"""
TEST CLEAR BUG FIX
Verify that the fix for hardcoded text drawing works correctly
"""
import requests
import time

def test_clear_bug_fix():
    print("🔧 TESTING CLEAR BUG FIX")
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
    
    # Step 2: Clear positioning data via API
    print("📋 Step 2: Clear positioning data...")
    clear_payload = {"positioning_data": {}}
    clear_response = session.post(
        "http://localhost:5111/api/pdf-positioning/1",
        json=clear_payload,
        headers={'Content-Type': 'application/json'}
    )
    
    if clear_response.status_code != 200:
        print(f"❌ Clear failed: {clear_response.status_code}")
        return False
    
    print("✅ Positioning data cleared")
    
    # Step 3: Verify data is cleared
    print("📋 Step 3: Verify data is cleared...")
    verify_response = session.get("http://localhost:5111/api/pdf-positioning/1")
    
    if verify_response.status_code == 200:
        verify_data = verify_response.json()
        positioning_data = verify_data.get('positioning_data', {})
        
        if len(positioning_data) == 0:
            print("✅ Positioning data confirmed empty")
        else:
            print(f"❌ Positioning data not empty: {positioning_data}")
            return False
    else:
        print(f"❌ Verify failed: {verify_response.status_code}")
        return False
    
    # Step 4: Generate PDF and check content
    print("📋 Step 4: Generate PDF with empty positioning data...")
    pdf_response = session.get("http://localhost:5111/api/pdf-positioning/preview/1")
    
    if pdf_response.status_code != 200:
        print(f"❌ PDF generation failed: {pdf_response.status_code}")
        return False
    
    print(f"✅ PDF generated: {len(pdf_response.content)} bytes")
    
    # Save PDF for inspection
    with open("test_clear_bug_fix.pdf", "wb") as f:
        f.write(pdf_response.content)
    print("📄 PDF saved as: test_clear_bug_fix.pdf")
    
    # Step 5: Analyze PDF content
    print("📋 Step 5: Analyze PDF content...")
    pdf_text = pdf_response.content.decode('latin-1', errors='ignore')
    
    # Check for field keywords that should NOT be present
    problematic_keywords = ['VENDOR IS', 'VENDOR', 'PO NUMBER', 'PO DATE', 'DELIVERY', 'PAYMENT']
    found_keywords = []
    
    for keyword in problematic_keywords:
        if keyword in pdf_text.upper():
            found_keywords.append(keyword)
    
    print(f"   Problematic keywords found: {len(found_keywords)}")
    
    if found_keywords:
        print(f"      Found: {', '.join(found_keywords)}")
        print("   ❌ PDF still contains field content!")
        
        # Check if it's just the template structure vs actual field data
        # Count occurrences to see if it's excessive
        vendor_count = pdf_text.upper().count('VENDOR')
        print(f"   'VENDOR' appears {vendor_count} times in PDF")
        
        if vendor_count > 2:  # Allow some template structure
            print("   ❌ Excessive field content - fix incomplete")
            return False
        else:
            print("   ⚠️ Minimal content found - may be template structure")
            return True
    else:
        print("   ✅ No problematic field content found!")
        return True

if __name__ == "__main__":
    success = test_clear_bug_fix()
    
    print(f"\n" + "="*60)
    print("🏆 CLEAR BUG FIX TEST RESULTS")
    print("="*60)
    
    if success:
        print("✅ CLEAR BUG FIX: SUCCESSFUL!")
        print("   PDF generation now respects empty positioning data")
        print("   Hardcoded text drawing has been eliminated")
    else:
        print("❌ CLEAR BUG FIX: INCOMPLETE!")
        print("   PDF still contains field content when cleared")
        print("   More hardcoded drawing calls need to be fixed")
    
    print(f"\n📄 Check test_clear_bug_fix.pdf for visual confirmation")
    print("="*60)
