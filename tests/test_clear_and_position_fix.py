#!/usr/bin/env python3
"""
Test the critical fix for cleared fields and positioning
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.alert import Alert
from selenium.common.exceptions import TimeoutException

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

def test_clear_and_position_fix():
    """Test the fix for cleared fields and accurate positioning"""
    driver = setup_driver()
    if not driver:
        return
    
    try:
        print("🔧 TESTING CRITICAL CLEAR AND POSITIONING FIX")
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
        
        # TEST 1: Clear everything and verify empty preview
        print("\n🧹 TEST 1: Clear All Fields")
        print("-" * 40)
        
        # Clear all fields
        clear_btn = driver.find_element(By.ID, "clear-canvas")
        clear_btn.click()
        
        try:
            WebDriverWait(driver, 3).until(EC.alert_is_present())
            alert = Alert(driver)
            alert.accept()
            time.sleep(2)
        except TimeoutException:
            pass
        
        # Verify cleared in designer
        positioned_fields = driver.find_elements(By.CSS_SELECTOR, "#pdf-canvas .pdf-field")
        print(f"   Fields in designer: {len(positioned_fields)}")
        
        # Save cleared state
        save_btn = driver.find_element(By.ID, "save-config")
        save_btn.click()
        time.sleep(2)
        
        # Test cleared preview
        print("   Generating cleared preview...")
        original_windows = driver.window_handles
        preview_btn = driver.find_element(By.ID, "preview-pdf")
        preview_btn.click()
        time.sleep(8)
        
        if len(driver.window_handles) > len(original_windows):
            driver.switch_to.window(driver.window_handles[-1])
            print("   ✅ Preview generated for cleared state")
            print("   👀 VERIFY: No positioned fields should appear in PDF")
            print("      (Check for phantom elements - should be NONE)")
            time.sleep(8)
            driver.close()
            driver.switch_to.window(original_windows[0])
        
        # TEST 2: Add specific positioned fields
        print("\n🎯 TEST 2: Add Positioned Fields")
        print("-" * 40)
        
        # Add PO NUMBER in top-right area
        print("   Adding PO NUMBER at position (500, 50) - TOP RIGHT")
        driver.execute_script("""
            const canvas = document.getElementById('pdf-canvas');
            const field = document.createElement('div');
            field.className = 'pdf-field';
            field.dataset.fieldName = 'po_number';
            field.textContent = 'PO NUMBER';
            field.style.position = 'absolute';
            field.style.left = '500px';
            field.style.top = '50px';
            field.style.padding = '4px 8px';
            field.style.fontSize = '9px';
            field.style.fontFamily = 'Arial, sans-serif';
            field.style.backgroundColor = 'rgba(255, 255, 0, 0.9)';
            field.style.border = '2px solid red';
            field.style.borderRadius = '3px';
            field.style.zIndex = '200';
            
            canvas.appendChild(field);
            
            if (!window.POSITIONING_DATA) {
                window.POSITIONING_DATA = {};
            }
            
            window.POSITIONING_DATA['po_number'] = {
                x: 500,
                y: 50,
                font_size: 9,
                font_weight: 'normal',
                visible: true
            };
        """)
        
        # Add PO DATE in top-right area
        print("   Adding PO DATE at position (500, 90) - TOP RIGHT")
        driver.execute_script("""
            const canvas = document.getElementById('pdf-canvas');
            const field = document.createElement('div');
            field.className = 'pdf-field';
            field.dataset.fieldName = 'po_date';
            field.textContent = 'PO DATE';
            field.style.position = 'absolute';
            field.style.left = '500px';
            field.style.top = '90px';
            field.style.padding = '4px 8px';
            field.style.fontSize = '9px';
            field.style.fontFamily = 'Arial, sans-serif';
            field.style.backgroundColor = 'rgba(255, 255, 0, 0.9)';
            field.style.border = '2px solid red';
            field.style.borderRadius = '3px';
            field.style.zIndex = '200';
            
            canvas.appendChild(field);
            
            window.POSITIONING_DATA['po_date'] = {
                x: 500,
                y: 90,
                font_size: 9,
                font_weight: 'normal',
                visible: true
            };
        """)
        
        time.sleep(2)
        
        # Verify fields in designer
        new_fields = driver.find_elements(By.CSS_SELECTOR, "#pdf-canvas .pdf-field")
        print(f"   Fields now in designer: {len(new_fields)}")
        
        # Show positioning data
        positioning_data = driver.execute_script("return window.POSITIONING_DATA;")
        print("   Positioning data:")
        for field_name, data in positioning_data.items():
            if field_name in ['po_number', 'po_date']:
                print(f"      {field_name}: x={data.get('x')}, y={data.get('y')}, visible={data.get('visible')}")
        
        # Save positioned state
        save_btn.click()
        time.sleep(3)
        
        # Test positioned preview
        print("   Generating positioned preview...")
        print("   🔍 Watch server console for positioning debug!")
        
        original_windows = driver.window_handles
        preview_btn.click()
        time.sleep(10)
        
        if len(driver.window_handles) > len(original_windows):
            driver.switch_to.window(driver.window_handles[-1])
            print("   ✅ Preview generated for positioned fields")
            
            # Calculate expected PDF positions
            # PO NUMBER: Designer(500, 50) → PDF(500, 742)
            # PO DATE: Designer(500, 90) → PDF(500, 702)
            print("\n   👀 CRITICAL VERIFICATION:")
            print("      PO NUMBER should be at PDF coordinates (500, 742) - TOP RIGHT")
            print("      PO DATE should be at PDF coordinates (500, 702) - TOP RIGHT")
            print("      Both should appear in TOP-RIGHT area of PDF")
            print("      NO other fields should appear (cleared state working)")
            
            time.sleep(12)
            driver.close()
            driver.switch_to.window(original_windows[0])
        
        print(f"\n" + "="*80)
        print("🎯 FINAL VALIDATION")
        print("="*80)
        print("If the fix worked correctly:")
        print("✅ Test 1: Cleared preview shows NO positioned elements")
        print("✅ Test 2: Positioned elements appear in TOP-RIGHT area of PDF")
        print("✅ No phantom/extra elements in either preview")
        print()
        print("If issues remain:")
        print("❌ Phantom elements in cleared preview = positioning data not cleared")
        print("❌ Wrong positions in positioned preview = coordinate conversion broken")
        print("❌ Missing elements = positioning pipeline broken")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    test_clear_and_position_fix()
