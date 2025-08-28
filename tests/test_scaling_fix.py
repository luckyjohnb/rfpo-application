#!/usr/bin/env python3
"""
Test the coordinate scaling fix
"""
import time
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

def test_scaling_fix():
    """Test coordinate scaling fix"""
    driver = setup_driver()
    if not driver:
        return
    
    try:
        print("🔧 TESTING COORDINATE SCALING FIX")
        print("=" * 60)
        
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
        
        # Find PO NUMBER field
        test_field = None
        fields = driver.find_elements(By.CSS_SELECTOR, "#pdf-canvas .pdf-field")
        for field in fields:
            if field.get_attribute('data-field-name') == 'po_number':
                test_field = field
                break
        
        if not test_field:
            print("❌ PO NUMBER field not found")
            return
        
        # Test scaling with known positions
        test_positions = [
            (100, 150, "Top-left corner"),
            (400, 300, "Center-right area"),
            (200, 800, "Bottom area")
        ]
        
        for i, (x, y, desc) in enumerate(test_positions):
            print(f"\n🎯 Test Position {i+1}: {desc}")
            print(f"   Designer coordinates: ({x}, {y})")
            
            # Calculate expected PDF coordinates with scaling
            canvas_width, canvas_height = 827, 1070
            pdf_width, pdf_height = 612, 792
            scale_x = pdf_width / canvas_width
            scale_y = pdf_height / canvas_height
            expected_pdf_x = x * scale_x
            expected_pdf_y = pdf_height - (y * scale_y)
            
            print(f"   Expected PDF coordinates: ({expected_pdf_x:.1f}, {expected_pdf_y:.1f})")
            
            # Move field to test position
            driver.execute_script("""
                const field = arguments[0];
                field.style.left = arguments[1] + 'px';
                field.style.top = arguments[2] + 'px';
                
                // Update positioning data
                const fieldName = field.dataset.fieldName;
                if (window.POSITIONING_DATA && fieldName) {
                    window.POSITIONING_DATA[fieldName].x = arguments[1];
                    window.POSITIONING_DATA[fieldName].y = arguments[2];
                    window.POSITIONING_DATA[fieldName].visible = true;
                }
            """, test_field, x, y)
            
            time.sleep(1)
            
            # Save and preview
            save_btn = driver.find_element(By.ID, "save-config")
            save_btn.click()
            time.sleep(2)
            
            print(f"   📄 Generating preview (check server console for scaling debug)")
            original_windows = driver.window_handles
            preview_btn = driver.find_element(By.ID, "preview-pdf")
            preview_btn.click()
            time.sleep(5)
            
            if len(driver.window_handles) > len(original_windows):
                driver.switch_to.window(driver.window_handles[-1])
                
                # Check relative position
                if y < 300:
                    expected_area = "TOP"
                elif y < 600:
                    expected_area = "MIDDLE"  
                else:
                    expected_area = "BOTTOM"
                
                if x < 200:
                    expected_area += "-LEFT"
                elif x < 400:
                    expected_area += "-CENTER"
                else:
                    expected_area += "-RIGHT"
                
                print(f"   👀 MANUAL CHECK: PO NUMBER should be in {expected_area} area")
                time.sleep(5)
                
                driver.close()
                driver.switch_to.window(original_windows[0])
            else:
                print(f"   ❌ Preview failed")
        
        print(f"\n🎯 SCALING VALIDATION:")
        print(f"   If PO NUMBER moved between different areas (TOP-LEFT, CENTER-RIGHT, BOTTOM)")
        print(f"   in the previews, then scaling is working correctly!")
        print(f"   If PO NUMBER stayed in same area, scaling needs more work.")
        print(f"\n📊 Check server console for debug output:")
        print(f"   - Canvas dimensions detection")
        print(f"   - Scale factor calculations")
        print(f"   - Position conversion messages")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        driver.quit()

if __name__ == "__main__":
    test_scaling_fix()
