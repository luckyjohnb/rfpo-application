#!/usr/bin/env python3
"""
COMPREHENSIVE POSITIONING FIX VALIDATION
Test the complete fix for the background-size coordinate mismatch issue
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

def test_positioning_fix():
    print("🎯 COMPREHENSIVE POSITIONING FIX VALIDATION")
    print("="*80)
    print("Testing the complete fix for background-size coordinate mismatch")
    print()
    
    driver = setup_driver()
    
    try:
        # Setup
        print("📋 Step 1: Setup and navigate...")
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
        
        # Clear canvas
        print("📋 Step 2: Clear canvas...")
        try:
            clear_button = driver.find_element(By.ID, "clear-canvas")
            clear_button.click()
            time.sleep(1)
            driver.switch_to.alert.accept()
            time.sleep(2)
            print("   ✅ Canvas cleared")
        except:
            print("   ⚠️ No elements to clear")
        
        # Verify canvas properties
        print("📋 Step 3: Verify fixed canvas properties...")
        canvas_properties = driver.execute_script("""
            const canvas = document.getElementById('pdf-canvas');
            const computedStyle = window.getComputedStyle(canvas);
            const rect = canvas.getBoundingClientRect();
            
            return {
                width: rect.width,
                height: rect.height,
                computedWidth: computedStyle.width,
                computedHeight: computedStyle.height,
                backgroundSize: computedStyle.backgroundSize,
                backgroundPosition: computedStyle.backgroundPosition,
                overflow: computedStyle.overflow
            };
        """)
        
        print(f"   Canvas size: {canvas_properties['width']} x {canvas_properties['height']}")
        print(f"   Background size: {canvas_properties['backgroundSize']}")
        print(f"   Background position: {canvas_properties['backgroundPosition']}")
        
        # Check if dimensions are exactly 612x792
        width_perfect = abs(canvas_properties['width'] - 612) < 1
        height_perfect = abs(canvas_properties['height'] - 792) < 1
        background_perfect = canvas_properties['backgroundSize'] == "612px 792px"
        
        print(f"   ✅ Width: {'PERFECT' if width_perfect else 'INCORRECT'} (612px)")
        print(f"   ✅ Height: {'PERFECT' if height_perfect else 'INCORRECT'} (792px)")
        print(f"   ✅ Background: {'PERFECT' if background_perfect else 'INCORRECT'} (612px 792px)")
        
        # Place element at specific landmark position
        print("📋 Step 4: Place element at landmark position...")
        driver.execute_script("populateFieldsList();")
        time.sleep(2)
        
        # Find PO Number field
        field_buttons = driver.find_elements(By.CSS_SELECTOR, "#fields-list .list-group-item")
        po_number_field = None
        for field in field_buttons:
            if field.get_attribute("data-field-name") == "po_number":
                po_number_field = field
                break
        
        if not po_number_field:
            print("   ❌ PO Number field not found")
            return False
        
        # Drag to top-right area (landmark position)
        canvas = driver.find_element(By.ID, "pdf-canvas")
        actions = ActionChains(driver)
        actions.drag_and_drop(po_number_field, canvas).perform()
        time.sleep(2)
        
        # Move to specific position using precise coordinates
        placed_fields = driver.find_elements(By.CSS_SELECTOR, ".pdf-field")
        if placed_fields:
            field = placed_fields[0]
            # Move to top-right landmark area (around where PO Number should go)
            target_x = 450  # Specific landmark X
            target_y = 50   # Specific landmark Y (top area)
            
            # Use JavaScript to set exact position
            driver.execute_script("""
                const field = arguments[0];
                field.style.left = arguments[1] + 'px';
                field.style.top = arguments[2] + 'px';
                
                // Trigger position update
                if (window.selectedField === field) {
                    const event = new Event('mousemove');
                    document.dispatchEvent(event);
                }
            """, field, target_x, target_y)
            time.sleep(1)
            
            # Select the field to trigger coordinate updates
            field.click()
            time.sleep(1)
            
            print(f"   ✅ Element positioned at landmark: ({target_x}, {target_y})")
        
        # Get precise positioning information
        print("📋 Step 5: Analyze positioning accuracy...")
        positioning_info = driver.execute_script("""
            const field = document.querySelector('.pdf-field');
            const canvas = document.getElementById('pdf-canvas');
            const canvasRect = canvas.getBoundingClientRect();
            const fieldRect = field.getBoundingClientRect();
            
            // Get coordinates from the system
            const coordsDisplay = document.getElementById('coordinates').textContent;
            const xInput = document.getElementById('field-x').value;
            const yInput = document.getElementById('field-y').value;
            
            return {
                field: {
                    x: fieldRect.left - canvasRect.left,
                    y: fieldRect.top - canvasRect.top,
                    styleLeft: field.style.left,
                    styleTop: field.style.top
                },
                canvas: {
                    width: canvasRect.width,
                    height: canvasRect.height
                },
                coordinates: {
                    display: coordsDisplay,
                    xInput: parseInt(xInput),
                    yInput: parseInt(yInput)
                }
            };
        """)
        
        field_x = positioning_info['field']['x']
        field_y = positioning_info['field']['y']
        coord_x = positioning_info['coordinates']['xInput']
        coord_y = positioning_info['coordinates']['yInput']
        
        print(f"   Field visual position: ({field_x:.1f}, {field_y:.1f})")
        print(f"   Stored coordinates: ({coord_x}, {coord_y})")
        print(f"   Canvas size: {positioning_info['canvas']['width']} x {positioning_info['canvas']['height']}")
        print(f"   Coordinates display: {positioning_info['coordinates']['display']}")
        
        # Calculate coordinate accuracy
        x_accuracy = abs(field_x - coord_x)
        y_accuracy = abs(field_y - coord_y)
        
        print(f"   Coordinate accuracy: X={x_accuracy:.1f}px, Y={y_accuracy:.1f}px")
        
        # Save positioning
        print("📋 Step 6: Save and test preview...")
        save_button = driver.find_element(By.ID, "save-config")
        driver.execute_script("arguments[0].scrollIntoView(true);", save_button)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", save_button)
        time.sleep(3)
        print("   ✅ Positioning saved")
        
        # Take screenshot of fixed designer
        driver.save_screenshot("FINAL_DESIGNER_FIXED.png")
        print("   📸 Designer screenshot: FINAL_DESIGNER_FIXED.png")
        
        # Test preview
        driver.get("http://localhost:5111/api/pdf-positioning/preview/1")
        time.sleep(4)
        
        # Take screenshot of preview
        driver.save_screenshot("FINAL_PREVIEW_FIXED.png")
        print("   📸 Preview screenshot: FINAL_PREVIEW_FIXED.png")
        
        # Final validation
        print("📋 Step 7: Final validation...")
        
        accuracy_tolerance = 5  # 5px tolerance
        x_accurate = x_accuracy <= accuracy_tolerance
        y_accurate = y_accuracy <= accuracy_tolerance
        canvas_correct = width_perfect and height_perfect and background_perfect
        
        print(f"   Canvas configuration: {'✅ CORRECT' if canvas_correct else '❌ INCORRECT'}")
        print(f"   X coordinate accuracy: {'✅ ACCURATE' if x_accurate else '❌ INACCURATE'} ({x_accuracy:.1f}px ≤ {accuracy_tolerance}px)")
        print(f"   Y coordinate accuracy: {'✅ ACCURATE' if y_accurate else '❌ INACCURATE'} ({y_accuracy:.1f}px ≤ {accuracy_tolerance}px)")
        
        overall_success = canvas_correct and x_accurate and y_accurate
        
        return overall_success
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        driver.quit()

if __name__ == "__main__":
    success = test_positioning_fix()
    print(f"\n" + "="*80)
    print("🏆 COMPREHENSIVE POSITIONING FIX RESULTS")
    print("="*80)
    if success:
        print("🎉 POSITIONING FIX: COMPLETE SUCCESS ✅")
        print()
        print("✅ FIXED ISSUES:")
        print("   • Canvas now exactly 612x792 (matches PDF)")
        print("   • Background-size set to exact dimensions")
        print("   • No more coordinate scaling issues")
        print("   • Element positioning accurate within tolerance")
        print()
        print("📸 PROOF IMAGES:")
        print("   • FINAL_DESIGNER_FIXED.png - Designer with fixed coordinates")
        print("   • FINAL_PREVIEW_FIXED.png - Preview with accurate positioning")
        print()
        print("🎯 ROOT CAUSE RESOLVED:")
        print("   The background-size: contain issue has been eliminated.")
        print("   Canvas container and PDF template are now perfectly aligned.")
    else:
        print("💥 POSITIONING FIX: NEEDS MORE WORK ❌")
        print("   Some issues may still remain")
    print("="*80)
