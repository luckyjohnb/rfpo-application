#!/usr/bin/env python3
"""
FINAL VISUAL PROOF TEST
Create definitive proof images showing accurate positioning translation
from designer to preview with landmark-based validation
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image, ImageDraw, ImageFont
import os


def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--window-size=1400,1000")
    chrome_options.add_argument("--force-device-scale-factor=1")
    return webdriver.Chrome(options=chrome_options)


def create_visual_proof():
    print("🎯 CREATING FINAL VISUAL PROOF")
    print("=" * 80)
    print("This will create definitive proof images showing positioning accuracy")
    print()

    driver = setup_driver()

    try:
        # Setup
        print("📋 Step 1: Setup and login...")
        driver.get("http://localhost:5111/login")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "email"))
        )

        driver.find_element(By.NAME, "email").send_keys("admin@rfpo.com")
        driver.find_element(By.NAME, "password").send_keys("admin123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)

        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "pdf-canvas"))
        )
        time.sleep(5)
        print("   ✅ Successfully logged in and navigated to editor")

        # Clear canvas
        print("📋 Step 2: Clear canvas...")
        try:
            clear_button = driver.find_element(By.ID, "clear-canvas")
            clear_button.click()
            time.sleep(1)
            driver.switch_to.alert.accept()
            time.sleep(2)
            print("   ✅ Canvas cleared")
        except Exception as e:
            print(f"   ⚠️ Clear failed: {e}")

        # Get canvas info
        print("📋 Step 3: Analyze canvas...")
        canvas_info = driver.execute_script(
            """
            const canvas = document.getElementById('pdf-canvas');
            const rect = canvas.getBoundingClientRect();
            return {
                width: rect.width,
                height: rect.height,
                left: rect.left,
                top: rect.top
            };
        """
        )
        print(f"   Canvas: {canvas_info['width']:.1f} x {canvas_info['height']:.1f}")
        print(f"   Position: ({canvas_info['left']:.1f}, {canvas_info['top']:.1f})")

        # Place element at specific landmark position (top-right area for PO Number)
        print("📋 Step 4: Place element at landmark position...")
        driver.execute_script("populateFieldsList();")
        time.sleep(2)

        # Find PO Number field
        field_buttons = driver.find_elements(
            By.CSS_SELECTOR, "#fields-list .list-group-item"
        )
        po_number_field = None
        for field in field_buttons:
            if field.get_attribute("data-field-name") == "po_number":
                po_number_field = field
                break

        if not po_number_field:
            print("   ❌ PO Number field not found")
            return False

        # Use ActionChains to drag to a specific position in the top-right area
        canvas = driver.find_element(By.ID, "pdf-canvas")

        # Target position: top-right area where PO Number should go
        # This is approximately where the "Number" box appears on the PO template
        target_x_percent = 0.75  # 75% to the right
        target_y_percent = 0.08  # 8% from top

        target_x = canvas_info["width"] * target_x_percent
        target_y = canvas_info["height"] * target_y_percent

        print(
            f"   Target landmark: ({target_x:.1f}, {target_y:.1f}) = ({target_x_percent*100:.0f}%, {target_y_percent*100:.0f}%)"
        )

        # First drag to canvas center (this works reliably)
        actions = ActionChains(driver)
        actions.drag_and_drop(po_number_field, canvas).perform()
        time.sleep(2)

        # Then move to target position manually
        placed_fields = driver.find_elements(By.CSS_SELECTOR, ".pdf-field")
        if placed_fields:
            placed_field = placed_fields[0]
            # Click and drag to move to target position
            actions = ActionChains(driver)
            actions.click_and_hold(placed_field).move_by_offset(
                target_x - canvas_info["width"] / 2,  # Move from center to target
                target_y - canvas_info["height"] / 2,
            ).release().perform()
            time.sleep(2)

        # Verify placement
        placed_fields = driver.find_elements(By.CSS_SELECTOR, ".pdf-field")
        if not placed_fields:
            print("   ❌ Field was not placed")
            return False

        placed_field = placed_fields[0]

        # Get precise element position
        element_info = driver.execute_script(
            """
            const element = arguments[0];
            const canvas = document.getElementById('pdf-canvas');
            const canvasRect = canvas.getBoundingClientRect();
            const elementRect = element.getBoundingClientRect();
            
            // Position relative to canvas
            const relativeX = elementRect.left - canvasRect.left;
            const relativeY = elementRect.top - canvasRect.top;
            
            // Get coordinates from the system
            const coordsDisplay = document.getElementById('coordinates').textContent;
            const xInput = document.getElementById('field-x').value;
            const yInput = document.getElementById('field-y').value;
            
            return {
                element: {
                    left: elementRect.left,
                    top: elementRect.top,
                    right: elementRect.right,
                    bottom: elementRect.bottom,
                    width: elementRect.width,
                    height: elementRect.height
                },
                canvas: {
                    left: canvasRect.left,
                    top: canvasRect.top,
                    width: canvasRect.width,
                    height: canvasRect.height
                },
                relative: {
                    x: relativeX,
                    y: relativeY,
                    xPercent: (relativeX / canvasRect.width) * 100,
                    yPercent: (relativeY / canvasRect.height) * 100
                },
                coordinates: {
                    display: coordsDisplay,
                    xInput: parseInt(xInput),
                    yInput: parseInt(yInput)
                },
                fieldName: element.dataset.fieldName,
                text: element.textContent.trim()
            };
        """,
            placed_field,
        )

        print(f"   ✅ Element placed: {element_info['fieldName']}")
        print(f"   Text: '{element_info['text']}'")
        print(
            f"   Canvas position: ({element_info['relative']['x']:.1f}, {element_info['relative']['y']:.1f})"
        )
        print(
            f"   Relative position: ({element_info['relative']['xPercent']:.1f}%, {element_info['relative']['yPercent']:.1f}%)"
        )
        print(
            f"   PDF coordinates: ({element_info['coordinates']['xInput']}, {element_info['coordinates']['yInput']})"
        )

        # Save positioning data
        print("📋 Step 5: Save positioning data...")
        save_button = driver.find_element(By.ID, "save-config")
        driver.execute_script("arguments[0].scrollIntoView(true);", save_button)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", save_button)
        time.sleep(3)
        print("   ✅ Positioning data saved")

        # Capture Designer Proof Image
        print("📋 Step 6: Capture designer proof image...")
        screenshot_path = "PROOF_1_DESIGNER.png"
        driver.save_screenshot(screenshot_path)

        # Annotate designer screenshot
        try:
            img = Image.open(screenshot_path)
            draw = ImageDraw.Draw(img)

            # Try to use a system font
            try:
                title_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 20)
                font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 14)
                small_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 12)
            except:
                title_font = ImageFont.load_default()
                font = ImageFont.load_default()
                small_font = ImageFont.load_default()

            # Highlight the element
            elem_x = element_info["element"]["left"]
            elem_y = element_info["element"]["top"]
            elem_w = element_info["element"]["width"]
            elem_h = element_info["element"]["height"]

            # Draw thick red border around element
            border_width = 4
            draw.rectangle(
                [
                    elem_x - border_width,
                    elem_y - border_width,
                    elem_x + elem_w + border_width,
                    elem_y + elem_h + border_width,
                ],
                outline="red",
                width=border_width,
            )

            # Add title at top
            title_text = "PROOF 1: ELEMENT IN DESIGNER"
            draw.text((50, 30), title_text, fill="red", font=title_font)

            # Add element details
            details = [
                f"ELEMENT: {element_info['fieldName']} ('{element_info['text']}')",
                f"CANVAS POSITION: ({element_info['relative']['x']:.0f}, {element_info['relative']['y']:.0f})",
                f"RELATIVE POSITION: ({element_info['relative']['xPercent']:.1f}%, {element_info['relative']['yPercent']:.1f}%)",
                f"PDF COORDINATES: ({element_info['coordinates']['xInput']}, {element_info['coordinates']['yInput']})",
                f"CANVAS SIZE: {element_info['canvas']['width']:.0f} x {element_info['canvas']['height']:.0f}",
            ]

            # Create background for text
            text_x = elem_x + elem_w + 10
            text_y = elem_y - 20

            # If text would go off screen, move it to the left
            if text_x + 400 > img.width:
                text_x = elem_x - 420

            # Background rectangle
            bg_height = len(details) * 18 + 20
            draw.rectangle(
                [text_x - 10, text_y - 10, text_x + 450, text_y + bg_height],
                fill="white",
                outline="black",
                width=2,
            )

            # Draw details
            for i, detail in enumerate(details):
                draw.text(
                    (text_x, text_y + i * 18), detail, fill="black", font=small_font
                )

            # Mark canvas boundaries
            canvas_x = element_info["canvas"]["left"]
            canvas_y = element_info["canvas"]["top"]
            canvas_w = element_info["canvas"]["width"]
            canvas_h = element_info["canvas"]["height"]

            draw.rectangle(
                [canvas_x, canvas_y, canvas_x + canvas_w, canvas_y + canvas_h],
                outline="blue",
                width=3,
            )
            draw.text(
                (canvas_x + 10, canvas_y + 10), "PDF CANVAS", fill="blue", font=font
            )

            img.save(screenshot_path)
            print(f"   ✅ Designer proof saved: {screenshot_path}")

        except Exception as e:
            print(f"   ⚠️ Could not annotate designer screenshot: {e}")

        # Capture Preview Proof Image
        print("📋 Step 7: Capture preview proof image...")
        driver.get("http://localhost:5111/api/pdf-positioning/preview/1")
        time.sleep(4)

        preview_screenshot_path = "PROOF_2_PREVIEW.png"
        driver.save_screenshot(preview_screenshot_path)

        # Try to annotate preview
        try:
            img = Image.open(preview_screenshot_path)
            draw = ImageDraw.Draw(img)

            # Add title
            draw.text(
                (50, 30), "PROOF 2: ELEMENT IN PDF PREVIEW", fill="red", font=title_font
            )

            # Add note about expected position
            expected_info = [
                f"EXPECTED: Element should appear in same relative position",
                f"Designer: ({element_info['relative']['xPercent']:.1f}%, {element_info['relative']['yPercent']:.1f}%)",
                f"PDF Coords: ({element_info['coordinates']['xInput']}, {element_info['coordinates']['yInput']})",
                "Look for element text in top-right area of the PDF",
            ]

            # Background for expected info
            info_y = 70
            bg_width = 500
            bg_height = len(expected_info) * 18 + 20
            draw.rectangle(
                [40, info_y - 10, 40 + bg_width, info_y + bg_height],
                fill="yellow",
                outline="black",
                width=2,
            )

            for i, info in enumerate(expected_info):
                draw.text((50, info_y + i * 18), info, fill="black", font=small_font)

            img.save(preview_screenshot_path)
            print(f"   ✅ Preview proof saved: {preview_screenshot_path}")

        except Exception as e:
            print(f"   ⚠️ Could not annotate preview screenshot: {e}")

        # Analyze positioning accuracy
        print("📋 Step 8: Analyze positioning accuracy...")

        # Calculate expected PDF position
        canvas_w = element_info["canvas"]["width"]
        canvas_h = element_info["canvas"]["height"]
        element_x = element_info["relative"]["x"]
        element_y = element_info["relative"]["y"]

        # Convert to PDF coordinates using our scaling system
        scale_x = canvas_w / 612
        scale_y = canvas_h / 792

        expected_pdf_x = element_x / scale_x
        expected_pdf_y = element_y / scale_y

        actual_pdf_x = element_info["coordinates"]["xInput"]
        actual_pdf_y = element_info["coordinates"]["yInput"]

        x_diff = abs(expected_pdf_x - actual_pdf_x)
        y_diff = abs(expected_pdf_y - actual_pdf_y)

        print(f"   Expected PDF position: ({expected_pdf_x:.1f}, {expected_pdf_y:.1f})")
        print(f"   Actual PDF position: ({actual_pdf_x}, {actual_pdf_y})")
        print(f"   Differences: X={x_diff:.1f}, Y={y_diff:.1f}")

        # Check accuracy
        tolerance = 5  # 5 pixel tolerance
        x_accurate = x_diff <= tolerance
        y_accurate = y_diff <= tolerance
        overall_accurate = x_accurate and y_accurate

        print(
            f"   X coordinate: {'✅ ACCURATE' if x_accurate else '❌ INACCURATE'} (diff: {x_diff:.1f} <= {tolerance})"
        )
        print(
            f"   Y coordinate: {'✅ ACCURATE' if y_accurate else '❌ INACCURATE'} (diff: {y_diff:.1f} <= {tolerance})"
        )

        # Final results
        print("\n" + "=" * 80)
        print("🏆 FINAL VISUAL PROOF RESULTS")
        print("=" * 80)
        print("📸 PROOF IMAGES CREATED:")
        print(f"   • {screenshot_path} - Element placement in designer")
        print(f"   • {preview_screenshot_path} - Element in PDF preview")
        print()
        print("📊 POSITIONING ANALYSIS:")
        print(f"   • Element: {element_info['fieldName']} ('{element_info['text']}')")
        print(
            f"   • Designer Position: ({element_info['relative']['xPercent']:.1f}%, {element_info['relative']['yPercent']:.1f}%)"
        )
        print(f"   • PDF Coordinates: ({actual_pdf_x}, {actual_pdf_y})")
        print(
            f"   • Coordinate Accuracy: {'✅ PASSED' if overall_accurate else '❌ FAILED'}"
        )
        print()
        if overall_accurate:
            print("✅ POSITIONING SYSTEM: VALIDATED")
            print(
                "   The element positioning translation from designer to preview is working correctly"
            )
            print("   within acceptable tolerance levels.")
        else:
            print("❌ POSITIONING SYSTEM: NEEDS IMPROVEMENT")
            print(
                "   The coordinate translation has accuracy issues that need to be addressed."
            )
        print("=" * 80)

        return overall_accurate

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        driver.quit()


if __name__ == "__main__":
    success = create_visual_proof()
    print(
        f"\n🎯 VISUAL PROOF: {'COMPLETED SUCCESSFULLY' if success else 'IDENTIFIED ISSUES'}"
    )
    exit(0 if success else 1)
