#!/usr/bin/env python3
"""
THOROUGH POSITIONING ANALYSIS
Comprehensive test with visual proof of designer vs preview positioning
"""
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains


def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--window-size=1400,1000")
    return webdriver.Chrome(options=chrome_options)


def thorough_positioning_analysis():
    print("🔍 THOROUGH POSITIONING ANALYSIS")
    print("=" * 80)
    print("GOAL: Place 1 element and verify exact position in designer vs preview")
    print()

    driver = setup_driver()
    session = requests.Session()

    try:
        # Step 1: Login
        print("📋 Step 1: Login...")
        driver.get("http://localhost:5111/login")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "email"))
        )

        driver.find_element(By.NAME, "email").send_keys("admin@rfpo.com")
        driver.find_element(By.NAME, "password").send_keys("admin123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)

        # Login with requests too
        login_data = {"email": "admin@rfpo.com", "password": "admin123"}
        session.post("http://localhost:5111/login", data=login_data)
        print("   ✅ Logged in")

        # Step 2: Navigate to designer and clear
        print("📋 Step 2: Navigate to designer and clear...")
        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "pdf-canvas"))
        )
        time.sleep(5)

        # Clear existing elements
        try:
            clear_button = driver.find_element(By.ID, "clear-canvas")
            clear_button.click()
            time.sleep(1)
            driver.switch_to.alert.accept()
            time.sleep(3)
            print("   ✅ Designer cleared")
        except:
            print("   ⚠️ No clear needed")

        # Take screenshot of empty designer
        driver.save_screenshot("ANALYSIS_1_EMPTY_DESIGNER.png")
        print("   📸 Empty designer: ANALYSIS_1_EMPTY_DESIGNER.png")

        # Step 3: Place element at a specific location (top-right area)
        print("📋 Step 3: Place element at top-right area...")

        # Use JavaScript to place element precisely
        place_element_script = """
        // Populate fields list
        populateFieldsList();
        
        // Place PO_NUMBER field at top-right position
        const fieldName = 'po_number';
        const topRightX = 450; // Near right edge
        const topRightY = 50;  // Near top edge (screen coordinates)
        
        // Calculate PDF coordinates
        const pdfX = topRightX;
        const pdfY = 792 - topRightY; // Convert to PDF coordinates
        
        console.log('Placing element at:');
        console.log('  Screen coordinates:', topRightX, topRightY);
        console.log('  PDF coordinates:', pdfX, pdfY);
        
        // Create field data
        POSITIONING_DATA[fieldName] = {
            x: pdfX,
            y: pdfY,
            font_size: 12,
            font_weight: 'normal',
            visible: true
        };
        
        // Create field element
        createFieldElement(fieldName, POSITIONING_DATA[fieldName]);
        
        // Save configuration
        saveConfiguration();
        
        return {
            fieldName: fieldName,
            screenX: topRightX,
            screenY: topRightY,
            pdfX: pdfX,
            pdfY: pdfY
        };
        """

        placement_result = driver.execute_script(place_element_script)
        print(f"   ✅ Placed {placement_result['fieldName']}")
        print(
            f"   Screen position: ({placement_result['screenX']}, {placement_result['screenY']})"
        )
        print(
            f"   PDF position: ({placement_result['pdfX']}, {placement_result['pdfY']})"
        )
        time.sleep(3)

        # Step 4: Check UI display values
        print("📋 Step 4: Check UI coordinate display...")

        # Click on the field to select it
        field_element = driver.find_element(By.CSS_SELECTOR, ".pdf-field")
        field_element.click()
        time.sleep(2)

        # Get displayed coordinates
        coordinates_text = driver.find_element(By.ID, "coordinates").text
        field_x_value = driver.find_element(By.ID, "field-x").get_attribute("value")
        field_y_value = driver.find_element(By.ID, "field-y").get_attribute("value")

        print(f"   Coordinates display: {coordinates_text}")
        print(f"   Field X input: {field_x_value}")
        print(f"   Field Y input: {field_y_value}")

        # Analyze if UI values make sense
        expected_display_y = placement_result["pdfY"]  # Should show PDF Y coordinate
        actual_display_y = float(field_y_value)

        print(f"   Expected Y display: {expected_display_y}")
        print(f"   Actual Y display: {actual_display_y}")

        if abs(actual_display_y - expected_display_y) < 5:
            print("   ✅ UI Y display appears correct")
            ui_display_correct = True
        else:
            print("   ❌ UI Y display is wrong!")
            ui_display_correct = False

        # Step 5: Take screenshot of designer with element
        print("📋 Step 5: Screenshot designer with element...")
        driver.save_screenshot("ANALYSIS_2_DESIGNER_WITH_ELEMENT.png")
        print("   📸 Designer with element: ANALYSIS_2_DESIGNER_WITH_ELEMENT.png")

        # Step 6: Get API data
        print("📋 Step 6: Verify API data...")
        api_response = session.get("http://localhost:5111/api/pdf-positioning/1")

        if api_response.status_code == 200:
            data = api_response.json()
            api_field_data = data["positioning_data"].get("po_number", {})
            api_x = api_field_data.get("x", 0)
            api_y = api_field_data.get("y", 0)
            print(f"   API position: x={api_x}, y={api_y}")

            if (
                abs(api_x - placement_result["pdfX"]) < 5
                and abs(api_y - placement_result["pdfY"]) < 5
            ):
                print("   ✅ API data matches expected")
                api_correct = True
            else:
                print("   ❌ API data doesn't match expected!")
                api_correct = False
        else:
            print("   ❌ Failed to get API data")
            api_correct = False

        # Step 7: Generate and analyze preview
        print("📋 Step 7: Generate preview and analyze...")

        # Open preview in new tab
        original_window = driver.current_window_handle
        preview_button = driver.find_element(By.ID, "preview-pdf")
        preview_button.click()
        time.sleep(5)

        # Switch to preview window if it opened
        preview_window = None
        for window in driver.window_handles:
            if window != original_window:
                preview_window = window
                break

        if preview_window:
            driver.switch_to.window(preview_window)
            time.sleep(4)

            # Take screenshot of preview
            driver.save_screenshot("ANALYSIS_3_PREVIEW_WITH_ELEMENT.png")
            print("   📸 Preview with element: ANALYSIS_3_PREVIEW_WITH_ELEMENT.png")

            # Get preview URL to analyze
            preview_url = driver.current_url
            print(f"   Preview URL: {preview_url}")

            # Switch back to designer
            driver.switch_to.window(original_window)
        else:
            print("   ⚠️ Preview window didn't open properly")

        # Step 8: Generate PDF via API for detailed analysis
        print("📋 Step 8: Generate PDF via API...")
        pdf_response = session.get(
            "http://localhost:5111/api/pdf-positioning/preview/1"
        )

        if pdf_response.status_code == 200:
            print(f"   ✅ PDF generated: {len(pdf_response.content)} bytes")

            with open("ANALYSIS_PREVIEW.pdf", "wb") as f:
                f.write(pdf_response.content)
            print("   📄 PDF saved: ANALYSIS_PREVIEW.pdf")

            # Check if field content is present
            pdf_text = pdf_response.content.decode("latin-1", errors="ignore")
            if (
                "PO NUMBER" in pdf_text.upper()
                or placement_result["fieldName"].upper() in pdf_text.upper()
            ):
                print("   ✅ Field content found in PDF")
                pdf_has_field = True
            else:
                print("   ❌ Field content not found in PDF")
                pdf_has_field = False
        else:
            print(f"   ❌ PDF generation failed: {pdf_response.status_code}")
            pdf_has_field = False

        # Step 9: Analysis summary
        print("\n" + "=" * 80)
        print("🔍 POSITIONING ANALYSIS RESULTS")
        print("=" * 80)

        print(f"Element Placement:")
        print(f"  Field: {placement_result['fieldName']}")
        print(
            f"  Target screen position: ({placement_result['screenX']}, {placement_result['screenY']})"
        )
        print(
            f"  Calculated PDF position: ({placement_result['pdfX']}, {placement_result['pdfY']})"
        )
        print()

        print(f"UI Display Check:")
        print(f"  Expected Y display: {expected_display_y}")
        print(f"  Actual Y display: {actual_display_y}")
        print(f"  UI display correct: {'✅' if ui_display_correct else '❌'}")
        print()

        print(f"API Storage Check:")
        if api_correct:
            print(f"  API position: ({api_x}, {api_y}) ✅")
        else:
            print(f"  API position: ({api_x}, {api_y}) ❌")
        print()

        print(f"PDF Generation Check:")
        print(f"  PDF contains field: {'✅' if pdf_has_field else '❌'}")
        print()

        # Overall assessment
        issues_found = []
        if not ui_display_correct:
            issues_found.append("UI coordinate display")
        if not api_correct:
            issues_found.append("API data storage")
        if not pdf_has_field:
            issues_found.append("PDF generation")

        if len(issues_found) == 0:
            print("🎉 NO ISSUES FOUND - Positioning appears to work correctly!")
            return True
        else:
            print(f"💥 ISSUES FOUND: {', '.join(issues_found)}")
            print("\n🔧 DETAILED ISSUE ANALYSIS NEEDED:")

            if not ui_display_correct:
                y_diff = actual_display_y - expected_display_y
                print(f"  • UI Y display off by {y_diff} pixels")
                print(f"    This suggests coordinate conversion in UI display is wrong")

            if not api_correct:
                print(f"  • API storage doesn't match calculated coordinates")
                print(f"    This suggests saveConfiguration() has issues")

            if not pdf_has_field:
                print(f"  • PDF doesn't contain the field")
                print(f"    This suggests PDF generator isn't reading positioning data")

            return False

    except Exception as e:
        print(f"❌ Analysis failed: {e}")
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
    print("🎯 THOROUGH POSITIONING ANALYSIS")
    print("=" * 80)
    print("This test will:")
    print("1. Place ONE element at a specific position")
    print("2. Check UI coordinate display")
    print("3. Verify API data storage")
    print("4. Generate visual proof (screenshots)")
    print("5. Test PDF generation")
    print("6. Provide detailed analysis of any issues")
    print()

    success = thorough_positioning_analysis()

    print(f"\n" + "=" * 80)
    print("📸 VISUAL PROOF FILES GENERATED:")
    print("=" * 80)
    print("   1. ANALYSIS_1_EMPTY_DESIGNER.png - Designer before placing element")
    print("   2. ANALYSIS_2_DESIGNER_WITH_ELEMENT.png - Designer with element placed")
    print(
        "   3. ANALYSIS_3_PREVIEW_WITH_ELEMENT.png - Preview showing element position"
    )
    print("   4. ANALYSIS_PREVIEW.pdf - Generated PDF file")
    print()
    print("👀 EXAMINE THESE FILES TO SEE:")
    print("   • Where element appears in designer")
    print("   • Where element appears in preview")
    print("   • Whether positions match")
    print("=" * 80)
