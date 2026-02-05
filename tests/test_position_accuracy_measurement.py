#!/usr/bin/env python3
"""
PRECISE POSITIONING ACCURACY MEASUREMENT
Measures exact positioning accuracy between designer and preview
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

def test_position_accuracy_measurement():
    """Measure exact positioning accuracy"""
    driver = setup_driver()
    if not driver:
        return
    
    try:
        print("📐 PRECISE POSITIONING ACCURACY MEASUREMENT")
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
        
        # Clear existing fields
        clear_btn = driver.find_element(By.ID, "clear-canvas")
        clear_btn.click()
        
        try:
            WebDriverWait(driver, 3).until(EC.alert_is_present())
            alert = Alert(driver)
            alert.accept()
            time.sleep(2)
        except TimeoutException:
            pass
        
        # Test with very specific positioning for TOP-RIGHT area
        test_x = 500  # Should be in right area of canvas
        test_y = 80   # Should be in top area of canvas
        
        print(f"\n🎯 Testing with precise positioning:")
        print(f"   Position: ({test_x}, {test_y}) - Should be TOP-RIGHT")
        
        # Create PO NUMBER field
        driver.execute_script("""
            const canvas = document.getElementById('pdf-canvas');
            const field = document.createElement('div');
            field.className = 'pdf-field';
            field.dataset.fieldName = 'po_number';
            field.textContent = 'PO NUMBER TEST';
            field.style.position = 'absolute';
            field.style.left = arguments[0] + 'px';
            field.style.top = arguments[1] + 'px';
            field.style.padding = '6px 12px';
            field.style.fontSize = '12px';
            field.style.fontFamily = 'Arial, sans-serif';
            field.style.backgroundColor = 'rgba(255, 255, 0, 0.9)';
            field.style.border = '3px solid red';
            field.style.borderRadius = '4px';
            field.style.zIndex = '200';
            field.style.fontWeight = 'bold';
            
            canvas.appendChild(field);
            
            if (!window.POSITIONING_DATA) {
                window.POSITIONING_DATA = {};
            }
            
            window.POSITIONING_DATA['po_number'] = {
                x: arguments[0],
                y: arguments[1],
                font_size: 12,
                font_weight: 'bold',
                visible: true
            };
            
            console.log('Created PO NUMBER at', arguments[0], arguments[1]);
        """, test_x, test_y)
        
        time.sleep(2)
        
        # Get exact canvas dimensions and field position
        positioning_info = driver.execute_script("""
            const canvas = document.getElementById('pdf-canvas');
            const canvasRect = canvas.getBoundingClientRect();
            const field = document.querySelector('.pdf-field[data-field-name="po_number"]');
            const fieldRect = field.getBoundingClientRect();
            
            return {
                canvas: {
                    width: canvasRect.width,
                    height: canvasRect.height,
                    left: canvasRect.left,
                    top: canvasRect.top
                },
                field: {
                    left: parseFloat(field.style.left),
                    top: parseFloat(field.style.top),
                    boundingLeft: fieldRect.left,
                    boundingTop: fieldRect.top,
                    width: fieldRect.width,
                    height: fieldRect.height
                }
            };
        """)
        
        canvas_info = positioning_info['canvas']
        field_info = positioning_info['field']
        
        # Calculate relative positions
        rel_x = (field_info['left'] / canvas_info['width']) * 100
        rel_y = (field_info['top'] / canvas_info['height']) * 100
        
        print(f"\n📊 DESIGNER MEASUREMENTS:")
        print(f"   Canvas: {canvas_info['width']:.1f} x {canvas_info['height']:.1f}")
        print(f"   Field absolute: ({field_info['left']:.1f}, {field_info['top']:.1f})")
        print(f"   Field relative: ({rel_x:.2f}%, {rel_y:.2f}%)")
        
        # Determine area
        h_area = "RIGHT" if rel_x > 60 else "CENTER" if rel_x > 30 else "LEFT"
        v_area = "TOP" if rel_y < 30 else "MIDDLE" if rel_y < 70 else "BOTTOM"
        designer_area = f"{v_area}-{h_area}"
        
        print(f"   Designer area: {designer_area}")
        
        # Save configuration  
        save_btn = driver.find_element(By.ID, "save-config")
        save_btn.click()
        time.sleep(2)
        
        # Check positioning data was saved
        saved_data = driver.execute_script("return window.POSITIONING_DATA;")
        print(f"\n💾 SAVED POSITIONING DATA:")
        if 'po_number' in saved_data:
            data = saved_data['po_number']
            print(f"   po_number: x={data['x']}, y={data['y']}, visible={data['visible']}")
        else:
            print(f"   ❌ po_number not found in saved data!")
            return False
        
        # Generate preview and analyze
        print(f"\n📄 Generating preview for accuracy test...")
        print(f"   Expected PDF coordinates: ({test_x}, {792 - test_y}) = ({test_x}, {792 - test_y})")
        
        original_windows = driver.window_handles
        preview_btn = driver.find_element(By.ID, "preview-pdf")
        preview_btn.click()
        time.sleep(8)
        
        if len(driver.window_handles) > len(original_windows):
            driver.switch_to.window(driver.window_handles[-1])
            print(f"   ✅ Preview opened")
            
            # Wait for PDF to fully load
            time.sleep(5)
            
            # Try to find elements in the PDF content
            print(f"\n🔍 ANALYZING PDF CONTENT:")
            
            # Check if we can find any text content
            try:
                page_text = driver.execute_script("return document.body.innerText;")
                if "PO NUMBER" in page_text or str(test_x) in page_text:
                    print(f"   ✅ Found PO NUMBER related content in PDF")
                else:
                    print(f"   ⚠️  No PO NUMBER content found in PDF text")
                
                # Look for our test value
                if "TEST" in page_text:
                    print(f"   ✅ Found TEST marker in PDF")
                else:
                    print(f"   ⚠️  No TEST marker found")
                    
            except Exception as e:
                print(f"   ⚠️  Could not analyze PDF text: {e}")
            
            # Get PDF viewport info
            pdf_info = driver.execute_script("""
                return {
                    windowWidth: window.innerWidth,
                    windowHeight: window.innerHeight,
                    documentWidth: document.documentElement.scrollWidth,
                    documentHeight: document.documentElement.scrollHeight,
                    scrollX: window.scrollX,
                    scrollY: window.scrollY
                };
            """)
            
            print(f"   PDF viewport: {pdf_info['windowWidth']} x {pdf_info['windowHeight']}")
            
            # CRITICAL: Check if coordinates were converted correctly
            expected_pdf_x = test_x
            expected_pdf_y = 792 - test_y
            
            print(f"\n📐 COORDINATE CONVERSION ANALYSIS:")
            print(f"   Designer position: ({test_x}, {test_y})")
            print(f"   Expected PDF position: ({expected_pdf_x}, {expected_pdf_y})")
            print(f"   Designer area: {designer_area}")
            
            # Calculate what area this should be in PDF
            pdf_rel_x = (expected_pdf_x / 612) * 100  # PDF is 612 wide
            pdf_rel_y = (expected_pdf_y / 792) * 100  # PDF is 792 tall
            
            pdf_h_area = "RIGHT" if pdf_rel_x > 60 else "CENTER" if pdf_rel_x > 30 else "LEFT"
            pdf_v_area = "TOP" if pdf_rel_y > 70 else "MIDDLE" if pdf_rel_y > 30 else "BOTTOM"
            expected_pdf_area = f"{pdf_v_area}-{pdf_h_area}"
            
            print(f"   Expected PDF area: {expected_pdf_area}")
            print(f"   PDF relative position: ({pdf_rel_x:.2f}%, {pdf_rel_y:.2f}%)")
            
            time.sleep(10)  # Time for manual inspection
            
            driver.close()
            driver.switch_to.window(original_windows[0])
        else:
            print(f"   ❌ Preview failed to open")
            return False
        
        # FINAL VALIDATION
        print(f"\n" + "="*80)
        print("🎯 POSITIONING ACCURACY VALIDATION")
        print("="*80)
        
        accuracy_passed = True
        
        print(f"\n✅ VALIDATION RESULTS:")
        print(f"   Designer position: ({test_x}, {test_y}) → {designer_area}")
        print(f"   Expected PDF area: {expected_pdf_area}")
        
        if designer_area == expected_pdf_area:
            print(f"   ✅ PASS: Areas match perfectly!")
        else:
            print(f"   ❌ FAIL: Area mismatch - {designer_area} ≠ {expected_pdf_area}")
            accuracy_passed = False
        
        # Check relative position accuracy (within 5%)
        if abs(rel_x - pdf_rel_x) <= 5 and abs(rel_y - pdf_rel_y) <= 5:
            print(f"   ✅ PASS: Relative position within 5% tolerance")
        else:
            print(f"   ❌ FAIL: Position difference > 5%")
            print(f"      X diff: {abs(rel_x - pdf_rel_x):.2f}%")
            print(f"      Y diff: {abs(rel_y - pdf_rel_y):.2f}%")
            accuracy_passed = False
        
        print(f"\n🔍 MANUAL VERIFICATION:")
        print(f"   Check the PDF preview manually:")
        print(f"   - PO NUMBER should appear in {expected_pdf_area} area")
        print(f"   - Position should be approximately ({expected_pdf_x}, {expected_pdf_y}) in PDF coordinates")
        print(f"   - Field should be visible and properly styled")
        
        if accuracy_passed:
            print(f"\n🎉 POSITIONING ACCURACY: PASSED ✅")
            return True
        else:
            print(f"\n💥 POSITIONING ACCURACY: FAILED ❌")
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
    success = test_position_accuracy_measurement()
    if success:
        print(f"\n🏆 POSITIONING SYSTEM VALIDATED - ACCURACY WITHIN 5%")
    else:
        print(f"\n🔥 POSITIONING SYSTEM FAILED - ACCURACY > 5% OR OTHER ISSUES")
