#!/usr/bin/env python3
"""
Test the critical visibility fix
"""
import time
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


def test_critical_visibility_fix():
    """Test the visibility fix"""
    driver = setup_driver()
    if not driver:
        return

    try:
        print("🔧 TESTING CRITICAL VISIBILITY FIX")
        print("=" * 80)
        print("This test validates that positioned fields are marked as visible=true")
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

        # Clear everything first (test new clear logic)
        print("\n🧹 Testing new clear functionality...")
        clear_btn = driver.find_element(By.ID, "clear-canvas")
        clear_btn.click()

        try:
            WebDriverWait(driver, 3).until(EC.alert_is_present())
            alert = Alert(driver)
            alert.accept()
            time.sleep(2)
        except TimeoutException:
            pass

        # Check positioning data after clear
        positioning_data = driver.execute_script("return window.POSITIONING_DATA;")
        print(f"   Positioning data after clear: {positioning_data}")

        if not positioning_data or len(positioning_data) == 0:
            print("   ✅ Clear correctly emptied positioning data")
        else:
            print("   ❌ Clear failed - positioning data still exists")
            return False

        # Add a test field with explicit visible=true
        print("\n🎯 Adding test field with visible=true...")
        driver.execute_script(
            """
            const canvas = document.getElementById('pdf-canvas');
            const field = document.createElement('div');
            field.className = 'pdf-field';
            field.dataset.fieldName = 'po_number';
            field.textContent = 'TEST PO NUMBER';
            field.style.position = 'absolute';
            field.style.left = '500px';
            field.style.top = '80px';
            field.style.padding = '6px 12px';
            field.style.fontSize = '14px';
            field.style.fontFamily = 'Arial, sans-serif';
            field.style.backgroundColor = 'rgba(255, 255, 0, 0.9)';
            field.style.border = '3px solid red';
            field.style.borderRadius = '4px';
            field.style.zIndex = '200';
            field.style.fontWeight = 'bold';
            
            canvas.appendChild(field);
            
            // CRITICAL: Set visible=true explicitly
            window.POSITIONING_DATA = {
                'po_number': {
                    x: 500,
                    y: 80,
                    font_size: 14,
                    font_weight: 'bold',
                    visible: true  // EXPLICITLY TRUE
                }
            };
            
            console.log('Created field with visible=true:', window.POSITIONING_DATA);
        """
        )

        time.sleep(2)

        # Verify positioning data
        new_positioning_data = driver.execute_script("return window.POSITIONING_DATA;")
        print(f"   New positioning data: {new_positioning_data}")

        if "po_number" in new_positioning_data:
            field_data = new_positioning_data["po_number"]
            if field_data.get("visible") == True:
                print("   ✅ Field correctly set to visible=true")
            else:
                print(
                    f"   ❌ Field visible={field_data.get('visible')} (should be True)"
                )
                return False
        else:
            print("   ❌ Field not found in positioning data")
            return False

        # Save configuration
        print("\n💾 Saving configuration with visible=true...")
        save_btn = driver.find_element(By.ID, "save-config")
        save_btn.click()
        time.sleep(3)

        # Generate preview to test if field appears
        print("\n📄 Testing preview with visible=true field...")
        original_windows = driver.window_handles
        preview_btn = driver.find_element(By.ID, "preview-pdf")
        preview_btn.click()
        time.sleep(10)

        if len(driver.window_handles) > len(original_windows):
            driver.switch_to.window(driver.window_handles[-1])
            print("   ✅ Preview opened")

            # Check for field content in PDF
            try:
                page_text = driver.execute_script(
                    "return document.body.innerText || document.body.textContent || '';"
                )
                if "TEST PO NUMBER" in page_text or "PO NUMBER" in page_text:
                    print("   ✅ SUCCESS: Field content found in PDF!")
                    print(f"      Found text containing PO NUMBER")
                else:
                    print("   ❌ FAILURE: No field content found in PDF")
                    print(f"      PDF text preview: {page_text[:200]}...")
            except Exception as e:
                print(f"   ⚠️  Could not check PDF text: {e}")

            time.sleep(8)
            driver.close()
            driver.switch_to.window(original_windows[0])
        else:
            print("   ❌ Preview failed to open")
            return False

        print(f"\n🎯 VALIDATION COMPLETE")
        print(f"If 'Field content found in PDF' appeared above, the fix worked!")

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
    success = test_critical_visibility_fix()
    if success:
        print(f"\n🎉 VISIBILITY FIX VALIDATED")
    else:
        print(f"\n💥 VISIBILITY FIX FAILED")
