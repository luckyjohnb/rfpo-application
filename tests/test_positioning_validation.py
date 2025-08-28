#!/usr/bin/env python3
"""
COMPREHENSIVE POSITIONING VALIDATION TEST
Tests all 3 issues: click release, dynamic positioning, coordinate translation
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

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

def test_positioning_validation():
    """Test all 3 positioning issues comprehensively"""
    driver = setup_driver()
    if not driver:
        return
    
    try:
        print("🔥 COMPREHENSIVE POSITIONING VALIDATION TEST")
        print("=" * 80)
        print("Testing 3 critical issues:")
        print("1. Element deselection (LOW)")
        print("2. Dynamic positioning (CRITICAL)")
        print("3. Coordinate translation (HIGH)")
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
        
        print("✅ Editor loaded successfully")
        
        # Get canvas dimensions for coordinate analysis
        canvas_info = driver.execute_script("""
            const canvas = document.getElementById('pdf-canvas');
            const canvasRect = canvas.getBoundingClientRect();
            const style = window.getComputedStyle(canvas);
            return {
                width: canvasRect.width,
                height: canvasRect.height,
                backgroundImage: style.backgroundImage,
                backgroundSize: style.backgroundSize
            };
        """)
        
        print(f"\n📐 CANVAS ANALYSIS:")
        print(f"   Canvas size: {canvas_info['width']} x {canvas_info['height']}")
        print(f"   Background: {canvas_info['backgroundImage'][:50]}...")
        print(f"   Background size: {canvas_info['backgroundSize']}")
        
        # Find test element (PO NUMBER)
        test_field = None
        fields = driver.find_elements(By.CSS_SELECTOR, "#pdf-canvas .pdf-field")
        print(f"\n📋 Found {len(fields)} positioned fields")
        
        for field in fields:
            field_name = field.get_attribute('data-field-name')
            if field_name == 'po_number':
                test_field = field
                break
        
        if not test_field:
            print("❌ PO NUMBER field not found - cannot continue test")
            return
        
        print(f"✅ Found test field: PO NUMBER")
        
        # TEST 1: Element deselection (LOW priority)
        print(f"\n🧪 TEST 1: Element Deselection")
        print("=" * 40)
        
        # Click field to select it
        test_field.click()
        time.sleep(1)
        
        # Check if field is selected
        is_selected = driver.execute_script("""
            return document.querySelector('.pdf-field.selected') !== null;
        """)
        
        if is_selected:
            print("✅ Field selected successfully")
            
            # Test Escape key deselection
            driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            time.sleep(1)
            
            is_deselected = driver.execute_script("""
                return document.querySelector('.pdf-field.selected') === null;
            """)
            
            if is_deselected:
                print("✅ PASS: Escape key deselection works")
            else:
                print("❌ FAIL: Escape key deselection doesn't work")
        else:
            print("⚠️  Field selection styling not detected")
        
        # TEST 2: Get initial position for dynamic testing
        print(f"\n🧪 TEST 2: Dynamic Positioning (CRITICAL)")
        print("=" * 40)
        
        initial_pos = driver.execute_script("""
            const field = arguments[0];
            const style = window.getComputedStyle(field);
            return {
                left: parseFloat(style.left),
                top: parseFloat(style.top),
                text: field.textContent.trim()
            };
        """, test_field)
        
        print(f"📍 Initial position: ({initial_pos['left']:.1f}, {initial_pos['top']:.1f})")
        print(f"📝 Field text: '{initial_pos['text']}'")
        
        # Move to Position A (top-left area)
        pos_a_x, pos_a_y = 100, 150
        print(f"\n🎯 Moving to Position A: ({pos_a_x}, {pos_a_y}) - TOP LEFT area")
        
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
        """, test_field, pos_a_x, pos_a_y)
        
        time.sleep(1)
        
        # Verify position A
        pos_a_actual = driver.execute_script("""
            const field = arguments[0];
            const style = window.getComputedStyle(field);
            return {
                left: parseFloat(style.left),
                top: parseFloat(style.top)
            };
        """, test_field)
        
        print(f"✅ Moved to: ({pos_a_actual['left']:.1f}, {pos_a_actual['top']:.1f})")
        
        # Save and preview Position A
        print("💾 Saving Position A...")
        save_btn = driver.find_element(By.ID, "save-config")
        save_btn.click()
        time.sleep(2)
        
        print("📄 Generating Preview A...")
        original_windows = driver.window_handles
        preview_btn = driver.find_element(By.ID, "preview-pdf")
        preview_btn.click()
        time.sleep(5)
        
        preview_a_success = False
        if len(driver.window_handles) > len(original_windows):
            print("✅ Preview A generated")
            driver.switch_to.window(driver.window_handles[-1])
            time.sleep(3)
            print("👀 MANUAL CHECK: PO NUMBER should be in TOP-LEFT area")
            time.sleep(8)
            driver.close()
            driver.switch_to.window(original_windows[0])
            preview_a_success = True
        else:
            print("❌ Preview A failed to generate")
        
        # Move to Position B (bottom-right area)
        pos_b_x, pos_b_y = 450, 600
        print(f"\n🎯 Moving to Position B: ({pos_b_x}, {pos_b_y}) - BOTTOM RIGHT area")
        
        driver.execute_script("""
            const field = arguments[0];
            field.style.left = arguments[1] + 'px';
            field.style.top = arguments[2] + 'px';
            
            // Update positioning data
            const fieldName = field.dataset.fieldName;
            if (window.POSITIONING_DATA && fieldName) {
                window.POSITIONING_DATA[fieldName].x = arguments[1];
                window.POSITIONING_DATA[fieldName].y = arguments[2];
            }
        """, test_field, pos_b_x, pos_b_y)
        
        time.sleep(1)
        
        # Verify position B
        pos_b_actual = driver.execute_script("""
            const field = arguments[0];
            const style = window.getComputedStyle(field);
            return {
                left: parseFloat(style.left),
                top: parseFloat(style.top)
            };
        """, test_field)
        
        print(f"✅ Moved to: ({pos_b_actual['left']:.1f}, {pos_b_actual['top']:.1f})")
        
        # Save and preview Position B
        print("💾 Saving Position B...")
        save_btn.click()
        time.sleep(2)
        
        print("📄 Generating Preview B...")
        preview_btn.click()
        time.sleep(5)
        
        preview_b_success = False
        if len(driver.window_handles) > len(original_windows):
            print("✅ Preview B generated")
            driver.switch_to.window(driver.window_handles[-1])
            time.sleep(3)
            print("👀 MANUAL CHECK: PO NUMBER should be in BOTTOM-RIGHT area (DIFFERENT from Preview A)")
            time.sleep(8)
            driver.close()
            driver.switch_to.window(original_windows[0])
            preview_b_success = True
        else:
            print("❌ Preview B failed to generate")
        
        # TEST 3: Coordinate Translation Analysis
        print(f"\n🧪 TEST 3: Coordinate Translation Analysis (HIGH)")
        print("=" * 40)
        
        # Calculate coordinate ratios
        canvas_width = canvas_info['width']
        canvas_height = canvas_info['height']
        pdf_width = 612  # Standard PDF width in points
        pdf_height = 792  # Standard PDF height in points
        
        print(f"📐 Canvas size: {canvas_width:.1f} x {canvas_height:.1f}")
        print(f"📐 PDF size: {pdf_width} x {pdf_height}")
        print(f"📐 Scale factors: X={pdf_width/canvas_width:.3f}, Y={pdf_height/canvas_height:.3f}")
        
        # Test coordinate conversion
        test_positions = [
            (100, 150, "Top-left"),
            (300, 300, "Center"),
            (450, 600, "Bottom-right")
        ]
        
        print(f"\n🔄 Coordinate Conversion Analysis:")
        for x, y, desc in test_positions:
            # What the current system does
            current_pdf_y = 792 - y
            
            # What it SHOULD do with scaling
            scaled_x = (x / canvas_width) * pdf_width
            scaled_y = pdf_height - ((y / canvas_height) * pdf_height)
            
            print(f"   {desc}: Designer({x}, {y})")
            print(f"      Current PDF: ({x}, {current_pdf_y})")
            print(f"      Scaled PDF:  ({scaled_x:.1f}, {scaled_y:.1f})")
            
            if abs(scaled_x - x) > 10 or abs(scaled_y - current_pdf_y) > 10:
                print(f"      ⚠️  SCALING ISSUE DETECTED!")
        
        # RESULTS SUMMARY
        print(f"\n" + "=" * 80)
        print("🎯 TEST RESULTS SUMMARY")
        print("=" * 80)
        
        print(f"1. Element Deselection (LOW): {'✅ FIXED' if is_deselected else '❌ NEEDS WORK'}")
        print(f"2. Dynamic Positioning (CRITICAL): {'✅ WORKING' if preview_a_success and preview_b_success else '❌ BROKEN'}")
        print(f"3. Coordinate Translation (HIGH): {'⚠️  NEEDS SCALING' if canvas_width != pdf_width else '✅ OK'}")
        
        print(f"\n🔍 MANUAL VALIDATION REQUIRED:")
        print(f"   Did PO NUMBER move between Preview A and Preview B?")
        print(f"   - Preview A: Should be TOP-LEFT area")
        print(f"   - Preview B: Should be BOTTOM-RIGHT area")
        print(f"   If YES: Dynamic positioning works! ✅")
        print(f"   If NO: Dynamic positioning is broken! ❌")
        
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
    test_positioning_validation()
