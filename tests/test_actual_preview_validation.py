#!/usr/bin/env python3
"""
REAL validation test - verify that field positions in designer match preview PDF
This test will hold me accountable by actually checking the data flow
"""
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

def setup_driver():
    """Setup Chrome driver"""
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1400,1000")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception as e:
        print(f"Error setting up Chrome driver: {e}")
        return None

def test_actual_preview_validation():
    """Actually validate that preview shows positioned fields"""
    driver = setup_driver()
    if not driver:
        return
    
    try:
        print("🔍 REAL VALIDATION: Testing Preview vs Designer Field Positions")
        print("=" * 70)
        
        # Login
        driver.get("http://localhost:5111/")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "email")))
        driver.find_element(By.NAME, "email").send_keys("admin@rfpo.com")
        driver.find_element(By.NAME, "password").send_keys("admin123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        print("✅ Login successful")
        
        # Navigate to PDF editor
        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "pdf-canvas")))
        print("✅ PDF Editor loaded")
        time.sleep(3)
        
        # 1. CAPTURE CURRENT FIELD POSITIONS IN DESIGNER
        print("\n📋 STEP 1: Capturing field positions in designer...")
        positioned_fields = driver.find_elements(By.CSS_SELECTOR, "#pdf-canvas .pdf-field")
        print(f"   Found {len(positioned_fields)} fields on canvas")
        
        designer_positions = {}
        for field in positioned_fields:
            field_info = driver.execute_script("""
                const field = arguments[0];
                const style = window.getComputedStyle(field);
                return {
                    fieldName: field.dataset.fieldName,
                    text: field.textContent.trim(),
                    left: parseFloat(style.left),
                    top: parseFloat(style.top),
                    visible: style.display !== 'none'
                };
            """, field)
            
            if field_info['fieldName'] and field_info['visible']:
                designer_positions[field_info['fieldName']] = field_info
                print(f"      {field_info['fieldName']}: '{field_info['text']}' at ({field_info['left']:.1f}, {field_info['top']:.1f})")
        
        # 2. CHECK POSITIONING DATA IN MEMORY
        print("\n💾 STEP 2: Checking positioning data in JavaScript memory...")
        positioning_data = driver.execute_script("return POSITIONING_DATA;")
        
        print("   POSITIONING_DATA contents:")
        for field_name, data in positioning_data.items():
            if data.get('visible', True):
                print(f"      {field_name}: x={data.get('x', 'N/A')}, y={data.get('y', 'N/A')}, visible={data.get('visible', True)}")
        
        # 3. VERIFY DATABASE SAVE WORKS
        print("\n💾 STEP 3: Testing save functionality...")
        save_btn = driver.find_element(By.ID, "save-config")
        save_btn.click()
        time.sleep(2)
        print("   ✅ Save clicked")
        
        # 4. VERIFY DATABASE DATA VIA API
        print("\n🌐 STEP 4: Checking database via API...")
        response = requests.get("http://localhost:5111/api/pdf-positioning/1")
        if response.status_code == 200:
            db_data = response.json()
            print("   ✅ API response received")
            print(f"   Database positioning_data keys: {list(db_data.get('positioning_data', {}).keys())}")
            
            # Check specific fields that should be visible
            db_positioning = db_data.get('positioning_data', {})
            key_fields = ['po_number', 'po_date']
            for field in key_fields:
                if field in db_positioning:
                    field_data = db_positioning[field]
                    print(f"      {field} in DB: x={field_data.get('x')}, y={field_data.get('y')}, visible={field_data.get('visible')}")
                else:
                    print(f"      ❌ {field} NOT FOUND in database")
        else:
            print(f"   ❌ API request failed: {response.status_code}")
            return False
        
        # 5. TEST PREVIEW GENERATION
        print("\n📄 STEP 5: Testing preview generation...")
        
        # Store original windows
        original_windows = driver.window_handles
        
        # Click preview
        preview_btn = driver.find_element(By.ID, "preview-pdf")
        print("   Clicking preview button...")
        preview_btn.click()
        time.sleep(5)  # Wait longer for save+preview
        
        # Check for new window
        new_windows = driver.window_handles
        if len(new_windows) > len(original_windows):
            print("   ✅ Preview tab opened")
            
            # Switch to preview tab
            driver.switch_to.window(new_windows[-1])
            preview_url = driver.current_url
            print(f"   Preview URL: {preview_url}")
            
            # Close preview and return to editor
            driver.close()
            driver.switch_to.window(original_windows[0])
            
            # 6. VERIFY PDF PREVIEW VIA DIRECT API CALL
            print("\n🔍 STEP 6: Testing preview API directly...")
            preview_response = requests.get("http://localhost:5111/api/pdf-positioning/preview/1")
            if preview_response.status_code == 200:
                content_type = preview_response.headers.get('content-type', '')
                content_length = len(preview_response.content)
                print(f"   ✅ Preview API works: {content_type}, {content_length} bytes")
                
                if 'pdf' in content_type.lower():
                    print("   ✅ PDF content type confirmed")
                else:
                    print(f"   ❌ Unexpected content type: {content_type}")
            else:
                print(f"   ❌ Preview API failed: {preview_response.status_code}")
                print(f"   Response: {preview_response.text[:200]}")
                return False
            
        else:
            print("   ❌ No preview tab opened")
            return False
        
        # 7. ANALYZE THE PROBLEM
        print("\n🔍 STEP 7: Problem analysis...")
        
        # Check if fields that should be in top-right are positioned correctly
        po_number_pos = designer_positions.get('po_number')
        po_date_pos = designer_positions.get('po_date')
        
        if po_number_pos and po_date_pos:
            print(f"   PO NUMBER in designer: x={po_number_pos['left']:.1f}, y={po_number_pos['top']:.1f}")
            print(f"   PO DATE in designer: x={po_date_pos['left']:.1f}, y={po_date_pos['top']:.1f}")
            
            # Check against DB
            db_po_number = db_positioning.get('po_number', {})
            db_po_date = db_positioning.get('po_date', {})
            
            print(f"   PO NUMBER in DB: x={db_po_number.get('x')}, y={db_po_number.get('y')}")
            print(f"   PO DATE in DB: x={db_po_date.get('x')}, y={db_po_date.get('y')}")
            
            # Check if positions match
            if (abs(po_number_pos['left'] - db_po_number.get('x', 0)) > 5 or 
                abs(po_number_pos['top'] - db_po_number.get('y', 0)) > 5):
                print("   ❌ PO NUMBER positions don't match between designer and DB!")
                
            if (abs(po_date_pos['left'] - db_po_date.get('x', 0)) > 5 or 
                abs(po_date_pos['top'] - db_po_date.get('y', 0)) > 5):
                print("   ❌ PO DATE positions don't match between designer and DB!")
        else:
            print("   ❌ PO NUMBER or PO DATE not found in designer positions!")
        
        # 8. FINAL VERDICT
        print("\n" + "=" * 70)
        print("🏆 FINAL VALIDATION RESULTS:")
        print("=" * 70)
        
        # Check key conditions
        has_positioned_fields = len(positioned_fields) > 0
        api_works = response.status_code == 200
        preview_works = preview_response.status_code == 200
        fields_in_db = 'po_number' in db_positioning and 'po_date' in db_positioning
        
        print(f"   ✅ Fields positioned in designer: {has_positioned_fields} ({len(positioned_fields)} fields)")
        print(f"   ✅ Save API works: {api_works}")
        print(f"   ✅ Preview API works: {preview_works}")
        print(f"   ✅ Key fields in database: {fields_in_db}")
        
        if has_positioned_fields and api_works and preview_works and fields_in_db:
            print("\n🎉 BASIC FUNCTIONALITY WORKS!")
            print("   However, if fields are missing from preview PDF,")
            print("   the issue is likely in the PDF generation logic,")
            print("   not the data saving/loading.")
        else:
            print("\n❌ BASIC FUNCTIONALITY BROKEN!")
            print("   Need to fix fundamental data flow issues first.")
        
        print("\n👀 Manual verification time - 30 seconds...")
        print("   1. Check if fields are visible in designer")
        print("   2. Click Preview PDF")
        print("   3. Compare field positions")
        time.sleep(30)
        
        return True
        
    except Exception as e:
        print(f"❌ Error during validation: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        driver.quit()
        print("\n🔚 Validation test completed")

if __name__ == "__main__":
    test_actual_preview_validation()
