#!/usr/bin/env python3
"""
Debug why positioning is completely failing - check every step of the data flow
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

def test_debug_positioning_failure():
    """Debug complete positioning failure"""
    driver = setup_driver()
    if not driver:
        return
    
    try:
        print("🚨 DEBUGGING COMPLETE POSITIONING FAILURE")
        print("=" * 80)
        
        # Login and navigate
        driver.get("http://localhost:5111/")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "email")))
        driver.find_element(By.NAME, "email").send_keys("admin@rfpo.com")
        driver.find_element(By.NAME, "password").send_keys("admin123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "pdf-canvas")))
        time.sleep(3)
        print("✅ Editor loaded")
        
        # 1. CHECK POSITIONED FIELDS IN DESIGNER
        print("\n📋 STEP 1: Checking positioned fields in designer...")
        positioned_fields = driver.find_elements(By.CSS_SELECTOR, "#pdf-canvas .pdf-field")
        
        if len(positioned_fields) == 0:
            print("   ❌ NO positioned fields found in designer!")
            return
        
        print(f"   ✅ Found {len(positioned_fields)} positioned fields")
        
        # Get details of first few fields
        for i, field in enumerate(positioned_fields[:5]):
            field_info = driver.execute_script("""
                const field = arguments[0];
                const style = window.getComputedStyle(field);
                return {
                    fieldName: field.dataset.fieldName,
                    text: field.textContent.trim(),
                    left: parseFloat(style.left),
                    top: parseFloat(style.top),
                    display: style.display,
                    visible: field.dataset.visible !== 'false'
                };
            """, field)
            print(f"      {i+1}. {field_info['fieldName']}: '{field_info['text']}' at ({field_info['left']:.1f}, {field_info['top']:.1f}) visible={field_info['visible']}")
        
        # 2. CHECK JAVASCRIPT POSITIONING DATA
        print("\n💾 STEP 2: Checking JavaScript POSITIONING_DATA...")
        positioning_data = driver.execute_script("return POSITIONING_DATA;")
        
        visible_fields = {k: v for k, v in positioning_data.items() if v.get('visible', True)}
        hidden_fields = {k: v for k, v in positioning_data.items() if not v.get('visible', True)}
        
        print(f"   Visible fields in POSITIONING_DATA: {len(visible_fields)}")
        print(f"   Hidden fields in POSITIONING_DATA: {len(hidden_fields)}")
        
        # Show a few visible fields
        for i, (field_name, data) in enumerate(list(visible_fields.items())[:3]):
            print(f"      {i+1}. {field_name}: x={data.get('x')}, y={data.get('y')}, visible={data.get('visible', True)}")
        
        # 3. MANUAL SAVE TO ENSURE DATA IS IN DATABASE
        print("\n💾 STEP 3: Manually saving configuration...")
        save_btn = driver.find_element(By.ID, "save-config")
        save_btn.click()
        time.sleep(3)
        print("   ✅ Save completed")
        
        # 4. CHECK WHAT'S ACTUALLY IN THE DATABASE VIA BACKEND LOGS
        print("\n🔍 STEP 4: Testing preview to see backend logs...")
        
        # Click preview and immediately check backend
        preview_btn = driver.find_element(By.ID, "preview-pdf")
        print("   Clicking preview to trigger backend PDF generation...")
        
        original_windows = driver.window_handles
        preview_btn.click()
        time.sleep(5)
        
        # Check if preview opened
        new_windows = driver.window_handles
        if len(new_windows) > len(original_windows):
            print("   ✅ Preview opened")
            driver.close()  # Close preview tab
            driver.switch_to.window(original_windows[0])
        else:
            print("   ❌ Preview failed to open")
        
        # 5. CHECK FOR SPECIFIC PROBLEM AREAS
        print("\n🔍 STEP 5: Checking for specific issues...")
        
        # Check if positioning_config is being passed correctly
        config_check = driver.execute_script("return CONFIG_ID;")
        print(f"   CONFIG_ID: {config_check}")
        
        # Check visible status of key fields
        key_fields = ['po_number', 'po_date', 'ship_to_name', 'total', 'subtotal']
        print(f"\n   Key field visibility in POSITIONING_DATA:")
        for field in key_fields:
            if field in positioning_data:
                data = positioning_data[field]
                print(f"      {field}: visible={data.get('visible', True)}, x={data.get('x')}, y={data.get('y')}")
            else:
                print(f"      {field}: NOT FOUND in positioning data")
        
        # 6. TEST COORDINATE CONVERSION MANUALLY
        print("\n🔄 STEP 6: Testing coordinate conversion...")
        test_fields = ['po_number', 'po_date']
        for field_name in test_fields:
            if field_name in positioning_data:
                screen_y = positioning_data[field_name].get('y', 0)
                pdf_y = 792 - screen_y
                print(f"   {field_name}: screen_y={screen_y} -> pdf_y={pdf_y}")
                
                # Check if these are reasonable coordinates
                if pdf_y < 0 or pdf_y > 792:
                    print(f"      ❌ {field_name} PDF Y coordinate {pdf_y} is out of bounds!")
                elif pdf_y > 700:  # Top area of PDF
                    print(f"      ✅ {field_name} should appear in top area of PDF")
                else:
                    print(f"      ⚠️  {field_name} will appear in lower area of PDF")
        
        # 7. CHECK IF FIELDS ARE ACTUALLY HIDDEN BY CSS
        print("\n👁️ STEP 7: Checking if fields are visually hidden...")
        hidden_count = 0
        for field in positioned_fields:
            is_hidden = driver.execute_script("""
                const field = arguments[0];
                const style = window.getComputedStyle(field);
                return style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0';
            """, field)
            if is_hidden:
                hidden_count += 1
        
        print(f"   {hidden_count} out of {len(positioned_fields)} fields are visually hidden")
        
        # 8. FINAL DIAGNOSIS
        print("\n" + "=" * 80)
        print("🔥 DIAGNOSIS:")
        print("=" * 80)
        
        if len(positioned_fields) > 0 and len(visible_fields) > 0:
            print("✅ Fields are positioned in designer and marked visible in data")
            print("❌ BUT they're not appearing in PDF preview")
            print("\n💡 LIKELY CAUSES:")
            print("   1. Coordinate conversion issue (fields positioned outside visible area)")
            print("   2. PDF generator not receiving/using positioning_config correctly")
            print("   3. Fields being overwritten by default positioning")
            print("   4. Text rendering issue (transparent text, wrong layer)")
        else:
            print("❌ FUNDAMENTAL DATA ISSUE:")
            print("   - Fields missing from designer or positioning data")
        
        print("\n🎯 NEXT STEPS TO TRY:")
        print("   1. Check server logs for coordinate conversion debug messages")
        print("   2. Verify positioning_config is passed to PDF generator")
        print("   3. Test with extreme coordinates to see if anything appears")
        print("   4. Check if PDF generator is using fallback defaults instead")
        
        time.sleep(10)
        
    except Exception as e:
        print(f"❌ Error during debug: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        driver.quit()

if __name__ == "__main__":
    test_debug_positioning_failure()
