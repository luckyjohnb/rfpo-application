#!/usr/bin/env python3
"""
Test existing positioned fields to validate translation system
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


def test_existing_positioning():
    """Test existing positioned fields and their translation"""
    driver = setup_driver()
    if not driver:
        return

    try:
        print("🔍 ANALYZING EXISTING POSITIONED FIELDS")
        print("=" * 70)

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

        # Get all positioned fields
        positioned_fields = driver.find_elements(
            By.CSS_SELECTOR, "#pdf-canvas .pdf-field"
        )
        print(f"📋 Found {len(positioned_fields)} positioned fields")

        # Analyze key fields
        key_fields = ["po_number", "po_date", "vendor_company"]
        field_positions = {}

        for field in positioned_fields:
            field_name = field.get_attribute("data-field-name")
            if field_name in key_fields:
                pos_data = driver.execute_script(
                    """
                    const field = arguments[0];
                    const style = window.getComputedStyle(field);
                    return {
                        name: field.dataset.fieldName,
                        text: field.textContent.trim(),
                        left: parseFloat(style.left),
                        top: parseFloat(style.top),
                        visible: style.display !== 'none'
                    };
                """,
                    field,
                )
                field_positions[field_name] = pos_data

        print(f"\n📍 KEY FIELD POSITIONS IN DESIGNER:")
        for field_name, data in field_positions.items():
            print(
                f"   {data['name']}: '{data['text']}' at ({data['left']:.1f}, {data['top']:.1f})"
            )

            # Analyze relative position
            x, y = data["left"], data["top"]
            if x < 200:
                x_area = "LEFT"
            elif x < 500:
                x_area = "CENTER"
            else:
                x_area = "RIGHT"

            if y < 200:
                y_area = "TOP"
            elif y < 600:
                y_area = "MIDDLE"
            else:
                y_area = "BOTTOM"

            expected_area = f"{y_area}-{x_area}"
            print(f"      → Expected in PDF: {expected_area} area")

        # Test coordinate conversion calculation
        print(f"\n🔄 COORDINATE CONVERSION ANALYSIS:")
        canvas_width, canvas_height = 827, 1070
        pdf_width, pdf_height = 612, 792
        scale_x = pdf_width / canvas_width
        scale_y = pdf_height / canvas_height

        print(f"   Canvas size: {canvas_width} x {canvas_height}")
        print(f"   PDF size: {pdf_width} x {pdf_height}")
        print(f"   Scale factors: X={scale_x:.3f}, Y={scale_y:.3f}")

        for field_name, data in field_positions.items():
            x, y = data["left"], data["top"]

            # Current system (wrong)
            current_pdf_y = 792 - y

            # Correct system with scaling
            scaled_x = x * scale_x
            scaled_pdf_y = pdf_height - (y * scale_y)

            print(f"\n   {field_name}:")
            print(f"      Designer: ({x:.1f}, {y:.1f})")
            print(
                f"      Current PDF: ({x:.1f}, {current_pdf_y:.1f}) ❌ WRONG - No scaling"
            )
            print(
                f"      Correct PDF: ({scaled_x:.1f}, {scaled_pdf_y:.1f}) ✅ WITH scaling"
            )

            # Check if coordinates are vastly different
            x_diff = abs(scaled_x - x)
            y_diff = abs(scaled_pdf_y - current_pdf_y)
            if x_diff > 50 or y_diff > 50:
                print(
                    f"      🚨 MAJOR SCALING ISSUE: Diff X={x_diff:.1f}, Y={y_diff:.1f}"
                )

        # Move one field to test position and verify
        if "po_number" in field_positions:
            print(f"\n🎯 TESTING POSITION CHANGE:")
            po_field = None
            for field in positioned_fields:
                if field.get_attribute("data-field-name") == "po_number":
                    po_field = field
                    break

            if po_field:
                # Move to a distinctive position
                test_x, test_y = 150, 200  # Top-left area
                print(f"   Moving PO NUMBER to test position: ({test_x}, {test_y})")

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
                    po_field,
                    test_x,
                    test_y,
                )

                # Calculate expected PDF position
                expected_pdf_x = test_x * scale_x
                expected_pdf_y = pdf_height - (test_y * scale_y)
                print(
                    f"   Expected PDF position: ({expected_pdf_x:.1f}, {expected_pdf_y:.1f})"
                )

                # Save and preview
                save_btn = driver.find_element(By.ID, "save-config")
                save_btn.click()
                time.sleep(2)

                print(f"\n📄 Generating preview to test positioning...")
                print(f"   🔍 Watch server console for debug output!")

                original_windows = driver.window_handles
                preview_btn = driver.find_element(By.ID, "preview-pdf")
                preview_btn.click()
                time.sleep(8)

                if len(driver.window_handles) > len(original_windows):
                    driver.switch_to.window(driver.window_handles[-1])

                    print(f"\n✅ Preview generated!")
                    print(f"🔍 MANUAL CHECK: PO NUMBER should be in TOP-LEFT area")
                    print(f"   If it appears in TOP-LEFT: Translation working! ✅")
                    print(f"   If it appears elsewhere: Translation broken! ❌")

                    time.sleep(10)
                    driver.close()
                    driver.switch_to.window(original_windows[0])
                else:
                    print(f"❌ Preview failed to generate")

        print(f"\n" + "=" * 70)
        print("🎯 TRANSLATION SYSTEM STATUS")
        print("=" * 70)
        print("Based on the coordinate analysis above:")
        print("✅ IF scaling factors are being applied in PDF generation")
        print("❌ IF raw coordinates are being used without scaling")
        print()
        print("Check server console for debug messages:")
        print("- 'Canvas dimensions: XXXxYYY'")
        print("- 'Scale factors: X=0.740, Y=0.740'")
        print("- 'Position conversion for po_number: ...'")

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
    test_existing_positioning()
