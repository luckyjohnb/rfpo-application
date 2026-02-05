#!/usr/bin/env python3
"""
VALIDATION TEST WITH SCREENSHOTS
Validates positioning accuracy between designer and preview with visual proof
"""
import time
import os
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


def calculate_relative_position(x, y, container_width, container_height):
    """Calculate relative position as percentage"""
    rel_x = (x / container_width) * 100
    rel_y = (y / container_height) * 100
    return rel_x, rel_y


def get_position_area(rel_x, rel_y):
    """Get descriptive area based on relative position"""
    # Determine horizontal area
    if rel_x < 33:
        h_area = "LEFT"
    elif rel_x < 66:
        h_area = "CENTER"
    else:
        h_area = "RIGHT"

    # Determine vertical area
    if rel_y < 33:
        v_area = "TOP"
    elif rel_y < 66:
        v_area = "MIDDLE"
    else:
        v_area = "BOTTOM"

    return f"{v_area}-{h_area}"


def test_positioning_validation_with_screenshots():
    """Test positioning with screenshot validation"""
    driver = setup_driver()
    if not driver:
        return

    # Create screenshots directory
    os.makedirs("screenshots", exist_ok=True)

    try:
        print("📸 POSITIONING VALIDATION WITH SCREENSHOTS")
        print("=" * 80)
        print("This test will take screenshots and measure positioning accuracy")
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

        # Clear existing fields
        print("\n🧹 Clearing existing fields...")
        clear_btn = driver.find_element(By.ID, "clear-canvas")
        clear_btn.click()

        try:
            WebDriverWait(driver, 3).until(EC.alert_is_present())
            alert = Alert(driver)
            alert.accept()
            time.sleep(2)
        except TimeoutException:
            pass

        # Test cases with specific positioning
        test_cases = [
            {
                "name": "po_number",
                "text": "PO NUMBER",
                "x": 450,  # Right side
                "y": 50,  # Top area
                "expected_area": "TOP-RIGHT",
            },
            {
                "name": "po_date",
                "text": "PO DATE",
                "x": 450,  # Right side
                "y": 100,  # Top area
                "expected_area": "TOP-RIGHT",
            },
        ]

        # Create positioned fields
        print(f"\n🎯 Creating positioned fields...")
        for case in test_cases:
            print(
                f"   Creating {case['name']} at ({case['x']}, {case['y']}) - Expected: {case['expected_area']}"
            )

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
                field.style.backgroundColor = 'rgba(255, 255, 0, 0.9)';
                field.style.border = '2px solid red';
                field.style.borderRadius = '3px';
                field.style.zIndex = '200';
                field.style.cursor = 'move';
                
                canvas.appendChild(field);
                
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
            """,
                case["name"],
                case["text"],
                case["x"],
                case["y"],
            )

        time.sleep(2)

        # Get canvas dimensions for relative calculations
        canvas_info = driver.execute_script(
            """
            const canvas = document.getElementById('pdf-canvas');
            const rect = canvas.getBoundingClientRect();
            return {
                width: rect.width,
                height: rect.height
            };
        """
        )

        print(
            f"   Canvas dimensions: {canvas_info['width']:.1f} x {canvas_info['height']:.1f}"
        )

        # Measure positioned fields in designer
        designer_positions = {}
        positioned_fields = driver.find_elements(
            By.CSS_SELECTOR, "#pdf-canvas .pdf-field"
        )

        print(f"\n📏 Measuring designer positions...")
        for field in positioned_fields:
            field_data = driver.execute_script(
                """
                const field = arguments[0];
                const style = window.getComputedStyle(field);
                const rect = field.getBoundingClientRect();
                return {
                    name: field.dataset.fieldName,
                    text: field.textContent,
                    left: parseFloat(style.left),
                    top: parseFloat(style.top),
                    centerX: rect.left + rect.width / 2,
                    centerY: rect.top + rect.height / 2
                };
            """,
                field,
            )

            # Calculate relative position
            rel_x, rel_y = calculate_relative_position(
                field_data["left"],
                field_data["top"],
                canvas_info["width"],
                canvas_info["height"],
            )

            area = get_position_area(rel_x, rel_y)

            designer_positions[field_data["name"]] = {
                "absolute": (field_data["left"], field_data["top"]),
                "relative": (rel_x, rel_y),
                "area": area,
                "text": field_data["text"],
            }

            print(
                f"   {field_data['name']}: absolute({field_data['left']:.1f}, {field_data['top']:.1f}) relative({rel_x:.1f}%, {rel_y:.1f}%) → {area}"
            )

        # Take screenshot of designer
        print(f"\n📸 Taking designer screenshot...")
        driver.save_screenshot("screenshots/designer_positioned.png")
        print(f"   Saved: screenshots/designer_positioned.png")

        # Save configuration
        print(f"\n💾 Saving configuration...")
        save_btn = driver.find_element(By.ID, "save-config")
        save_btn.click()
        time.sleep(3)

        # Generate preview
        print(f"\n📄 Generating preview...")
        print(f"   🔍 Watch server console for debug output!")

        original_windows = driver.window_handles
        preview_btn = driver.find_element(By.ID, "preview-pdf")
        preview_btn.click()
        time.sleep(10)  # Extra time for generation and debug

        if len(driver.window_handles) > len(original_windows):
            driver.switch_to.window(driver.window_handles[-1])
            print(f"   ✅ Preview opened")

            # Wait for PDF to load
            time.sleep(5)

            # Take screenshot of preview
            print(f"📸 Taking preview screenshot...")
            driver.save_screenshot("screenshots/preview_positioned.png")
            print(f"   Saved: screenshots/preview_positioned.png")

            # Get PDF dimensions for analysis
            pdf_dimensions = driver.execute_script(
                """
                return {
                    width: window.innerWidth,
                    height: window.innerHeight,
                    scrollWidth: document.body.scrollWidth,
                    scrollHeight: document.body.scrollHeight
                };
            """
            )

            print(
                f"   PDF view dimensions: {pdf_dimensions['width']} x {pdf_dimensions['height']}"
            )

            time.sleep(10)  # Allow manual inspection

            driver.close()
            driver.switch_to.window(original_windows[0])
        else:
            print(f"   ❌ Preview failed to open")
            return False

        # VALIDATION ANALYSIS
        print(f"\n" + "=" * 80)
        print("🔍 POSITIONING VALIDATION ANALYSIS")
        print("=" * 80)

        print(f"\n📊 DESIGNER POSITIONING SUMMARY:")
        for field_name, pos_data in designer_positions.items():
            abs_pos = pos_data["absolute"]
            rel_pos = pos_data["relative"]
            area = pos_data["area"]
            print(f"   {field_name}:")
            print(f"      Absolute: ({abs_pos[0]:.1f}, {abs_pos[1]:.1f})")
            print(f"      Relative: ({rel_pos[0]:.1f}%, {rel_pos[1]:.1f}%)")
            print(f"      Area: {area}")

        print(f"\n📸 SCREENSHOT ANALYSIS:")
        print(f"   Designer: screenshots/designer_positioned.png")
        print(f"   Preview:  screenshots/preview_positioned.png")

        print(f"\n🎯 MANUAL VALIDATION REQUIRED:")
        print(f"   1. Open both screenshots side by side")
        print(f"   2. Verify PO NUMBER appears in TOP-RIGHT area of BOTH images")
        print(f"   3. Verify PO DATE appears in TOP-RIGHT area of BOTH images")
        print(f"   4. Check that relative positions match within 5% tolerance")

        print(f"\n✅ SUCCESS CRITERIA:")
        print(f"   - Both fields in TOP-RIGHT area of preview PDF")
        print(f"   - Relative positions match designer within 5%")
        print(f"   - No phantom elements in preview")
        print(f"   - Fields contain actual data (not 'PO NUMBER' text)")

        print(f"\n❌ FAILURE INDICATORS:")
        print(f"   - Fields missing from preview")
        print(f"   - Fields in wrong areas (not TOP-RIGHT)")
        print(f"   - Phantom/extra elements in preview")
        print(f"   - Position difference > 5%")

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
    success = test_positioning_validation_with_screenshots()
    if success:
        print(f"\n🎉 VALIDATION TEST COMPLETED")
        print(f"Check screenshots/ directory for visual evidence")
    else:
        print(f"\n💥 VALIDATION TEST FAILED")
