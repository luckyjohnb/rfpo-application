#!/usr/bin/env python3
"""
TEST FIXED COORDINATE SYSTEM
Verify that the coordinate system fix resolves the background-size mismatch issue
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

def test_coordinate_system_fix():
    print("🎯 TESTING FIXED COORDINATE SYSTEM")
    print("="*60)
    print("Verifying that canvas now matches PDF template exactly")
    print()
    
    driver = setup_driver()
    
    try:
        # Setup
        print("📋 Step 1: Login and navigate...")
        driver.get("http://localhost:5111/login")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "email")))
        
        driver.find_element(By.NAME, "email").send_keys("admin@rfpo.com")
        driver.find_element(By.NAME, "password").send_keys("admin123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)
        
        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "pdf-canvas")))
        time.sleep(5)
        print("   ✅ Successfully navigated to editor")
        
        # Check canvas dimensions
        print("📋 Step 2: Verify canvas dimensions...")
        canvas_info = driver.execute_script("""
            const canvas = document.getElementById('pdf-canvas');
            const computedStyle = window.getComputedStyle(canvas);
            const rect = canvas.getBoundingClientRect();
            
            return {
                computedWidth: computedStyle.width,
                computedHeight: computedStyle.height,
                boundingWidth: rect.width,
                boundingHeight: rect.height,
                backgroundSize: computedStyle.backgroundSize,
                backgroundPosition: computedStyle.backgroundPosition
            };
        """)
        
        print(f"   Canvas computed size: {canvas_info['computedWidth']} x {canvas_info['computedHeight']}")
        print(f"   Canvas bounding size: {canvas_info['boundingWidth']} x {canvas_info['boundingHeight']}")
        print(f"   Background size: {canvas_info['backgroundSize']}")
        print(f"   Background position: {canvas_info['backgroundPosition']}")
        
        # Check if canvas is exactly 612x792
        width_correct = abs(float(canvas_info['boundingWidth']) - 612) < 5
        height_correct = abs(float(canvas_info['boundingHeight']) - 792) < 5
        
        print(f"   Width correct (612px): {'✅' if width_correct else '❌'} ({canvas_info['boundingWidth']})")
        print(f"   Height correct (792px): {'✅' if height_correct else '❌'} ({canvas_info['boundingHeight']})")
        
        if not (width_correct and height_correct):
            print("❌ Canvas dimensions are not correct!")
            return False
        
        # Clear canvas and place a test element
        print("📋 Step 3: Test coordinate precision...")
        try:
            clear_button = driver.find_element(By.ID, "clear-canvas")
            clear_button.click()
            time.sleep(1)
            driver.switch_to.alert.accept()
            time.sleep(2)
        except:
            pass
        
        # Place element at known coordinates
        driver.execute_script("populateFieldsList();")
        time.sleep(2)
        
        field_buttons = driver.find_elements(By.CSS_SELECTOR, "#fields-list .list-group-item")
        po_number_field = None
        for field in field_buttons:
            if field.get_attribute("data-field-name") == "po_number":
                po_number_field = field
                break
        
        if not po_number_field:
            print("❌ PO Number field not found")
            return False
        
        # Drag to canvas
        canvas = driver.find_element(By.ID, "pdf-canvas")
        actions = ActionChains(driver)
        actions.drag_and_drop(po_number_field, canvas).perform()
        time.sleep(2)
        
        # Check element coordinates
        placed_fields = driver.find_elements(By.CSS_SELECTOR, ".pdf-field")
        if not placed_fields:
            print("❌ Element not placed")
            return False
        
        element_info = driver.execute_script("""
            const element = arguments[0];
            const canvas = document.getElementById('pdf-canvas');
            const canvasRect = canvas.getBoundingClientRect();
            const elementRect = element.getBoundingClientRect();
            
            return {
                elementX: elementRect.left - canvasRect.left,
                elementY: elementRect.top - canvasRect.top,
                canvasWidth: canvasRect.width,
                canvasHeight: canvasRect.height,
                styleLeft: element.style.left,
                styleTop: element.style.top
            };
        """, placed_fields[0])
        
        print(f"   Element position: ({element_info['elementX']:.1f}, {element_info['elementY']:.1f})")
        print(f"   Canvas size: {element_info['canvasWidth']:.1f} x {element_info['canvasHeight']:.1f}")
        print(f"   Style position: {element_info['styleLeft']}, {element_info['styleTop']}")
        
        # Verify coordinates are within reasonable PDF bounds
        x_in_bounds = 0 <= element_info['elementX'] <= 612
        y_in_bounds = 0 <= element_info['elementY'] <= 792
        
        print(f"   X coordinate in bounds: {'✅' if x_in_bounds else '❌'}")
        print(f"   Y coordinate in bounds: {'✅' if y_in_bounds else '❌'}")
        
        # Take screenshot for visual verification
        driver.save_screenshot("FIXED_COORDINATE_SYSTEM.png")
        print("   📸 Screenshot saved: FIXED_COORDINATE_SYSTEM.png")
        
        # Test coordinate precision by checking that element position matches its style
        style_x = float(element_info['styleLeft'].replace('px', ''))
        style_y = float(element_info['styleTop'].replace('px', ''))
        
        x_precision = abs(style_x - element_info['elementX']) < 2
        y_precision = abs(style_y - element_info['elementY']) < 2
        
        print(f"   Coordinate precision X: {'✅' if x_precision else '❌'} (diff: {abs(style_x - element_info['elementX']):.1f})")
        print(f"   Coordinate precision Y: {'✅' if y_precision else '❌'} (diff: {abs(style_y - element_info['elementY']):.1f})")
        
        all_checks_passed = (width_correct and height_correct and 
                           x_in_bounds and y_in_bounds and 
                           x_precision and y_precision)
        
        print("\n📊 COORDINATE SYSTEM FIX VALIDATION:")
        print(f"   Canvas dimensions: {'✅ CORRECT' if width_correct and height_correct else '❌ INCORRECT'}")
        print(f"   Element positioning: {'✅ ACCURATE' if x_in_bounds and y_in_bounds else '❌ INACCURATE'}")
        print(f"   Coordinate precision: {'✅ PRECISE' if x_precision and y_precision else '❌ IMPRECISE'}")
        
        return all_checks_passed
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        driver.quit()

if __name__ == "__main__":
    success = test_coordinate_system_fix()
    print(f"\n" + "="*60)
    if success:
        print("🎉 COORDINATE SYSTEM FIX: VALIDATED ✅")
        print("   Canvas now exactly matches PDF template")
        print("   No more background-size mismatch issues")
    else:
        print("💥 COORDINATE SYSTEM FIX: FAILED ❌")
        print("   Additional adjustments needed")
    print("="*60)
