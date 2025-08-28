#!/usr/bin/env python3
"""
SIMPLE DRAG AND DROP TEST
Test basic drag and drop functionality
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

def test_drag_drop():
    print("🎯 TESTING SIMPLE DRAG AND DROP")
    print("="*50)
    
    driver = setup_driver()
    
    try:
        # Login and navigate
        print("1. Setting up...")
        driver.get("http://localhost:5111/login")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "email")))
        
        driver.find_element(By.NAME, "email").send_keys("admin@rfpo.com")
        driver.find_element(By.NAME, "password").send_keys("admin123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)
        
        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "pdf-canvas")))
        time.sleep(5)
        
        # Clear canvas
        try:
            clear_button = driver.find_element(By.ID, "clear-canvas")
            clear_button.click()
            time.sleep(1)
            driver.switch_to.alert.accept()
            time.sleep(2)
        except:
            pass
        
        # Populate fields
        driver.execute_script("populateFieldsList();")
        time.sleep(2)
        
        # Get field and canvas
        field_buttons = driver.find_elements(By.CSS_SELECTOR, "#fields-list .list-group-item")
        canvas = driver.find_element(By.ID, "pdf-canvas")
        
        if not field_buttons:
            print("❌ No fields found")
            return False
        
        first_field = field_buttons[0]
        field_name = first_field.get_attribute("data-field-name")
        print(f"2. Dragging field: {field_name}")
        
        # Simple drag and drop directly to canvas center
        actions = ActionChains(driver)
        actions.drag_and_drop(first_field, canvas).perform()
        time.sleep(3)
        
        # Check result
        placed_fields = driver.find_elements(By.CSS_SELECTOR, ".pdf-field")
        print(f"3. Result: {len(placed_fields)} fields placed")
        
        if placed_fields:
            print("✅ SUCCESS - Field placed!")
            
            # Get field details
            field_info = driver.execute_script("""
                const field = arguments[0];
                const canvas = document.getElementById('pdf-canvas');
                const canvasRect = canvas.getBoundingClientRect();
                const fieldRect = field.getBoundingClientRect();
                
                return {
                    fieldName: field.dataset.fieldName,
                    text: field.textContent,
                    position: {
                        x: fieldRect.left - canvasRect.left,
                        y: fieldRect.top - canvasRect.top
                    },
                    style: {
                        left: field.style.left,
                        top: field.style.top
                    }
                };
            """, placed_fields[0])
            
            print(f"   Field: {field_info['fieldName']}")
            print(f"   Text: '{field_info['text']}'")
            print(f"   Position: ({field_info['position']['x']:.1f}, {field_info['position']['y']:.1f})")
            print(f"   Style: {field_info['style']['left']}, {field_info['style']['top']}")
            
            # Save positioning
            save_button = driver.find_element(By.ID, "save-config")
            driver.execute_script("arguments[0].scrollIntoView(true);", save_button)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", save_button)
            time.sleep(3)
            print("   ✅ Positioning saved")
            
            # Take screenshot
            driver.save_screenshot("test_successful_placement.png")
            print("   📸 Screenshot: test_successful_placement.png")
            
            return True
        else:
            print("❌ FAILED - No field placed")
            driver.save_screenshot("test_failed_placement.png")
            print("   📸 Screenshot: test_failed_placement.png")
            return False
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        driver.quit()

if __name__ == "__main__":
    success = test_drag_drop()
    print(f"\n{'🎉 DRAG DROP WORKS!' if success else '💥 DRAG DROP FAILED!'}")
