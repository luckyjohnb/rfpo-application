#!/usr/bin/env python3
"""
EMPTY PREVIEW PROOF TEST
Test the exact sequence: clear all elements → refresh PDF → save → view preview
Take screenshots to prove whether preview is truly empty or still shows elements
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--window-size=1400,1000")
    return webdriver.Chrome(options=chrome_options)


def test_empty_preview():
    print("🔍 EMPTY PREVIEW PROOF TEST")
    print("=" * 80)
    print("Following exact sequence to prove preview behavior with no elements")
    print()

    driver = setup_driver()

    try:
        # Step 1: Login and open new report to design
        print("📋 Step 1: Open new report to design...")
        driver.get("http://localhost:5111/login")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "email"))
        )

        driver.find_element(By.NAME, "email").send_keys("admin@rfpo.com")
        driver.find_element(By.NAME, "password").send_keys("admin123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)

        # Navigate to designer
        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "pdf-canvas"))
        )
        time.sleep(5)
        print("   ✅ Designer opened")

        # Check initial state
        initial_fields = driver.find_elements(By.CSS_SELECTOR, ".pdf-field")
        print(f"   Initial fields on canvas: {len(initial_fields)}")

        # Step 2: Clear all elements
        print("📋 Step 2: Clear all elements...")
        try:
            clear_button = driver.find_element(By.ID, "clear-canvas")
            clear_button.click()
            time.sleep(1)

            # Handle confirmation dialog
            try:
                driver.switch_to.alert.accept()
                print("   ✅ Confirmed clear operation")
            except:
                print("   ⚠️ No confirmation dialog appeared")

            time.sleep(2)

            # Verify elements are cleared from designer
            after_clear_fields = driver.find_elements(By.CSS_SELECTOR, ".pdf-field")
            print(f"   Fields after clear: {len(after_clear_fields)}")

            if len(after_clear_fields) == 0:
                print("   ✅ Designer canvas is empty")
            else:
                print("   ❌ Designer still has elements!")
                for i, field in enumerate(after_clear_fields):
                    try:
                        field_name = field.get_attribute("data-field-name")
                        field_text = field.text
                        print(
                            f"      Remaining field {i+1}: {field_name} - '{field_text}'"
                        )
                    except:
                        print(f"      Remaining field {i+1}: Could not read details")

        except Exception as e:
            print(f"   ❌ Clear operation failed: {e}")
            return False

        # Take screenshot of empty designer
        driver.save_screenshot("STEP2_DESIGNER_EMPTY.png")
        print("   📸 Screenshot: STEP2_DESIGNER_EMPTY.png")

        # Step 3: Refresh the PDF
        print("📋 Step 3: Refresh the PDF...")
        try:
            refresh_button = driver.find_element(By.ID, "refresh-pdf")
            refresh_button.click()
            time.sleep(3)
            print("   ✅ PDF refreshed")
        except Exception as e:
            print(f"   ⚠️ Refresh button not found or failed: {e}")
            # Try alternative refresh method
            try:
                driver.execute_script("refreshBackground();")
                time.sleep(3)
                print("   ✅ PDF refreshed via JavaScript")
            except Exception as e2:
                print(f"   ⚠️ JavaScript refresh also failed: {e2}")

        # Step 4: Save config
        print("📋 Step 4: Save configuration...")
        try:
            save_button = driver.find_element(By.ID, "save-config")
            driver.execute_script("arguments[0].scrollIntoView(true);", save_button)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", save_button)
            time.sleep(3)
            print("   ✅ Configuration saved")
        except Exception as e:
            print(f"   ❌ Save failed: {e}")
            return False

        # Step 5: View preview in new tab
        print("📋 Step 5: View preview (opens in new tab)...")

        # Get current window handles
        original_window = driver.current_window_handle
        original_windows = driver.window_handles

        try:
            # Click preview button
            preview_button = driver.find_element(By.ID, "preview-pdf")
            preview_button.click()
            time.sleep(3)

            # Wait for new window to open
            WebDriverWait(driver, 10).until(
                lambda d: len(d.window_handles) > len(original_windows)
            )

            # Switch to the new preview window
            new_windows = driver.window_handles
            preview_window = None
            for window in new_windows:
                if window not in original_windows:
                    preview_window = window
                    break

            if preview_window:
                driver.switch_to.window(preview_window)
                time.sleep(4)  # Wait for PDF to load completely
                print("   ✅ Switched to preview window")

                # Take screenshot of preview
                driver.save_screenshot("STEP5_PREVIEW_RESULT.png")
                print("   📸 Screenshot: STEP5_PREVIEW_RESULT.png")

                # Analyze preview content
                try:
                    page_text = driver.execute_script("return document.body.innerText;")
                    lines = page_text.split("\n")

                    print(f"   Preview content analysis:")
                    print(f"      Total content length: {len(page_text)} characters")
                    print(f"      Number of lines: {len(lines)}")

                    # Look for field-related content
                    field_keywords = [
                        "PO NUMBER",
                        "PO DATE",
                        "VENDOR",
                        "DELIVERY",
                        "PAYMENT",
                        "PROJECT",
                        "TOTAL",
                    ]
                    found_fields = []

                    for line in lines:
                        line_clean = line.strip().upper()
                        if len(line_clean) > 2:  # Ignore very short lines
                            for keyword in field_keywords:
                                if keyword in line_clean:
                                    found_fields.append(f"'{line.strip()}'")
                                    break

                    print(
                        f"      Found field-related content: {len(found_fields)} items"
                    )
                    if found_fields:
                        print("      Field content detected:")
                        for i, field_content in enumerate(
                            found_fields[:10]
                        ):  # Show first 10
                            print(f"         {i+1}. {field_content}")
                        if len(found_fields) > 10:
                            print(f"         ... and {len(found_fields) - 10} more")
                    else:
                        print(
                            "      ✅ No field content detected - preview appears clean"
                        )

                    # Show sample of actual content
                    print(f"      Sample content (first 500 chars):")
                    print(
                        f"         '{page_text[:500]}{'...' if len(page_text) > 500 else ''}'"
                    )

                except Exception as e:
                    print(f"   ⚠️ Could not analyze preview content: {e}")

                # Switch back to original window
                driver.switch_to.window(original_window)
                print("   ✅ Switched back to designer window")

                return len(found_fields) == 0  # True if no fields found (truly empty)

            else:
                print("   ❌ Could not find preview window")
                return False

        except Exception as e:
            print(f"   ❌ Preview failed: {e}")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        # Close all windows
        try:
            for window in driver.window_handles:
                driver.switch_to.window(window)
                driver.close()
        except:
            pass
        driver.quit()


if __name__ == "__main__":
    is_truly_empty = test_empty_preview()

    print(f"\n" + "=" * 80)
    print("🏆 EMPTY PREVIEW PROOF RESULTS")
    print("=" * 80)
    print("📸 PROOF SCREENSHOTS CAPTURED:")
    print("   • STEP2_DESIGNER_EMPTY.png - Designer after clearing all elements")
    print("   • STEP5_PREVIEW_RESULT.png - Preview result (the key evidence)")
    print()

    if is_truly_empty:
        print("✅ PREVIEW IS TRULY EMPTY")
        print("   No field elements detected in preview")
        print("   The clear operation worked correctly")
    else:
        print("❌ PREVIEW STILL CONTAINS ELEMENTS!")
        print("   Field elements detected in preview despite clearing designer")
        print("   This proves the bug - elements persist in preview after clearing")

    print()
    print("🔍 MANUAL VERIFICATION:")
    print("   Please examine STEP5_PREVIEW_RESULT.png to visually confirm")
    print("   whether elements are present in the preview or not.")
    print("=" * 80)
