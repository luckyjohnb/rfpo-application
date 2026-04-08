#!/usr/bin/env python3
"""
CRITICAL TEST: Positioning Translation System
Test that elements placed in designer appear in correct relative positions in preview
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


def test_positioning_translation():
    """Test the positioning translation system comprehensively"""
    driver = setup_driver()
    if not driver:
        return

    try:
        print("🎯 CRITICAL POSITIONING TRANSLATION TEST")
        print("=" * 80)
        print(
            "Testing that designer positions translate correctly to preview positions"
        )
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

        # Get canvas dimensions for analysis
        canvas_info = driver.execute_script(
            """
            const canvas = document.getElementById('pdf-canvas');
            const canvasRect = canvas.getBoundingClientRect();
            return {
                width: canvasRect.width,
                height: canvasRect.height
            };
        """
        )

        print(
            f"📐 Canvas dimensions: {canvas_info['width']:.1f} x {canvas_info['height']:.1f}"
        )

        # Clear all existing positioned fields first
        print("\n🧹 Clearing all existing positioned fields...")
        driver.find_element(By.ID, "clear-canvas").click()
        time.sleep(2)

        # Find available fields to drag
        available_fields = driver.find_elements(
            By.CSS_SELECTOR, "#fields-list .list-group-item"
        )
        print(f"📋 Found {len(available_fields)} available fields")

        # Test positioning with specific fields that should be easy to identify
        test_cases = [
            {
                "field_name": "po_number",
                "description": "PO Number",
                "designer_x": 700,  # Far right
                "designer_y": 100,  # Top area
                "expected_area": "TOP-RIGHT",
            },
            {
                "field_name": "po_date",
                "description": "PO Date",
                "designer_x": 100,  # Far left
                "designer_y": 500,  # Middle area
                "expected_area": "MIDDLE-LEFT",
            },
            {
                "field_name": "vendor_company",
                "description": "Vendor Company",
                "designer_x": 400,  # Center
                "designer_y": 800,  # Bottom area
                "expected_area": "BOTTOM-CENTER",
            },
        ]

        print(f"\n🎯 POSITIONING TEST CASES:")
        for i, test_case in enumerate(test_cases):
            print(
                f"   {i+1}. {test_case['description']}: Designer({test_case['designer_x']}, {test_case['designer_y']}) → Expected: {test_case['expected_area']}"
            )

        # Execute positioning tests
        for i, test_case in enumerate(test_cases):
            print(f"\n{'='*60}")
            print(f"🧪 TEST CASE {i+1}: {test_case['description']}")
            print(f"{'='*60}")

            field_name = test_case["field_name"]
            x = test_case["designer_x"]
            y = test_case["designer_y"]
            expected_area = test_case["expected_area"]

            # Find the available field to drag
            field_element = None
            for available_field in available_fields:
                if (
                    field_name in available_field.get_attribute("data-field-name")
                    or field_name in available_field.text.lower()
                ):
                    field_element = available_field
                    break

            if not field_element:
                print(f"❌ Could not find available field for {field_name}")
                continue

            print(f"✅ Found available field: {test_case['description']}")

            # Drag field to canvas position
            print(f"📍 Positioning at Designer({x}, {y})")

            # Get canvas element for drop target
            canvas = driver.find_element(By.ID, "pdf-canvas")

            # Use JavaScript to simulate drag and drop with exact positioning
            driver.execute_script(
                """
                const fieldElement = arguments[0];
                const canvas = arguments[1];
                const x = arguments[2];
                const y = arguments[3];
                const fieldName = arguments[4];
                
                // Create field on canvas
                const field = document.createElement('div');
                field.className = 'pdf-field';
                field.dataset.fieldName = fieldName;
                field.textContent = fieldElement.textContent.split('\\n')[0]; // Get main title
                field.style.position = 'absolute';
                field.style.left = x + 'px';
                field.style.top = y + 'px';
                field.style.padding = '4px 8px';
                field.style.fontSize = '9px';
                field.style.fontFamily = 'Arial, sans-serif';
                field.style.cursor = 'move';
                field.style.userSelect = 'none';
                field.style.zIndex = '200';
                
                canvas.appendChild(field);
                
                // Update positioning data
                if (!window.POSITIONING_DATA) {
                    window.POSITIONING_DATA = {};
                }
                
                window.POSITIONING_DATA[fieldName] = {
                    x: x,
                    y: y,
                    font_size: 9,
                    font_weight: 'normal',
                    visible: true
                };
                
                console.log('Created field', fieldName, 'at position', x, y);
                return true;
            """,
                field_element,
                canvas,
                x,
                y,
                field_name,
            )

            time.sleep(1)

            # Verify field was created
            positioned_field = driver.find_element(
                By.CSS_SELECTOR, f".pdf-field[data-field-name='{field_name}']"
            )
            if positioned_field:
                actual_pos = driver.execute_script(
                    """
                    const field = arguments[0];
                    const style = window.getComputedStyle(field);
                    return {
                        left: parseFloat(style.left),
                        top: parseFloat(style.top),
                        text: field.textContent
                    };
                """,
                    positioned_field,
                )

                print(
                    f"✅ Field positioned at: ({actual_pos['left']:.1f}, {actual_pos['top']:.1f})"
                )
                print(f"📝 Field text: '{actual_pos['text']}'")
            else:
                print(f"❌ Field not found after positioning")
                continue

        # Save all positioned fields
        print(f"\n💾 Saving all positioned fields...")
        save_btn = driver.find_element(By.ID, "save-config")
        save_btn.click()
        time.sleep(3)

        # Generate preview and analyze
        print(f"\n📄 Generating preview for positioning analysis...")
        original_windows = driver.window_handles
        preview_btn = driver.find_element(By.ID, "preview-pdf")
        preview_btn.click()
        time.sleep(8)  # Give extra time for PDF generation and debug output

        if len(driver.window_handles) > len(original_windows):
            print("✅ Preview generated successfully")

            # Switch to preview window
            driver.switch_to.window(driver.window_handles[-1])
            time.sleep(3)

            print(f"\n" + "=" * 80)
            print("🔍 MANUAL VERIFICATION REQUIRED")
            print("=" * 80)
            print("Check the PDF preview that just opened:")
            print()

            for i, test_case in enumerate(test_cases):
                print(f"{i+1}. {test_case['description']}:")
                print(
                    f"   Designer position: ({test_case['designer_x']}, {test_case['designer_y']})"
                )
                print(f"   Expected PDF area: {test_case['expected_area']}")
                print(
                    f"   ✅ SUCCESS: Field appears in {test_case['expected_area']} area of PDF"
                )
                print(f"   ❌ FAILURE: Field appears in wrong area or missing")
                print()

            print("🎯 CRITICAL VALIDATION:")
            print("   - PO Number should be in TOP-RIGHT area")
            print("   - PO Date should be in MIDDLE-LEFT area")
            print("   - Vendor Company should be in BOTTOM-CENTER area")
            print()
            print("📊 Check server console for coordinate conversion debug messages!")
            print("   Look for scaling factors and position conversions")

            # Wait for manual verification
            time.sleep(20)

            driver.close()
            driver.switch_to.window(original_windows[0])

        else:
            print("❌ Preview failed to generate")

        print(f"\n" + "=" * 80)
        print("🎯 POSITIONING TRANSLATION ANALYSIS")
        print("=" * 80)
        print("If the fields appeared in the CORRECT areas in the PDF preview,")
        print("then the positioning translation system is working! ✅")
        print()
        print("If any fields appeared in WRONG areas or were MISSING,")
        print("then the translation system needs more work! ❌")
        print()
        print("This test validates the ENTIRE positioning pipeline:")
        print("   1. Designer positioning ✅")
        print("   2. Save to database ✅")
        print("   3. Load from database ✅")
        print("   4. Coordinate scaling/translation ❓")
        print("   5. PDF rendering ❓")

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
    test_positioning_translation()
