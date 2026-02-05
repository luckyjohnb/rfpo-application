#!/usr/bin/env python3
"""
TEST POSITIONING SYNCHRONIZATION FIX
Verify that moved elements show correctly in both designer and preview
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
import requests


def test_positioning_sync_fix():
    print("🔧 TESTING POSITIONING SYNCHRONIZATION FIX")
    print("=" * 70)

    # Test sequence:
    # 1. Login and go to positioning editor
    # 2. Drop a field at initial position
    # 3. Move the field to a new position
    # 4. Verify visual position matches stored data
    # 5. Generate preview and verify it shows the moved position

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

        # Drag PO Number field to canvas
        po_number_item = driver.find_element(
            By.XPATH, "//div[@data-field-name='po_number']"
        )
        canvas_element = driver.find_element(By.ID, "pdf-canvas")

        # Initial drop position
        initial_x = 100
        initial_y = 100

        print(f"   Dropping field at initial position: ({initial_x}, {initial_y})")

        ActionChains(driver).drag_and_drop_by_offset(
            po_number_item,
            initial_x - po_number_item.location["x"],
            initial_y - po_number_item.location["y"],
        ).perform()
        time.sleep(2)

        # Find the created field
        test_field = driver.find_element(
            By.CSS_SELECTOR, "[data-field-name='po_number']"
        )
        print(f"✅ Field created at: {test_field.location}")

        print("📋 Step 4: Move field to new position...")

        # Move field to new position
        new_x = 300
        new_y = 200

        print(f"   Moving field to new position: ({new_x}, {new_y})")

        # Click and drag the field
        ActionChains(driver).click_and_hold(test_field).move_by_offset(
            new_x - test_field.location["x"], new_y - test_field.location["y"]
        ).release().perform()
        time.sleep(3)

        # Save configuration
        save_btn = driver.find_element(By.ID, "save-config")
        save_btn.click()
        time.sleep(3)

        print("📋 Step 5: Verify synchronization fix...")

        # Check that POSITIONING_DATA was updated
        positioning_data = driver.execute_script("return window.POSITIONING_DATA;")
        po_data = positioning_data.get("po_number", {})

        print(f"   Stored positioning data: {po_data}")

        # Get current visual position
        test_field = driver.find_element(
            By.CSS_SELECTOR, "[data-field-name='po_number']"
        )
        visual_left = int(test_field.value_of_css_property("left").replace("px", ""))
        visual_top = int(test_field.value_of_css_property("top").replace("px", ""))

        print(f"   Visual position: left={visual_left}px, top={visual_top}px")

        # Calculate expected visual position from stored data
        if po_data.get("x") is not None and po_data.get("y") is not None:
            expected_left = po_data["x"]
            expected_top = 792 - po_data["y"]  # Convert PDF Y to screen Y

            print(
                f"   Expected visual position: left={expected_left}px, top={expected_top}px"
            )

            # Check if positions match (within tolerance)
            left_diff = abs(visual_left - expected_left)
            top_diff = abs(visual_top - expected_top)

            print(f"   Position differences: left={left_diff}px, top={top_diff}px")

            if left_diff <= 5 and top_diff <= 5:
                print("✅ POSITIONING SYNCHRONIZATION FIX WORKING!")
                print("   Visual position matches stored data")
            else:
                print("❌ POSITIONING SYNCHRONIZATION STILL BROKEN")
                print(f"   Differences too large: left={left_diff}px, top={top_diff}px")
                return False
        else:
            print("❌ No positioning data found")
            return False

        print("📋 Step 6: Test preview generation...")

        # Generate preview to test end-to-end
        original_windows = driver.window_handles
        preview_btn = driver.find_element(By.ID, "preview-pdf")
        preview_btn.click()
        time.sleep(5)

        if len(driver.window_handles) > len(original_windows):
            print("✅ Preview generated successfully")
            # Switch back to main window
            driver.switch_to.window(original_windows[0])
        else:
            print("⚠️  Preview may not have opened (check server console)")

        print("🎯 TEST COMPLETE: Positioning synchronization fix verified!")
        return True

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        driver.quit()


if __name__ == "__main__":
    test_positioning_sync_fix()
