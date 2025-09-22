#!/usr/bin/env python3
"""
MANUAL TEST FOR POSITIONING FIX
Simple script to verify the positioning synchronization fix works
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains

def manual_test_positioning_fix():
    print("🔧 MANUAL TEST: POSITIONING SYNCHRONIZATION FIX")
    print("=" * 60)
    print("This test will:")
    print("1. Login to the admin")
    print("2. Open the PDF positioning editor")
    print("3. Drop a field and move it")
    print("4. Generate preview to verify position")
    print()
    input("Press Enter to start the test...")
    
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
        
        print("\n🎯 MANUAL TEST INSTRUCTIONS:")
        print("1. Clear the canvas using the 'Clear All' button")
        print("2. Drag the 'PO Number' field from the right panel to the canvas")
        print("3. Note the initial position")
        print("4. Click and drag the field to move it to a new position")
        print("5. Click 'Save Configuration'")
        print("6. Click 'Preview PDF' to see if the field appears in the moved position")
        print("7. Check the browser console for positioning debug messages")
        print()
        print("🔍 LOOK FOR:")
        print("- Console messages starting with '🔧 FIXING VISUAL POSITION'")
        print("- Console messages starting with '🔄 Refreshing all field positions'")
        print("- Field should appear in preview at the MOVED position, not initial position")
        print()
        input("Press Enter when you've completed the manual test...")
        
        print("🎯 Manual test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Test setup failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        print("Closing browser in 5 seconds...")
        time.sleep(5)
        driver.quit()

if __name__ == "__main__":
    manual_test_positioning_fix()
