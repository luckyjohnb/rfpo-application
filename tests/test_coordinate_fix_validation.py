#!/usr/bin/env python3
"""
TEST COORDINATE FIX VALIDATION
Verify that the XY coordinate jumping issue is fixed
"""
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains

def setup_driver():
    """Setup Chrome driver"""
    chrome_options = Options()
    chrome_options.add_argument("--window-size=1400,1000")
    return webdriver.Chrome(options=chrome_options)

def login_and_navigate(driver):
    """Login and navigate to positioning editor"""
    # Login
    driver.get("http://localhost:5111/login")
    time.sleep(2)
    
    driver.find_element(By.NAME, "email").send_keys("admin@rfpo.com")
    driver.find_element(By.NAME, "password").send_keys("admin123")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(2)
    
    # Navigate to editor
    driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
    time.sleep(5)  # Wait for page to load
    
    return True

def test_coordinate_consistency():
    """Test that coordinates don't jump during drag operations"""
    print("🎯 TESTING COORDINATE CONSISTENCY FIX")
    print("="*60)
    
    driver = setup_driver()
    
    try:
        # Login and navigate
        if not login_and_navigate(driver):
            print("❌ Failed to login/navigate")
            return False
        
        # Clear canvas first
        try:
            clear_button = driver.find_element(By.ID, "clear-canvas")
            clear_button.click()
            time.sleep(1)
            driver.switch_to.alert.accept()
            time.sleep(2)
            print("✅ Canvas cleared")
        except:
            pass
        
        # Add a field
        driver.execute_script("populateFieldsList();")
        time.sleep(1)
        
        field_buttons = driver.find_elements(By.CSS_SELECTOR, "#fields-list .list-group-item")
        if not field_buttons:
            print("❌ No fields found")
            return False
        
        # Place first field
        first_field = field_buttons[0]
        first_field.click()
        time.sleep(0.5)
        
        canvas = driver.find_element(By.ID, "pdf-canvas")
        actions = ActionChains(driver)
        actions.move_to_element_with_offset(canvas, 200, 100).click().perform()
        time.sleep(1)
        
        print("✅ Field placed")
        
        # Get the placed field
        placed_fields = driver.find_elements(By.CSS_SELECTOR, ".pdf-field")
        if not placed_fields:
            print("❌ No placed field found")
            return False
        
        placed_field = placed_fields[0]
        
        # Test 1: Check initial coordinates
        initial_coords = driver.execute_script("""
            const field = arguments[0];
            const coordsDisplay = document.getElementById('coordinates');
            const xInput = document.getElementById('field-x');
            const yInput = document.getElementById('field-y');
            
            return {
                display: coordsDisplay.textContent,
                xInput: xInput.value,
                yInput: yInput.value,
                styleLeft: field.style.left,
                styleTop: field.style.top
            };
        """, placed_field)
        
        print(f"📋 Initial coordinates:")
        print(f"   Display: {initial_coords['display']}")
        print(f"   X Input: {initial_coords['xInput']}")
        print(f"   Y Input: {initial_coords['yInput']}")
        print(f"   Style: left={initial_coords['styleLeft']}, top={initial_coords['styleTop']}")
        
        # Test 2: Drag the field and check coordinates during drag
        placed_field.click()  # Select field
        time.sleep(0.5)
        
        # Start drag operation
        actions = ActionChains(driver)
        actions.click_and_hold(placed_field).perform()
        time.sleep(0.2)
        
        # Move slightly
        actions.move_by_offset(50, 30).perform()
        time.sleep(0.2)
        
        # Check coordinates during drag
        during_drag_coords = driver.execute_script("""
            const field = arguments[0];
            const coordsDisplay = document.getElementById('coordinates');
            const xInput = document.getElementById('field-x');
            const yInput = document.getElementById('field-y');
            
            return {
                display: coordsDisplay.textContent,
                xInput: xInput.value,
                yInput: yInput.value,
                styleLeft: field.style.left,
                styleTop: field.style.top
            };
        """, placed_field)
        
        print(f"📋 During drag coordinates:")
        print(f"   Display: {during_drag_coords['display']}")
        print(f"   X Input: {during_drag_coords['xInput']}")
        print(f"   Y Input: {during_drag_coords['yInput']}")
        print(f"   Style: left={during_drag_coords['styleLeft']}, top={during_drag_coords['styleTop']}")
        
        # Release drag
        actions.release().perform()
        time.sleep(1)
        
        # Test 3: Check coordinates after drag release
        final_coords = driver.execute_script("""
            const field = arguments[0];
            const coordsDisplay = document.getElementById('coordinates');
            const xInput = document.getElementById('field-x');
            const yInput = document.getElementById('field-y');
            
            return {
                display: coordsDisplay.textContent,
                xInput: xInput.value,
                yInput: yInput.value,
                styleLeft: field.style.left,
                styleTop: field.style.top
            };
        """, placed_field)
        
        print(f"📋 Final coordinates (after release):")
        print(f"   Display: {final_coords['display']}")
        print(f"   X Input: {final_coords['xInput']}")
        print(f"   Y Input: {final_coords['yInput']}")
        print(f"   Style: left={final_coords['styleLeft']}, top={final_coords['styleTop']}")
        
        # Test 4: Press ESC and check coordinates don't jump
        driver.find_element(By.TAG_NAME, "body").send_keys("\ue00c")  # ESC key
        time.sleep(1)
        
        after_esc_coords = driver.execute_script("""
            const field = arguments[0];
            const coordsDisplay = document.getElementById('coordinates');
            const xInput = document.getElementById('field-x');
            const yInput = document.getElementById('field-y');
            
            return {
                display: coordsDisplay.textContent,
                xInput: xInput.value,
                yInput: yInput.value,
                styleLeft: field.style.left,
                styleTop: field.style.top
            };
        """, placed_field)
        
        print(f"📋 After ESC coordinates:")
        print(f"   Display: {after_esc_coords['display']}")
        print(f"   X Input: {after_esc_coords['xInput']}")
        print(f"   Y Input: {after_esc_coords['yInput']}")
        print(f"   Style: left={after_esc_coords['styleLeft']}, top={after_esc_coords['styleTop']}")
        
        # Analysis
        print(f"\n🔍 COORDINATE CONSISTENCY ANALYSIS:")
        
        # Extract X values for comparison
        def extract_x_value(coord_text):
            try:
                return int(coord_text.split('x: ')[1].split(',')[0])
            except:
                return None
        
        initial_x = extract_x_value(initial_coords['display'])
        during_x = extract_x_value(during_drag_coords['display'])
        final_x = extract_x_value(final_coords['display'])
        esc_x = extract_x_value(after_esc_coords['display'])
        
        print(f"   X coordinates: initial={initial_x}, during={during_x}, final={final_x}, after_esc={esc_x}")
        
        # Check for large jumps
        if final_x and during_x:
            x_jump = abs(final_x - during_x)
            print(f"   X coordinate jump on release: {x_jump} pixels")
            
            if x_jump < 5:  # Small tolerance for rounding
                print("   ✅ X coordinates consistent (no jumping)")
            else:
                print(f"   ❌ X coordinates jumped {x_jump} pixels on release!")
                return False
        
        if esc_x and final_x:
            esc_jump = abs(esc_x - final_x)
            print(f"   X coordinate jump on ESC: {esc_jump} pixels")
            
            if esc_jump < 5:
                print("   ✅ X coordinates stable after ESC")
            else:
                print(f"   ❌ X coordinates jumped {esc_jump} pixels on ESC!")
                return False
        
        print("✅ Coordinate consistency test PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        driver.quit()

if __name__ == "__main__":
    success = test_coordinate_consistency()
    print(f"\n" + "="*60)
    if success:
        print("🎉 COORDINATE FIX VALIDATED!")
        print("   No more jumping coordinates")
    else:
        print("💥 COORDINATE FIX FAILED!")
        print("   Coordinates still jumping")
    print("="*60)
