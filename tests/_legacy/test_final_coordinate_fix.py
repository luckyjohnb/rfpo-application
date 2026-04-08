#!/usr/bin/env python3
"""
Test the final coordinate fix - no scaling, just Y-axis flip
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options


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


def test_final_coordinate_fix():
    """Test the corrected coordinate conversion (no scaling, just Y-axis flip)"""
    driver = setup_driver()
    if not driver:
        return

    try:
        print("🔧 TESTING FINAL COORDINATE FIX")
        print("=" * 60)
        print("Canvas = 612x792, PDF = 612x792 → No scaling, just Y-axis flip")
        print()

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

        # Find PO NUMBER field to test with
        po_field = None
        positioned_fields = driver.find_elements(
            By.CSS_SELECTOR, "#pdf-canvas .pdf-field"
        )
        for field in positioned_fields:
            if field.get_attribute("data-field-name") == "po_number":
                po_field = field
                break

        if not po_field:
            print("❌ PO NUMBER field not found")
            return

        # Test specific positions that should be easy to verify
        test_positions = [
            (100, 100, "TOP-LEFT"),  # Should appear at PDF(100, 692)
            (500, 100, "TOP-RIGHT"),  # Should appear at PDF(500, 692)
            (300, 400, "CENTER"),  # Should appear at PDF(300, 392)
            (100, 700, "BOTTOM-LEFT"),  # Should appear at PDF(100, 92)
            (500, 700, "BOTTOM-RIGHT"),  # Should appear at PDF(500, 92)
        ]

        for i, (x, y, area) in enumerate(test_positions):
            print(f"\n🎯 Test {i+1}: {area} area")
            print(f"   Designer position: ({x}, {y})")

            # Calculate expected PDF position (Y-axis flip only)
            expected_pdf_x = x
            expected_pdf_y = 792 - y
            print(f"   Expected PDF position: ({expected_pdf_x}, {expected_pdf_y})")

            # Move field to test position
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
                    window.POSITIONING_DATA[fieldName].visible = true;
                }
            """,
                po_field,
                x,
                y,
            )

            time.sleep(1)

            # Save and preview
            save_btn = driver.find_element(By.ID, "save-config")
            save_btn.click()
            time.sleep(2)

            print(
                f"   📄 Generating preview (check server console for conversion debug)"
            )
            original_windows = driver.window_handles
            preview_btn = driver.find_element(By.ID, "preview-pdf")
            preview_btn.click()
            time.sleep(5)

            if len(driver.window_handles) > len(original_windows):
                driver.switch_to.window(driver.window_handles[-1])

                # Determine expected area in PDF
                if expected_pdf_y > 600:
                    pdf_area = "TOP"
                elif expected_pdf_y > 300:
                    pdf_area = "MIDDLE"
                else:
                    pdf_area = "BOTTOM"

                if expected_pdf_x < 200:
                    pdf_area += "-LEFT"
                elif expected_pdf_x < 400:
                    pdf_area += "-CENTER"
                else:
                    pdf_area += "-RIGHT"

                print(f"   👀 VERIFY: PO NUMBER should be in {pdf_area} area of PDF")
                time.sleep(4)

                driver.close()
                driver.switch_to.window(original_windows[0])
            else:
                print(f"   ❌ Preview failed")

            # Brief pause between tests
            time.sleep(1)

        print(f"\n" + "=" * 60)
        print("🎯 VALIDATION SUMMARY")
        print("=" * 60)
        print("If PO NUMBER appeared in the CORRECT areas for each test:")
        print("✅ Coordinate translation is now working correctly!")
        print()
        print("If PO NUMBER appeared in WRONG areas:")
        print("❌ Still issues with the coordinate conversion")
        print()
        print("Check server console for coordinate conversion debug:")
        print("- 'Canvas styled dimensions: 612x792 (matches PDF)'")
        print("- 'Position conversion for po_number: Canvas(X,Y) -> PDF(X,792-Y)'")
        print("- 'No scaling needed - canvas matches PDF dimensions'")

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
    test_final_coordinate_fix()
