#!/usr/bin/env python3
"""
CRITICAL DIAGNOSIS: Why positioning is still completely broken
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


def test_positioning_diagnosis():
    """Diagnose why positioning is completely broken"""
    driver = setup_driver()
    if not driver:
        return

    try:
        print("🔥 CRITICAL POSITIONING DIAGNOSIS")
        print("=" * 80)
        print("Testing the exact scenario from user's report")
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

        # STEP 1: Test clearing everything
        print("\n🧹 STEP 1: Testing clear functionality")
        positioned_fields_before = driver.find_elements(
            By.CSS_SELECTOR, "#pdf-canvas .pdf-field"
        )
        print(f"   Fields before clear: {len(positioned_fields_before)}")

        if len(positioned_fields_before) > 0:
            print("   Attempting to clear all fields...")
            clear_btn = driver.find_element(By.ID, "clear-canvas")
            clear_btn.click()

            # Handle confirmation dialog
            try:
                WebDriverWait(driver, 3).until(EC.alert_is_present())
                alert = Alert(driver)
                print(f"   Alert detected: '{alert.text}'")
                alert.accept()
                time.sleep(2)
            except TimeoutException:
                print("   No alert appeared")

            # Check if fields were actually cleared
            positioned_fields_after = driver.find_elements(
                By.CSS_SELECTOR, "#pdf-canvas .pdf-field"
            )
            print(f"   Fields after clear: {len(positioned_fields_after)}")

            if len(positioned_fields_after) == 0:
                print("   ✅ Clear worked in designer")
            else:
                print("   ❌ Clear FAILED in designer")

        # Save the cleared state
        print("\n💾 Saving cleared state...")
        save_btn = driver.find_element(By.ID, "save-config")
        save_btn.click()
        time.sleep(2)

        # Test preview of cleared state
        print("\n📄 Testing preview of CLEARED state...")
        original_windows = driver.window_handles
        preview_btn = driver.find_element(By.ID, "preview-pdf")
        preview_btn.click()
        time.sleep(8)

        if len(driver.window_handles) > len(original_windows):
            driver.switch_to.window(driver.window_handles[-1])
            print("✅ Preview generated for cleared state")
            print("👀 MANUAL CHECK: Preview should show NO positioned elements")
            print(
                "   If you see ANY positioned elements, there's a caching/persistence issue"
            )
            time.sleep(8)
            driver.close()
            driver.switch_to.window(original_windows[0])

        # STEP 2: Add elements in specific positions and test translation
        print("\n🎯 STEP 2: Testing specific positioning")

        # Check available fields
        available_fields = driver.find_elements(
            By.CSS_SELECTOR, "#fields-list .list-group-item"
        )
        print(f"   Available fields found: {len(available_fields)}")

        # Create test fields manually via JavaScript
        print("   Creating PO NUMBER and PO DATE fields manually...")

        test_fields = [
            {"name": "po_number", "text": "PO NUMBER", "x": 700, "y": 100},  # Top-right
            {
                "name": "po_date",
                "text": "PO DATE",
                "x": 550,
                "y": 140,
            },  # Top-right area
        ]

        for field_info in test_fields:
            driver.execute_script(
                """
                const canvas = document.getElementById('pdf-canvas');
                const field = document.createElement('div');
                field.className = 'pdf-field';
                field.dataset.fieldName = arguments[0];
                field.textContent = arguments[1];
                field.style.position = 'absolute';
                field.style.left = arguments[2] + 'px';
                field.style.top = arguments[3] + 'px';
                field.style.padding = '4px 8px';
                field.style.fontSize = '9px';
                field.style.fontFamily = 'Arial, sans-serif';
                field.style.cursor = 'move';
                field.style.userSelect = 'none';
                field.style.zIndex = '200';
                field.style.backgroundColor = 'rgba(255, 255, 0, 0.9)';
                field.style.border = '2px solid red';
                field.style.borderRadius = '3px';
                
                canvas.appendChild(field);
                
                // Update positioning data
                if (!window.POSITIONING_DATA) {
                    window.POSITIONING_DATA = {};
                }
                
                window.POSITIONING_DATA[arguments[0]] = {
                    x: arguments[2],
                    y: arguments[3],
                    font_size: 9,
                    font_weight: 'normal',
                    visible: true
                };
                
                console.log('Created field', arguments[0], 'at', arguments[2], arguments[3]);
            """,
                field_info["name"],
                field_info["text"],
                field_info["x"],
                field_info["y"],
            )

        time.sleep(2)

        # Verify fields were created
        new_positioned_fields = driver.find_elements(
            By.CSS_SELECTOR, "#pdf-canvas .pdf-field"
        )
        print(f"   Fields created: {len(new_positioned_fields)}")

        for field in new_positioned_fields:
            field_data = driver.execute_script(
                """
                const field = arguments[0];
                const style = window.getComputedStyle(field);
                return {
                    name: field.dataset.fieldName,
                    text: field.textContent,
                    left: parseFloat(style.left),
                    top: parseFloat(style.top)
                };
            """,
                field,
            )
            print(
                f"      {field_data['name']}: '{field_data['text']}' at ({field_data['left']:.1f}, {field_data['top']:.1f})"
            )

        # Save positioned state
        print("\n💾 Saving positioned state...")
        save_btn.click()
        time.sleep(3)

        # Check positioning data in JavaScript
        positioning_data = driver.execute_script("return window.POSITIONING_DATA;")
        print(f"\n📊 JavaScript positioning data:")
        for field_name, data in positioning_data.items():
            if field_name in ["po_number", "po_date"]:
                print(
                    f"   {field_name}: x={data.get('x')}, y={data.get('y')}, visible={data.get('visible')}"
                )

        # Test preview with positioning
        print("\n📄 Testing preview with positioned elements...")
        print("   🔍 Watch server console for coordinate conversion debug!")

        original_windows = driver.window_handles
        preview_btn.click()
        time.sleep(10)  # Extra time for debug output

        if len(driver.window_handles) > len(original_windows):
            driver.switch_to.window(driver.window_handles[-1])
            print("✅ Preview generated for positioned elements")
            print("\n👀 CRITICAL VERIFICATION:")
            print("   1. PO NUMBER should be in TOP-RIGHT area of PDF")
            print("   2. PO DATE should be in TOP-RIGHT area of PDF")
            print("   3. NO other positioned elements should appear")
            print(
                "   4. If elements appear in wrong areas, coordinate conversion failed"
            )
            print("   5. If elements are missing, positioning data pipeline failed")

            time.sleep(15)
            driver.close()
            driver.switch_to.window(original_windows[0])
        else:
            print("❌ Preview generation failed")

        print(f"\n" + "=" * 80)
        print("🎯 DIAGNOSIS RESULTS")
        print("=" * 80)
        print("Check the following:")
        print("1. Did clear function work? (No elements in cleared preview)")
        print("2. Do positioned elements appear in correct PDF areas?")
        print("3. Are there any extra/phantom elements in preview?")
        print("4. Check server console for coordinate conversion debug messages")

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
    test_positioning_diagnosis()
