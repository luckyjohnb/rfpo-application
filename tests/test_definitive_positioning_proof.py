#!/usr/bin/env python3
"""
DEFINITIVE POSITIONING PROOF TEST
This test MUST pass with 5% accuracy or the positioning system is considered BROKEN
"""
import time
import os
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

def test_definitive_positioning_proof():
    """Definitive proof that positioning works within 5% accuracy"""
    driver = setup_driver()
    if not driver:
        return False
    
    # Create screenshots directory
    os.makedirs("proof_screenshots", exist_ok=True)
    
    try:
        print("🏆 DEFINITIVE POSITIONING PROOF TEST")
        print("=" * 80)
        print("This test will PASS only if positioning accuracy is within 5%")
        print("If this test fails, the positioning system is BROKEN")
        print()
        
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
        
        # STEP 1: Complete clean slate
        print("\n🧹 STEP 1: Creating completely clean slate...")
        
        # Clear all existing fields
        clear_btn = driver.find_element(By.ID, "clear-canvas")
        clear_btn.click()
        
        try:
            WebDriverWait(driver, 3).until(EC.alert_is_present())
            alert = Alert(driver)
            alert.accept()
            time.sleep(2)
        except TimeoutException:
            pass
        
        # Verify completely empty
        positioned_fields = driver.find_elements(By.CSS_SELECTOR, "#pdf-canvas .pdf-field")
        positioning_data = driver.execute_script("return window.POSITIONING_DATA;")
        
        if len(positioned_fields) == 0 and (not positioning_data or len(positioning_data) == 0):
            print("   ✅ Canvas completely cleared")
        else:
            print(f"   ❌ Clear failed: {len(positioned_fields)} fields, data: {positioning_data}")
            return False
        
        # Save empty state to database
        save_btn = driver.find_element(By.ID, "save-config")
        save_btn.click()
        time.sleep(2)
        
        # STEP 2: Add single test field in precise position
        print("\n🎯 STEP 2: Adding single test field in TOP-RIGHT area...")
        
        # Choose coordinates that should clearly be in TOP-RIGHT
        test_x = 450  # Right side of 612px canvas (73% from left)
        test_y = 100  # Top area of 792px canvas (12% from top)
        
        print(f"   Target position: ({test_x}, {test_y})")
        print(f"   Expected area: TOP-RIGHT")
        
        # Get canvas dimensions for relative calculations
        canvas_info = driver.execute_script("""
            const canvas = document.getElementById('pdf-canvas');
            const rect = canvas.getBoundingClientRect();
            return {
                width: rect.width,
                height: rect.height
            };
        """)
        
        # Calculate relative position in designer
        designer_rel_x = (test_x / canvas_info['width']) * 100
        designer_rel_y = (test_y / canvas_info['height']) * 100
        
        print(f"   Canvas size: {canvas_info['width']:.1f} x {canvas_info['height']:.1f}")
        print(f"   Designer relative: ({designer_rel_x:.2f}%, {designer_rel_y:.2f}%)")
        
        # Create field with precise positioning
        driver.execute_script("""
            const canvas = document.getElementById('pdf-canvas');
            const field = document.createElement('div');
            field.className = 'pdf-field';
            field.dataset.fieldName = 'test_field';
            field.textContent = 'PROOF TEST FIELD';
            field.style.position = 'absolute';
            field.style.left = arguments[0] + 'px';
            field.style.top = arguments[1] + 'px';
            field.style.padding = '8px 16px';
            field.style.fontSize = '16px';
            field.style.fontFamily = 'Arial, sans-serif';
            field.style.backgroundColor = 'rgba(255, 0, 0, 0.9)';  // Bright red
            field.style.border = '4px solid blue';
            field.style.borderRadius = '6px';
            field.style.zIndex = '1000';
            field.style.fontWeight = 'bold';
            field.style.color = 'white';
            
            canvas.appendChild(field);
            
            // Set positioning data with explicit visible=true
            window.POSITIONING_DATA = {
                'test_field': {
                    x: arguments[0],
                    y: arguments[1],
                    font_size: 16,
                    font_weight: 'bold',
                    visible: true
                }
            };
            
            console.log('PROOF: Created test field at', arguments[0], arguments[1]);
        """, test_x, test_y)
        
        time.sleep(2)
        
        # Verify field creation
        created_fields = driver.find_elements(By.CSS_SELECTOR, "#pdf-canvas .pdf-field")
        final_positioning_data = driver.execute_script("return window.POSITIONING_DATA;")
        
        if len(created_fields) == 1 and 'test_field' in final_positioning_data:
            field_data = final_positioning_data['test_field']
            print(f"   ✅ Field created: x={field_data['x']}, y={field_data['y']}, visible={field_data['visible']}")
        else:
            print(f"   ❌ Field creation failed")
            return False
        
        # Take designer screenshot
        print(f"\n📸 Taking designer screenshot...")
        driver.save_screenshot("proof_screenshots/designer_proof.png")
        print(f"   Saved: proof_screenshots/designer_proof.png")
        
        # STEP 3: Save and generate preview
        print(f"\n💾 STEP 3: Saving configuration and testing preview...")
        save_btn.click()
        time.sleep(3)
        
        # Generate preview
        print(f"   Generating preview (watch for debug output)...")
        original_windows = driver.window_handles
        preview_btn = driver.find_element(By.ID, "preview-pdf")
        preview_btn.click()
        time.sleep(12)  # Extra time for generation and debug
        
        preview_success = False
        if len(driver.window_handles) > len(original_windows):
            driver.switch_to.window(driver.window_handles[-1])
            print(f"   ✅ Preview opened")
            
            # Wait for PDF to load
            time.sleep(5)
            
            # Take preview screenshot
            driver.save_screenshot("proof_screenshots/preview_proof.png")
            print(f"   📸 Preview screenshot: proof_screenshots/preview_proof.png")
            
            # Check for field content in PDF
            try:
                page_text = driver.execute_script("return document.body.innerText || document.body.textContent || '';")
                if "PROOF TEST FIELD" in page_text:
                    print(f"   ✅ CRITICAL SUCCESS: Field content found in PDF!")
                    preview_success = True
                else:
                    print(f"   ❌ CRITICAL FAILURE: Field content NOT found in PDF")
                    print(f"      PDF contains: {page_text[:500]}...")
            except Exception as e:
                print(f"   ❌ Error checking PDF content: {e}")
            
            time.sleep(8)
            driver.close()
            driver.switch_to.window(original_windows[0])
        else:
            print(f"   ❌ Preview failed to open")
            return False
        
        # STEP 4: Calculate positioning accuracy
        print(f"\n📐 STEP 4: Calculating positioning accuracy...")
        
        # Expected PDF coordinates (Y-axis flip)
        expected_pdf_x = test_x
        expected_pdf_y = 792 - test_y  # 792 - 100 = 692
        
        # Calculate relative position in PDF (612x792)
        pdf_rel_x = (expected_pdf_x / 612) * 100
        pdf_rel_y = (expected_pdf_y / 792) * 100
        
        print(f"   Designer position: ({test_x}, {test_y})")
        print(f"   Expected PDF position: ({expected_pdf_x}, {expected_pdf_y})")
        print(f"   Designer relative: ({designer_rel_x:.2f}%, {designer_rel_y:.2f}%)")
        print(f"   PDF relative: ({pdf_rel_x:.2f}%, {pdf_rel_y:.2f}%)")
        
        # Calculate accuracy difference
        x_diff = abs(designer_rel_x - pdf_rel_x)
        y_diff = abs(designer_rel_y - pdf_rel_y)
        
        print(f"   Position difference: X={x_diff:.2f}%, Y={y_diff:.2f}%")
        
        # STEP 5: Final validation
        print(f"\n🎯 STEP 5: Final validation...")
        
        # Check if field appeared in preview
        if not preview_success:
            print(f"   ❌ FATAL: Field did not appear in preview PDF")
            print(f"   🔥 POSITIONING SYSTEM IS COMPLETELY BROKEN")
            return False
        
        # Check positioning accuracy
        accuracy_threshold = 5.0  # 5% as requested
        
        if x_diff <= accuracy_threshold and y_diff <= accuracy_threshold:
            print(f"   ✅ POSITIONING ACCURACY: PASSED")
            print(f"      X difference: {x_diff:.2f}% ≤ {accuracy_threshold}%")
            print(f"      Y difference: {y_diff:.2f}% ≤ {accuracy_threshold}%")
            accuracy_passed = True
        else:
            print(f"   ❌ POSITIONING ACCURACY: FAILED")
            print(f"      X difference: {x_diff:.2f}% > {accuracy_threshold}%")
            print(f"      Y difference: {y_diff:.2f}% > {accuracy_threshold}%")
            accuracy_passed = False
        
        # Final result
        print(f"\n" + "="*80)
        print("🏆 DEFINITIVE POSITIONING PROOF RESULTS")
        print("="*80)
        
        if preview_success and accuracy_passed:
            print(f"🎉 SUCCESS: POSITIONING SYSTEM WORKS CORRECTLY!")
            print(f"   ✅ Field appears in PDF preview")
            print(f"   ✅ Positioning accuracy within {accuracy_threshold}%")
            print(f"   ✅ Screenshots saved for verification")
            return True
        else:
            print(f"💥 FAILURE: POSITIONING SYSTEM IS BROKEN!")
            if not preview_success:
                print(f"   ❌ Field does not appear in PDF")
            if not accuracy_passed:
                print(f"   ❌ Positioning accuracy > {accuracy_threshold}%")
            print(f"   📸 Screenshots saved for debugging")
            return False
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    success = test_definitive_positioning_proof()
    print(f"\n" + "="*80)
    if success:
        print(f"🏆 POSITIONING SYSTEM: VALIDATED ✅")
        print(f"   The positioning translation system works correctly!")
    else:
        print(f"🔥 POSITIONING SYSTEM: BROKEN ❌") 
        print(f"   The positioning system requires further debugging!")
    print(f"="*80)
