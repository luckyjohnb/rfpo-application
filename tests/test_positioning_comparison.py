#!/usr/bin/env python3
"""
TEST POSITIONING COMPARISON - DESIGNER VS PREVIEW
This will capture screenshots to compare positions
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
import os

def test_positioning_comparison():
    print("📸 CAPTURING DESIGNER VS PREVIEW POSITIONING")
    print("=" * 60)
    
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1400,900")
    
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)
    
    try:
        print("📋 Step 1: Login to admin...")
        driver.get("http://localhost:5111/login")
        time.sleep(2)
        
        # Login
        email_field = driver.find_element(By.NAME, "email")
        password_field = driver.find_element(By.NAME, "password")
        email_field.send_keys("admin@rfpo.com")
        password_field.send_keys("admin123")
        
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        login_button.click()
        time.sleep(3)
        
        print("✅ Login successful")
        
        print("📋 Step 2: Navigate to PDF positioning editor...")
        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        time.sleep(5)
        
        # Wait for canvas to load
        canvas = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "pdf-canvas"))
        )
        print("✅ Canvas loaded")
        
        # Wait for fields list to populate
        fields_list = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "fields-list"))
        )
        time.sleep(2)
        
        print("📋 Step 3: Clear canvas and add PO Number field...")
        
        # Clear canvas first
        clear_btn = driver.find_element(By.ID, "clear-canvas")
        clear_btn.click()
        time.sleep(1)
        
        # Accept confirmation
        driver.switch_to.alert.accept()
        time.sleep(2)
        
        # Take screenshot of empty designer
        driver.save_screenshot("empty_designer.png")
        print("📸 Captured: empty_designer.png")
        
        # Drag PO Number field to canvas at specific position
        po_number_item = driver.find_element(By.XPATH, "//div[@data-field-name='po_number']")
        canvas_element = driver.find_element(By.ID, "pdf-canvas")
        
        # Get canvas bounds
        canvas_location = canvas_element.location
        canvas_size = canvas_element.size
        
        # Drop at specific position within canvas (middle-ish)
        drop_x = canvas_location['x'] + 200
        drop_y = canvas_location['y'] + 150
        
        print(f"   Canvas: {canvas_location} Size: {canvas_size}")
        print(f"   Dropping at: ({drop_x}, {drop_y})")
        
        ActionChains(driver).click_and_hold(po_number_item).move_to_element_with_offset(
            canvas_element, 200, 150
        ).release().perform()
        time.sleep(3)
        
        # Take screenshot after initial drop
        driver.save_screenshot("after_initial_drop.png")
        print("📸 Captured: after_initial_drop.png")
        
        # Find the created field and get its position
        test_field = driver.find_element(By.CSS_SELECTOR, "[data-field-name='po_number']")
        initial_location = test_field.location
        print(f"   Initial field location: {initial_location}")
        
        print("📋 Step 4: Move field to new position...")
        
        # Click and drag to new position
        new_drop_x = canvas_location['x'] + 400
        new_drop_y = canvas_location['y'] + 300
        
        print(f"   Moving to: ({new_drop_x}, {new_drop_y})")
        
        ActionChains(driver).click_and_hold(test_field).move_to_element_with_offset(
            canvas_element, 400, 300
        ).release().perform()
        time.sleep(3)
        
        # Take screenshot after move
        driver.save_screenshot("after_move.png")
        print("📸 Captured: after_move.png")
        
        # Get new position
        moved_location = test_field.location
        print(f"   Moved field location: {moved_location}")
        
        # Save configuration
        save_btn = driver.find_element(By.ID, "save-config")
        save_btn.click()
        time.sleep(3)
        
        # Get positioning data from JavaScript
        positioning_data = driver.execute_script("return window.POSITIONING_DATA;")
        po_data = positioning_data.get('po_number', {}) if positioning_data else {}
        print(f"   Stored positioning data: {po_data}")
        
        print("📋 Step 5: Generate preview...")
        
        # Generate preview
        original_windows = driver.window_handles
        preview_btn = driver.find_element(By.ID, "preview-pdf")
        preview_btn.click()
        time.sleep(5)
        
        if len(driver.window_handles) > len(original_windows):
            # Switch to preview window
            driver.switch_to.window(driver.window_handles[-1])
            time.sleep(3)
            
            # Take screenshot of preview
            driver.save_screenshot("preview_result.png")
            print("📸 Captured: preview_result.png")
            
            # Close preview window
            driver.close()
            driver.switch_to.window(original_windows[0])
        else:
            print("⚠️  Preview window didn't open")
        
        print("\n🎯 COMPARISON ANALYSIS:")
        print("=" * 40)
        print(f"Initial drop location: {initial_location}")
        print(f"After move location: {moved_location}")
        print(f"Stored PDF coords: {po_data}")
        print()
        print("📸 Screenshots captured:")
        print("  - empty_designer.png")
        print("  - after_initial_drop.png") 
        print("  - after_move.png")
        print("  - preview_result.png")
        print()
        print("🔍 Check these files to see:")
        print("  1. If field moves correctly in designer")
        print("  2. If preview shows field at moved position")
        print("  3. Position accuracy between designer and preview")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        driver.quit()

if __name__ == "__main__":
    test_positioning_comparison()
