#!/usr/bin/env python3
"""
TEST PDF AUTHENTICATION
Check if the PDF preview endpoint has authentication issues
"""
import requests
import time

def test_pdf_auth():
    print("🔍 PDF AUTHENTICATION TEST")
    print("="*60)
    
    # Test 1: Direct access without login
    print("📋 Test 1: Direct access to PDF preview...")
    response = requests.get("http://localhost:5111/api/pdf-positioning/preview/1")
    print(f"   Status: {response.status_code}")
    print(f"   Content-Type: {response.headers.get('Content-Type', 'unknown')}")
    print(f"   Content-Length: {len(response.content)} bytes")
    
    if response.status_code == 302:
        print(f"   Redirect Location: {response.headers.get('Location', 'unknown')}")
        print("   ❌ Authentication required - redirecting to login")
    
    # Test 2: Access with session
    print("\n📋 Test 2: Access with authenticated session...")
    session = requests.Session()
    
    # Login first
    login_data = {'email': 'admin@rfpo.com', 'password': 'admin123'}
    login_response = session.post('http://localhost:5111/login', data=login_data)
    
    print(f"   Login status: {login_response.status_code}")
    
    if login_response.status_code == 200:
        print("   ✅ Login successful")
        
        # Now try PDF preview with session
        pdf_response = session.get("http://localhost:5111/api/pdf-positioning/preview/1")
        print(f"   PDF status: {pdf_response.status_code}")
        print(f"   PDF Content-Type: {pdf_response.headers.get('Content-Type', 'unknown')}")
        print(f"   PDF Content-Length: {len(pdf_response.content)} bytes")
        
        if pdf_response.status_code == 200:
            print("   ✅ PDF generated successfully")
            
            # Save the PDF for inspection
            with open("debug_generated.pdf", "wb") as f:
                f.write(pdf_response.content)
            print("   📄 PDF saved as: debug_generated.pdf")
            
            # Analyze PDF content (basic check)
            pdf_text = pdf_response.content.decode('latin-1', errors='ignore')
            
            # Look for field-related content in PDF
            field_keywords = ['PO NUMBER', 'PO DATE', 'VENDOR', 'DELIVERY', 'PAYMENT']
            found_keywords = []
            
            for keyword in field_keywords:
                if keyword in pdf_text.upper():
                    found_keywords.append(keyword)
            
            print(f"   Field keywords found in PDF: {len(found_keywords)}")
            if found_keywords:
                print(f"      Found: {', '.join(found_keywords)}")
                print("   ❌ PDF contains field content despite clearing!")
            else:
                print("   ✅ No field keywords found - PDF appears clean")
            
            return len(found_keywords) == 0  # True if no fields found
            
        else:
            print(f"   ❌ PDF generation failed: {pdf_response.status_code}")
            print(f"   Response: {pdf_response.text[:200]}")
            return False
    else:
        print("   ❌ Login failed")
        return False

if __name__ == "__main__":
    is_clean = test_pdf_auth()
    
    print(f"\n" + "="*60)
    print("🏆 PDF AUTHENTICATION TEST RESULTS")
    print("="*60)
    
    if is_clean:
        print("✅ PDF PREVIEW IS CLEAN")
        print("   Authentication working, no fields in PDF")
    else:
        print("❌ PDF PREVIEW CONTAINS ELEMENTS!")
        print("   Either auth failed or fields persist in PDF")
        print("   Check debug_generated.pdf for visual confirmation")
    print("="*60)
