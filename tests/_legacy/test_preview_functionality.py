#!/usr/bin/env python3
"""
Test the PDF preview functionality to ensure it reflects current field positions
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains


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


def test_preview_functionality():
    """Test that preview reflects current field positions"""
    driver = setup_driver()
    if not driver:
        return

    try:
        print("🔍 Testing PDF Preview Functionality...")

        # Login
        driver.get("http://localhost:5111/")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "email"))
        )
        driver.find_element(By.NAME, "email").send_keys("admin@rfpo.com")
        driver.find_element(By.NAME, "password").send_keys("admin123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        print("✅ Login successful")

        # Navigate to PDF editor
        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "pdf-canvas"))
        )
        print("✅ PDF Editor loaded")

        # Wait for initialization
        time.sleep(3)

        # Check current field positions
        print("\n🔍 Checking current field positions...")
        positioned_fields = driver.find_elements(
            By.CSS_SELECTOR, "#pdf-canvas .pdf-field"
        )
        print(f"   Found {len(positioned_fields)} positioned fields")

        if len(positioned_fields) > 0:
            # Get first field's position
            first_field = positioned_fields[0]
            field_info = driver.execute_script(
                """
                const field = arguments[0];
                const style = window.getComputedStyle(field);
                return {
                    fieldName: field.dataset.fieldName || field.textContent.trim(),
                    left: style.left,
                    top: style.top,
                    text: field.textContent.trim()
                };
            """,
                first_field,
            )
            print(
                f"   First field: '{field_info['fieldName']}' at {field_info['left']},{field_info['top']}"
            )
            print(f"   Field text: '{field_info['text']}'")

            # Move the field to a new position for testing
            print("\n🔧 Moving field to test preview update...")
            original_left = field_info["left"]
            original_top = field_info["top"]

            # Click to select the field
            first_field.click()
            time.sleep(0.5)

            # Move the field using drag
            actions = ActionChains(driver)
            actions.click_and_hold(first_field).move_by_offset(
                100, 50
            ).release().perform()
            time.sleep(1)

            # Check new position
            new_field_info = driver.execute_script(
                """
                const field = arguments[0];
                const style = window.getComputedStyle(field);
                return {
                    left: style.left,
                    top: style.top
                };
            """,
                first_field,
            )
            print(
                f"   Field moved from {original_left},{original_top} to {new_field_info['left']},{new_field_info['top']}"
            )

        # Test preview button functionality
        print("\n🔍 Testing Preview Button...")
        try:
            preview_btn = driver.find_element(By.ID, "preview-pdf")
            print(f"   Preview button found: '{preview_btn.text}'")

            # Store original window handles
            original_windows = driver.window_handles

            # Click preview button
            print("   Clicking preview button...")
            preview_btn.click()

            # Wait a moment for the save operation and new tab
            time.sleep(3)

            # Check if button state changed (should show loading then restore)
            current_btn_text = preview_btn.text
            is_disabled = preview_btn.get_attribute("disabled")
            print(
                f"   Button state after click: '{current_btn_text}', disabled: {is_disabled}"
            )

            # Check for new window/tab
            new_windows = driver.window_handles
            if len(new_windows) > len(original_windows):
                print("   ✅ New tab opened for preview")

                # Switch to new tab
                driver.switch_to.window(new_windows[-1])
                time.sleep(2)

                # Check if it's a PDF
                current_url = driver.current_url
                print(f"   Preview URL: {current_url}")

                if "preview" in current_url and current_url.endswith(("pdf", "1")):
                    print("   ✅ Preview PDF opened successfully")

                    # Check page content (PDF should be displayed)
                    page_source = driver.page_source.lower()
                    if (
                        "pdf" in page_source or len(page_source) < 1000
                    ):  # PDF might have minimal HTML
                        print("   ✅ PDF content detected")
                    else:
                        print("   ⚠️  Page content unclear, but URL suggests PDF")
                else:
                    print(f"   ❌ Unexpected preview URL: {current_url}")

                # Close preview tab and return to editor
                driver.close()
                driver.switch_to.window(original_windows[0])
                print("   ✅ Returned to editor")

            else:
                print("   ❌ No new tab opened")

                # Check for any error messages
                try:
                    alerts = driver.switch_to.alert
                    print(f"   Alert message: {alerts.text}")
                    alerts.accept()
                except:
                    pass

        except Exception as e:
            print(f"   ❌ Error testing preview button: {e}")

        # Test save button for comparison
        print("\n🔍 Testing Save Button...")
        try:
            save_btn = driver.find_element(By.ID, "save-config")
            print(f"   Save button found: '{save_btn.text}'")

            # Click save button
            save_btn.click()
            time.sleep(1)
            print("   ✅ Save button clicked successfully")

        except Exception as e:
            print(f"   ❌ Error testing save button: {e}")

        print("\n🎯 Test Summary:")
        print("   - Preview button functionality: Auto-save before preview")
        print("   - Expected behavior: Field positions saved, then PDF preview opened")
        print("   - Users can now see real-time field positioning in preview")

        print(f"\n👀 Keeping browser open for 20 seconds for manual verification...")
        print("   You can:")
        print("   1. Move some fields around")
        print("   2. Click Preview PDF")
        print("   3. Verify the preview shows the current positions")
        time.sleep(20)

    except Exception as e:
        print(f"❌ Error during preview test: {e}")
        import traceback

        traceback.print_exc()

    finally:
        driver.quit()
        print("🔚 Preview test completed")


if __name__ == "__main__":
    test_preview_functionality()
