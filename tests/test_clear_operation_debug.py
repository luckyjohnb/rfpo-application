#!/usr/bin/env python3
"""
DEBUG CLEAR OPERATION
Step-by-step debugging of the clear operation to find where it fails
"""
import time
import requests
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--window-size=1400,1000")
    return webdriver.Chrome(options=chrome_options)

def debug_clear_operation():
    print("🔍 DEBUG CLEAR OPERATION")
    print("="*80)
    
    driver = setup_driver()
    session = requests.Session()
    
    try:
        # Step 1: Login via both selenium and requests
        print("📋 Step 1: Login...")
        driver.get("http://localhost:5111/login")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "email")))
        
        driver.find_element(By.NAME, "email").send_keys("admin@rfpo.com")
        driver.find_element(By.NAME, "password").send_keys("admin123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)
        
        # Login with requests session too
        login_data = {'email': 'admin@rfpo.com', 'password': 'admin123'}
        session.post('http://localhost:5111/login', data=login_data)
        print("   ✅ Logged in")
        
        # Step 2: Navigate to designer and check initial state
        print("📋 Step 2: Check initial positioning data...")
        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "pdf-canvas")))
        time.sleep(5)
        
        # Check initial positioning data via API
        api_response = session.get("http://localhost:5111/api/pdf-positioning/1")
        if api_response.status_code == 200:
            initial_data = api_response.json()
            print(f"   Initial positioning data keys: {list(initial_data.get('positioning_data', {}).keys())}")
            print(f"   Initial data length: {len(initial_data.get('positioning_data', {}))}")
        else:
            print(f"   ❌ Failed to get initial data: {api_response.status_code}")
        
        # Check frontend positioning data
        frontend_data = driver.execute_script("return window.POSITIONING_DATA || {};")
        print(f"   Frontend positioning data keys: {list(frontend_data.keys())}")
        print(f"   Frontend data length: {len(frontend_data)}")
        
        # Step 3: Perform clear operation
        print("📋 Step 3: Perform clear operation...")
        try:
            clear_button = driver.find_element(By.ID, "clear-canvas")
            clear_button.click()
            time.sleep(1)
            driver.switch_to.alert.accept()
            time.sleep(3)  # Wait for save operation
            print("   ✅ Clear operation completed")
        except Exception as e:
            print(f"   ❌ Clear operation failed: {e}")
            return False
        
        # Step 4: Check positioning data after clear
        print("📋 Step 4: Check positioning data after clear...")
        
        # Check frontend data
        frontend_data_after = driver.execute_script("return window.POSITIONING_DATA || {};")
        print(f"   Frontend data after clear: {frontend_data_after}")
        print(f"   Frontend keys count: {len(frontend_data_after)}")
        
        # Check API data
        api_response_after = session.get("http://localhost:5111/api/pdf-positioning/1")
        if api_response_after.status_code == 200:
            api_data_after = api_response_after.json()
            positioning_after = api_data_after.get('positioning_data', {})
            print(f"   API data after clear: {positioning_after}")
            print(f"   API keys count: {len(positioning_after)}")
            
            if len(positioning_after) == 0:
                print("   ✅ API data cleared successfully")
            else:
                print("   ❌ API data still contains elements!")
                for key, value in positioning_after.items():
                    print(f"      {key}: {value}")
        else:
            print(f"   ❌ Failed to get API data after clear: {api_response_after.status_code}")
        
        # Step 5: Test PDF generation with cleared data
        print("📋 Step 5: Test PDF generation after clear...")
        pdf_response = session.get("http://localhost:5111/api/pdf-positioning/preview/1")
        
        if pdf_response.status_code == 200:
            print(f"   PDF generated: {len(pdf_response.content)} bytes")
            
            # Save for inspection
            with open("debug_clear_pdf.pdf", "wb") as f:
                f.write(pdf_response.content)
            print("   📄 PDF saved as: debug_clear_pdf.pdf")
            
            # Check PDF content
            pdf_text = pdf_response.content.decode('latin-1', errors='ignore')
            field_keywords = ['PO NUMBER', 'PO DATE', 'VENDOR', 'DELIVERY', 'PAYMENT', 'PROJECT']
            found_keywords = [kw for kw in field_keywords if kw in pdf_text.upper()]
            
            print(f"   Field keywords in PDF: {len(found_keywords)}")
            if found_keywords:
                print(f"      Found: {', '.join(found_keywords)}")
                print("   ❌ PDF still contains field content!")
                return False
            else:
                print("   ✅ PDF is clean - no field content found")
                return True
        else:
            print(f"   ❌ PDF generation failed: {pdf_response.status_code}")
            return False
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        driver.quit()

def test_manual_clear_api():
    """Test clearing positioning data directly via API"""
    print("\n🔧 MANUAL API CLEAR TEST")
    print("="*50)
    
    session = requests.Session()
    
    # Login
    login_data = {'email': 'admin@rfpo.com', 'password': 'admin123'}
    session.post('http://localhost:5111/login', data=login_data)
    
    # Clear positioning data manually
    clear_payload = {"positioning_data": {}}
    response = session.post(
        "http://localhost:5111/api/pdf-positioning/1",
        json=clear_payload,
        headers={'Content-Type': 'application/json'}
    )
    
    print(f"   Clear API response: {response.status_code}")
    if response.status_code == 200:
        print(f"   Response: {response.json()}")
        
        # Verify it was cleared
        verify_response = session.get("http://localhost:5111/api/pdf-positioning/1")
        if verify_response.status_code == 200:
            verify_data = verify_response.json()
            positioning_data = verify_data.get('positioning_data', {})
            print(f"   Verified data: {positioning_data}")
            
            if len(positioning_data) == 0:
                print("   ✅ Manual API clear successful")
                
                # Test PDF after manual clear
                pdf_response = session.get("http://localhost:5111/api/pdf-positioning/preview/1")
                if pdf_response.status_code == 200:
                    pdf_text = pdf_response.content.decode('latin-1', errors='ignore')
                    field_keywords = ['PO NUMBER', 'PO DATE', 'VENDOR', 'DELIVERY', 'PAYMENT']
                    found_keywords = [kw for kw in field_keywords if kw in pdf_text.upper()]
                    
                    with open("debug_manual_clear_pdf.pdf", "wb") as f:
                        f.write(pdf_response.content)
                    
                    print(f"   PDF after manual clear: {len(pdf_response.content)} bytes")
                    print(f"   Field keywords found: {len(found_keywords)}")
                    if found_keywords:
                        print(f"      Found: {', '.join(found_keywords)}")
                        print("   ❌ PDF still has fields after manual clear!")
                        return False
                    else:
                        print("   ✅ PDF clean after manual clear")
                        return True
                else:
                    print("   ❌ PDF generation failed after manual clear")
                    return False
            else:
                print("   ❌ Manual API clear failed")
                return False
    else:
        print(f"   ❌ Clear API failed: {response.text}")
        return False

if __name__ == "__main__":
    print("🎯 DEBUGGING CLEAR OPERATION BUG")
    print("="*80)
    
    # Test 1: Debug browser clear operation
    browser_clear_works = debug_clear_operation()
    
    # Test 2: Test manual API clear
    api_clear_works = test_manual_clear_api()
    
    print(f"\n" + "="*80)
    print("🏆 CLEAR OPERATION DEBUG RESULTS")
    print("="*80)
    print(f"   Browser clear works: {'✅' if browser_clear_works else '❌'}")
    print(f"   Manual API clear works: {'✅' if api_clear_works else '❌'}")
    
    if not browser_clear_works and not api_clear_works:
        print("\n💥 CRITICAL: Both clear methods fail!")
        print("   The issue is in the PDF generation logic")
        print("   PDF generator is not respecting empty positioning data")
    elif not browser_clear_works and api_clear_works:
        print("\n🔧 Issue is in browser clear operation")
        print("   The frontend clear → save workflow has a bug")
    elif browser_clear_works and api_clear_works:
        print("\n✅ Clear operations work correctly!")
    
    print(f"\n📄 Check generated PDFs:")
    print(f"   - debug_clear_pdf.pdf (browser clear)")
    print(f"   - debug_manual_clear_pdf.pdf (API clear)")
    print("="*80)
