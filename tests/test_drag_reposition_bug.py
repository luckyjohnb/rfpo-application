#!/usr/bin/env python3
"""
TEST DRAG REPOSITION BUG
Reproduce the exact issue: initial placement works, but drag repositioning doesn't save
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


def test_drag_reposition_bug():
    print("🐛 TESTING DRAG REPOSITION BUG")
    print("=" * 80)
    print(
        "Workflow: place element → drag to new position → check if preview shows new position"
    )
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

        # Step 3: Place element at initial position using drag and drop from field list
        print("📋 Step 3: Place element at initial position via drag and drop...")

        # Populate field list
        driver.execute_script("populateFieldsList();")
        time.sleep(2)

        # Find field button and canvas
        field_buttons = driver.find_elements(
            By.CSS_SELECTOR, "#fields-list .list-group-item"
        )
        if not field_buttons:
            print("   ❌ No field buttons found")
            return False

        canvas = driver.find_element(By.ID, "pdf-canvas")

        # Drag field to initial position (left side of canvas)
        initial_x_offset = 100  # 100px from left edge of canvas
        initial_y_offset = 150  # 150px from top edge of canvas

        print(
            f"   Dragging field to initial position: offset ({initial_x_offset}, {initial_y_offset})"
        )

        actions = ActionChains(driver)
        actions.drag_and_drop_by_offset(
            field_buttons[0], initial_x_offset, initial_y_offset
        ).perform()
        time.sleep(3)

        # Verify field was created
        placed_fields = driver.find_elements(By.CSS_SELECTOR, ".pdf-field")
        if len(placed_fields) == 0:
            print("   ❌ Field was not created")
            return False

        field_element = placed_fields[0]
        field_name = field_element.get_attribute("data-field-name")
        print(f"   ✅ Created field: {field_name}")

        # Step 4: Get initial position from API
        print("📋 Step 4: Check initial position in API...")
        api_response = session.get("http://localhost:5111/api/pdf-positioning/1")

        if api_response.status_code == 200:
            initial_data = api_response.json()
            initial_field_data = initial_data["positioning_data"].get(field_name, {})
            initial_x = initial_field_data.get("x", 0)
            initial_y = initial_field_data.get("y", 0)
            print(f"   Initial API position: x={initial_x}, y={initial_y}")
        else:
            print("   ❌ Failed to get initial API data")
            return False

        # Step 5: Generate PDF to see initial position
        print("📋 Step 5: Generate PDF to see initial position...")
        pdf_response_initial = session.get(
            "http://localhost:5111/api/pdf-positioning/preview/1"
        )

        if pdf_response_initial.status_code == 200:
            with open("BUG_TEST_INITIAL_PDF.pdf", "wb") as f:
                f.write(pdf_response_initial.content)
            print("   📄 Initial PDF saved: BUG_TEST_INITIAL_PDF.pdf")
        else:
            print("   ❌ Initial PDF generation failed")

        # Take screenshot of initial position
        driver.save_screenshot("BUG_TEST_INITIAL_DESIGNER.png")
        print("   📸 Initial designer: BUG_TEST_INITIAL_DESIGNER.png")

        # Step 6: Drag element to new position (right side of canvas)
        print("📋 Step 6: Drag element to NEW position...")

        new_x_offset = 400  # 400px from left edge of canvas
        new_y_offset = 100  # 100px from top edge of canvas

        print(
            f"   Dragging field to NEW position: offset ({new_x_offset}, {new_y_offset})"
        )

        # Get current field position to calculate drag delta
        field_rect = field_element.get_attribute_dict(["data-field-name"])

        # Drag to new position
        actions = ActionChains(driver)
        actions.click_and_hold(field_element)
        actions.move_to_element_with_offset(canvas, new_x_offset, new_y_offset)
        actions.release()
        actions.perform()
        time.sleep(3)

        print("   ✅ Drag operation completed")

        # Step 7: Check new position in API
        print("📋 Step 7: Check NEW position in API...")
        api_response_final = session.get("http://localhost:5111/api/pdf-positioning/1")

        if api_response_final.status_code == 200:
            final_data = api_response_final.json()
            final_field_data = final_data["positioning_data"].get(field_name, {})
            final_x = final_field_data.get("x", 0)
            final_y = final_field_data.get("y", 0)
            print(f"   Final API position: x={final_x}, y={final_y}")

            # Compare positions
            x_change = abs(final_x - initial_x)
            y_change = abs(final_y - initial_y)

            print(f"   Position change: Δx={x_change:.1f}, Δy={y_change:.1f}")

            if x_change > 20 or y_change > 20:  # Significant change
                print("   ✅ API position updated after drag")
                api_updated = True
            else:
                print("   ❌ API position NOT updated after drag")
                api_updated = False
        else:
            print("   ❌ Failed to get final API data")
            api_updated = False

        # Step 8: Generate PDF to see final position
        print("📋 Step 8: Generate PDF to see final position...")
        pdf_response_final = session.get(
            "http://localhost:5111/api/pdf-positioning/preview/1"
        )

        if pdf_response_final.status_code == 200:
            with open("BUG_TEST_FINAL_PDF.pdf", "wb") as f:
                f.write(pdf_response_final.content)
            print("   📄 Final PDF saved: BUG_TEST_FINAL_PDF.pdf")

            # Compare PDF sizes (rough indicator of position change)
            initial_size = len(pdf_response_initial.content)
            final_size = len(pdf_response_final.content)

            print(f"   Initial PDF size: {initial_size} bytes")
            print(f"   Final PDF size: {final_size} bytes")

            if (
                abs(final_size - initial_size) > 100
            ):  # Size difference suggests content change
                print("   ✅ PDF appears to have changed")
                pdf_changed = True
            else:
                print("   ⚠️ PDF size similar - may not have changed")
                pdf_changed = False
        else:
            print("   ❌ Final PDF generation failed")
            pdf_changed = False

        # Take screenshot of final position
        driver.save_screenshot("BUG_TEST_FINAL_DESIGNER.png")
        print("   📸 Final designer: BUG_TEST_FINAL_DESIGNER.png")

        # Step 9: Analysis
        print("\n" + "=" * 80)
        print("🔍 DRAG REPOSITION BUG ANALYSIS")
        print("=" * 80)

        print("WORKFLOW STEPS:")
        print(f"  1. Placed element at initial position: ✅")
        print(f"  2. Dragged element to new position: ✅")
        print(f"  3. API position updated: {'✅' if api_updated else '❌'}")
        print(f"  4. PDF reflects new position: {'✅' if pdf_changed else '❌'}")
        print()

        if api_updated and pdf_changed:
            print("🎉 DRAG REPOSITIONING WORKS!")
            print("   Both API and PDF reflect the new position")
            return True
        elif api_updated and not pdf_changed:
            print("⚠️ PARTIAL BUG: API updated but PDF unchanged")
            print("   Issue may be in PDF generation logic")
            return False
        elif not api_updated:
            print("💥 CONFIRMED BUG: API position not updated after drag")
            print("   Drag event handlers are not saving properly")
            return False
        else:
            print("🤔 UNCLEAR RESULT")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        driver.quit()


if __name__ == "__main__":
    print("🎯 REPRODUCING DRAG REPOSITION BUG")
    print("=" * 80)
    print("This test reproduces the user's exact workflow:")
    print("1. Place element at initial position (should work)")
    print("2. Drag element to new position")
    print("3. Check if new position is saved to API")
    print("4. Check if PDF preview reflects new position")
    print()

    # Wait for Flask app to start
    time.sleep(3)

    success = test_drag_reposition_bug()

    print(f"\n" + "=" * 80)
    print("📸 PROOF FILES GENERATED:")
    print("=" * 80)
    print("   1. BUG_TEST_INITIAL_DESIGNER.png - Element at initial position")
    print("   2. BUG_TEST_INITIAL_PDF.pdf - PDF with initial position")
    print("   3. BUG_TEST_FINAL_DESIGNER.png - Element at dragged position")
    print("   4. BUG_TEST_FINAL_PDF.pdf - PDF with final position")
    print()
    print("👀 COMPARE THESE FILES TO SEE:")
    print("   • Where element appears initially vs after drag")
    print("   • Whether PDF position matches designer position")
    print("=" * 80)
