#!/usr/bin/env python3
"""
DEBUG ELEMENT PLACEMENT
Step-by-step debugging to understand why elements aren't being placed
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--window-size=1400,1000")
    return webdriver.Chrome(options=chrome_options)

def debug_field_placement():
    print("🔍 DEBUGGING ELEMENT PLACEMENT")
    print("="*50)
    
    driver = setup_driver()
    
    try:
        # Login
        print("1. Logging in...")
        driver.get("http://localhost:5111/login")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "email")))
        
        driver.find_element(By.NAME, "email").send_keys("admin@rfpo.com")
        driver.find_element(By.NAME, "password").send_keys("admin123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)
        
        # Navigate to editor
        print("2. Navigating to editor...")
        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "pdf-canvas")))
        time.sleep(5)
        
        # Clear canvas
        print("3. Clearing canvas...")
        try:
            clear_button = driver.find_element(By.ID, "clear-canvas")
            clear_button.click()
            time.sleep(1)
            driver.switch_to.alert.accept()
            time.sleep(2)
            print("   ✅ Canvas cleared")
        except Exception as e:
            print(f"   ⚠️ Clear failed: {e}")
        
        # Check initial state
        print("4. Checking initial state...")
        initial_fields = driver.find_elements(By.CSS_SELECTOR, ".pdf-field")
        print(f"   Fields on canvas: {len(initial_fields)}")
        
        # Populate fields list
        print("5. Populating fields list...")
        driver.execute_script("populateFieldsList();")
        time.sleep(2)
        
        # Check fields list
        field_buttons = driver.find_elements(By.CSS_SELECTOR, "#fields-list .list-group-item")
        print(f"   Available fields: {len(field_buttons)}")
        
        if field_buttons:
            for i, field in enumerate(field_buttons[:5]):  # Show first 5
                field_name = field.get_attribute("data-field-name")
                field_text = field.text[:50]
                print(f"     Field {i+1}: {field_name} - '{field_text}'")
        
        if not field_buttons:
            print("   ❌ No fields available!")
            return False
        
        # Try to place first field
        print("6. Attempting to place field...")
        first_field = field_buttons[0]
        field_name = first_field.get_attribute("data-field-name")
        print(f"   Selected field: {field_name}")
        
        # Use proper drag and drop
        print("   6a. Getting canvas...")
        canvas = driver.find_element(By.ID, "pdf-canvas")
        canvas_info = driver.execute_script("""
            const canvas = document.getElementById('pdf-canvas');
            const rect = canvas.getBoundingClientRect();
            return {
                width: rect.width,
                height: rect.height,
                left: rect.left,
                top: rect.top
            };
        """)
        print(f"   Canvas: {canvas_info}")
        
        # Drag field to canvas
        print("   6b. Dragging field to canvas...")
        target_x = 200  # Simple position
        target_y = 100
        print(f"   Target: ({target_x}, {target_y})")
        
        actions = ActionChains(driver)
        actions.drag_and_drop_by_offset(first_field, target_x, target_y).perform()
        time.sleep(2)
        
        print("   6c. Alternative method - drag and drop to element...")
        # Try alternative method
        actions = ActionChains(driver)
        actions.click_and_hold(first_field).move_to_element_with_offset(canvas, target_x, target_y).release().perform()
        time.sleep(2)
        
        # Check result
        print("7. Checking placement result...")
        placed_fields = driver.find_elements(By.CSS_SELECTOR, ".pdf-field")
        print(f"   Fields after placement: {len(placed_fields)}")
        
        if placed_fields:
            field = placed_fields[0]
            field_info = driver.execute_script("""
                const field = arguments[0];
                const canvas = document.getElementById('pdf-canvas');
                const canvasRect = canvas.getBoundingClientRect();
                const fieldRect = field.getBoundingClientRect();
                
                return {
                    fieldName: field.dataset.fieldName,
                    text: field.textContent,
                    style: {
                        left: field.style.left,
                        top: field.style.top
                    },
                    position: {
                        x: fieldRect.left - canvasRect.left,
                        y: fieldRect.top - canvasRect.top
                    }
                };
            """, field)
            print(f"   ✅ Field placed: {field_info}")
            
            # Take a screenshot
            driver.save_screenshot("debug_placement_success.png")
            print("   📸 Screenshot saved: debug_placement_success.png")
            return True
        else:
            print("   ❌ No field was placed")
            
            # Take screenshot for debugging
            driver.save_screenshot("debug_placement_failed.png")
            print("   📸 Screenshot saved: debug_placement_failed.png")
            
            # Check console errors
            logs = driver.get_log('browser')
            if logs:
                print("   Browser console errors:")
                for log in logs[-5:]:  # Last 5 errors
                    print(f"     {log['level']}: {log['message']}")
            
            return False
    
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        driver.quit()

if __name__ == "__main__":
    success = debug_field_placement()
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}")
