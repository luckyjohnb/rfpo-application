#!/usr/bin/env python3
"""
Test extreme positioning to see if ANY positioning is working
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


def test_extreme_positioning():
    """Test with extreme coordinates to see if anything works"""
    driver = setup_driver()
    if not driver:
        return

    try:
        print("🧪 TESTING EXTREME POSITIONING")
        print("=" * 60)

        # Login and navigate
        driver.get("http://localhost:5111/")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "email"))
        )
        driver.find_element(By.NAME, "email").send_keys("admin@rfpo.com")
        driver.find_element(By.NAME, "password").send_keys("admin123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "pdf-canvas"))
        )
        time.sleep(3)
        print("✅ Editor loaded")

        # Find PO NUMBER field and move it to extreme position
        po_number_field = None
        fields = driver.find_elements(By.CSS_SELECTOR, "#pdf-canvas .pdf-field")
        for field in fields:
            if field.get_attribute("data-field-name") == "po_number":
                po_number_field = field
                break

        if not po_number_field:
            print("❌ PO NUMBER field not found")
            return

        print("📍 Moving PO NUMBER to extreme position for testing...")

        # Get current position
        original_pos = driver.execute_script(
            """
            const field = arguments[0];
            const style = window.getComputedStyle(field);
            return {
                left: parseFloat(style.left),
                top: parseFloat(style.top)
            };
        """,
            po_number_field,
        )
        print(f"   Original position: ({original_pos['left']}, {original_pos['top']})")

        # Move to extreme position (manual JavaScript positioning)
        extreme_x = 50  # Far left
        extreme_y = 50  # Very top

        driver.execute_script(
            """
            const field = arguments[0];
            field.style.left = arguments[1] + 'px';
            field.style.top = arguments[2] + 'px';
            
            // Update positioning data
            const fieldName = field.dataset.fieldName;
            if (window.POSITIONING_DATA && fieldName) {
                window.POSITIONING_DATA[fieldName].x = arguments[1];
                window.POSITIONING_DATA[fieldName].y = arguments[2];
                console.log('Updated positioning data for', fieldName, 'to', arguments[1], arguments[2]);
            }
        """,
            po_number_field,
            extreme_x,
            extreme_y,
        )

        time.sleep(1)

        # Verify new position
        new_pos = driver.execute_script(
            """
            const field = arguments[0];
            const style = window.getComputedStyle(field);
            return {
                left: parseFloat(style.left),
                top: parseFloat(style.top)
            };
        """,
            po_number_field,
        )
        print(f"   New position: ({new_pos['left']}, {new_pos['top']})")

        # Calculate what this should be in PDF coordinates
        pdf_y = 792 - extreme_y
        print(f"   Expected PDF coordinates: ({extreme_x}, {pdf_y})")

        # Save configuration
        print("\n💾 Saving configuration with extreme position...")
        save_btn = driver.find_element(By.ID, "save-config")
        save_btn.click()
        time.sleep(2)

        # Test preview
        print("\n📄 Testing preview with extreme positioning...")
        original_windows = driver.window_handles
        preview_btn = driver.find_element(By.ID, "preview-pdf")
        preview_btn.click()
        time.sleep(5)

        new_windows = driver.window_handles
        if len(new_windows) > len(original_windows):
            print("   ✅ Preview opened")

            # Switch to preview
            driver.switch_to.window(new_windows[-1])
            time.sleep(2)

            print("\n🔍 MANUAL INSPECTION TIME:")
            print("   Look for PO NUMBER field in the preview PDF")
            print(f"   It should appear at coordinates ({extreme_x}, {pdf_y})")
            print("   - Far left side of page")
            print("   - Very top of page")
            print(
                "\n   If you see it, positioning IS working but coordinates might need adjustment"
            )
            print(
                "   If you don't see it, there's a deeper issue with the PDF generator"
            )

            time.sleep(15)

            driver.close()
            driver.switch_to.window(original_windows[0])
        else:
            print("   ❌ Preview failed to open")

        # Test with different extreme position
        print("\n🧪 Testing second extreme position...")
        extreme_x2 = 500  # Far right
        extreme_y2 = 700  # Bottom

        driver.execute_script(
            """
            const field = arguments[0];
            field.style.left = arguments[1] + 'px';
            field.style.top = arguments[2] + 'px';
            
            // Update positioning data
            const fieldName = field.dataset.fieldName;
            if (window.POSITIONING_DATA && fieldName) {
                window.POSITIONING_DATA[fieldName].x = arguments[1];
                window.POSITIONING_DATA[fieldName].y = arguments[2];
            }
        """,
            po_number_field,
            extreme_x2,
            extreme_y2,
        )

        pdf_y2 = 792 - extreme_y2
        print(
            f"   Position 2: screen({extreme_x2}, {extreme_y2}) -> pdf({extreme_x2}, {pdf_y2})"
        )

        # Save and preview again
        save_btn.click()
        time.sleep(2)

        original_windows = driver.window_handles
        preview_btn.click()
        time.sleep(5)

        new_windows = driver.window_handles
        if len(new_windows) > len(original_windows):
            driver.switch_to.window(new_windows[-1])
            print("   ✅ Second preview opened - check if PO NUMBER moved")
            time.sleep(10)
            driver.close()
            driver.switch_to.window(original_windows[0])

        print("\n🎯 RESULTS:")
        print("   If PO NUMBER appeared in EITHER position:")
        print("   ✅ Positioning system is working, just needs coordinate fine-tuning")
        print("   If PO NUMBER didn't appear in ANY position:")
        print("   ❌ Fundamental issue with PDF generator or field rendering")

    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback

        traceback.print_exc()

    finally:
        driver.quit()


if __name__ == "__main__":
    test_extreme_positioning()
