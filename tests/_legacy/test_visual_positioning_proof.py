#!/usr/bin/env python3
"""
VISUAL POSITIONING PROOF TEST
Create proof images showing element placement in designer vs preview
Use PO template landmarks to verify positioning accuracy
"""
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image, ImageDraw, ImageFont
import os


def setup_driver():
    """Setup Chrome driver with consistent window size"""
    chrome_options = Options()
    chrome_options.add_argument("--window-size=1400,1000")
    chrome_options.add_argument(
        "--force-device-scale-factor=1"
    )  # Prevent scaling issues
    return webdriver.Chrome(options=chrome_options)


def login_and_navigate(driver):
    """Login and navigate to positioning editor"""
    print("🔐 Logging in and navigating to editor...")

    # Login
    driver.get("http://localhost:5111/login")
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "email")))

    driver.find_element(By.NAME, "email").send_keys("admin@rfpo.com")
    driver.find_element(By.NAME, "password").send_keys("admin123")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

    # Navigate to editor
    driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")

    # Wait for canvas to load
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.ID, "pdf-canvas"))
    )
    time.sleep(3)  # Additional wait for PDF to render

    print("✅ Successfully navigated to positioning editor")
    return True


def clear_canvas(driver):
    """Clear all elements from canvas"""
    try:
        clear_button = driver.find_element(By.ID, "clear-canvas")
        clear_button.click()
        time.sleep(1)
        try:
            driver.switch_to.alert.accept()
        except:
            pass
        time.sleep(2)
        print("✅ Canvas cleared")
        return True
    except Exception as e:
        print(f"⚠️ Could not clear canvas: {e}")
        return False


def get_canvas_info(driver):
    """Get detailed canvas information"""
    canvas_info = driver.execute_script(
        """
        const canvas = document.getElementById('pdf-canvas');
        const rect = canvas.getBoundingClientRect();
        const containerRect = document.getElementById('pdf-canvas-container').getBoundingClientRect();
        
        return {
            canvas: {
                width: rect.width,
                height: rect.height,
                left: rect.left,
                top: rect.top
            },
            container: {
                width: containerRect.width,
                height: containerRect.height,
                left: containerRect.left,
                top: containerRect.top
            },
            viewport: {
                width: window.innerWidth,
                height: window.innerHeight
            }
        };
    """
    )

    print(f"📐 Canvas Info:")
    print(
        f"   Canvas: {canvas_info['canvas']['width']:.1f} x {canvas_info['canvas']['height']:.1f}"
    )
    print(
        f"   Container: {canvas_info['container']['width']:.1f} x {canvas_info['container']['height']:.1f}"
    )
    print(
        f"   Viewport: {canvas_info['viewport']['width']} x {canvas_info['viewport']['height']}"
    )

    return canvas_info


def place_element_at_landmark(driver, canvas_info):
    """Place an element at a specific landmark position on the PO template"""
    print("📍 Placing element at landmark position...")

    # Populate fields list
    driver.execute_script("populateFieldsList();")
    time.sleep(1)

    # Get available fields
    field_buttons = driver.find_elements(
        By.CSS_SELECTOR, "#fields-list .list-group-item"
    )
    if not field_buttons:
        print("❌ No fields found")
        return None

    # Use PO NUMBER field for testing
    po_number_field = None
    for field in field_buttons:
        if (
            "po_number" in field.get_attribute("data-field-name")
            or "PO NUMBER" in field.text.upper()
        ):
            po_number_field = field
            break

    if not po_number_field:
        po_number_field = field_buttons[0]  # Fallback to first field

    field_name = po_number_field.get_attribute("data-field-name")
    print(f"   Using field: {field_name}")

    # Click field to select it
    po_number_field.click()
    time.sleep(0.5)

    # Place at top-right area where PO Number typically goes
    # This should be around the "Number" box in the PO template
    canvas = driver.find_element(By.ID, "pdf-canvas")
    target_x = canvas_info["canvas"]["width"] * 0.75  # 75% to the right
    target_y = canvas_info["canvas"]["height"] * 0.08  # 8% from top

    print(f"   Target position: ({target_x:.1f}, {target_y:.1f})")

    # Click on canvas to place element
    actions = ActionChains(driver)
    actions.move_to_element_with_offset(canvas, target_x, target_y).click().perform()
    time.sleep(1)

    # Verify element was placed
    placed_elements = driver.find_elements(By.CSS_SELECTOR, ".pdf-field")
    if not placed_elements:
        print("❌ Element was not placed")
        return None

    placed_element = placed_elements[0]

    # Get element position info
    element_info = driver.execute_script(
        """
        const element = arguments[0];
        const canvas = document.getElementById('pdf-canvas');
        const canvasRect = canvas.getBoundingClientRect();
        const elementRect = element.getBoundingClientRect();
        
        const relativeX = elementRect.left - canvasRect.left;
        const relativeY = elementRect.top - canvasRect.top;
        
        // Get coordinates from properties panel
        const coordsDisplay = document.getElementById('coordinates').textContent;
        const xInput = document.getElementById('field-x').value;
        const yInput = document.getElementById('field-y').value;
        
        return {
            element: {
                left: elementRect.left,
                top: elementRect.top,
                width: elementRect.width,
                height: elementRect.height
            },
            relative: {
                x: relativeX,
                y: relativeY
            },
            style: {
                left: element.style.left,
                top: element.style.top
            },
            coordinates: {
                display: coordsDisplay,
                xInput: parseInt(xInput),
                yInput: parseInt(yInput)
            },
            fieldName: element.dataset.fieldName,
            text: element.textContent
        };
    """,
        placed_element,
    )

    print(f"✅ Element placed:")
    print(f"   Field: {element_info['fieldName']}")
    print(f"   Text: '{element_info['text']}'")
    print(
        f"   Relative position: ({element_info['relative']['x']:.1f}, {element_info['relative']['y']:.1f})"
    )
    print(
        f"   Style position: {element_info['style']['left']}, {element_info['style']['top']}"
    )
    print(f"   Coordinates display: {element_info['coordinates']['display']}")
    print(
        f"   Input values: X={element_info['coordinates']['xInput']}, Y={element_info['coordinates']['yInput']}"
    )

    return element_info


def save_positioning_data(driver):
    """Save the positioning data"""
    print("💾 Saving positioning data...")

    save_button = driver.find_element(By.ID, "save-config")
    driver.execute_script("arguments[0].scrollIntoView(true);", save_button)
    time.sleep(1)
    driver.execute_script("arguments[0].click();", save_button)
    time.sleep(3)

    print("✅ Positioning data saved")


def capture_designer_proof(driver, element_info, canvas_info):
    """Capture designer screenshot with annotations"""
    print("📸 Capturing designer proof screenshot...")

    # Take screenshot
    screenshot_path = "proof_1_designer.png"
    driver.save_screenshot(screenshot_path)

    # Add annotations using PIL
    try:
        img = Image.open(screenshot_path)
        draw = ImageDraw.Draw(img)

        # Try to load a font, fallback to default if not available
        try:
            font = ImageFont.truetype("Arial.ttf", 16)
            small_font = ImageFont.truetype("Arial.ttf", 12)
        except:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        # Mark element position
        element_x = element_info["element"]["left"]
        element_y = element_info["element"]["top"]
        element_w = element_info["element"]["width"]
        element_h = element_info["element"]["height"]

        # Draw rectangle around element
        draw.rectangle(
            [
                element_x - 2,
                element_y - 2,
                element_x + element_w + 2,
                element_y + element_h + 2,
            ],
            outline="red",
            width=3,
        )

        # Add label
        label_text = f"ELEMENT: {element_info['fieldName']}"
        coord_text = f"Position: ({element_info['relative']['x']:.0f}, {element_info['relative']['y']:.0f})"
        pdf_coord_text = f"PDF: ({element_info['coordinates']['xInput']}, {element_info['coordinates']['yInput']})"

        # Background for text
        label_bbox = draw.textbbox((0, 0), label_text, font=font)
        coord_bbox = draw.textbbox((0, 0), coord_text, font=small_font)
        pdf_bbox = draw.textbbox((0, 0), pdf_coord_text, font=small_font)

        text_x = element_x
        text_y = element_y - 60

        # Draw background rectangles
        draw.rectangle(
            [
                text_x - 5,
                text_y - 5,
                text_x + max(label_bbox[2], coord_bbox[2], pdf_bbox[2]) + 5,
                text_y + 50,
            ],
            fill="white",
            outline="black",
        )

        # Draw text
        draw.text((text_x, text_y), label_text, fill="red", font=font)
        draw.text((text_x, text_y + 18), coord_text, fill="black", font=small_font)
        draw.text((text_x, text_y + 32), pdf_coord_text, fill="blue", font=small_font)

        # Mark canvas boundaries
        canvas_x = canvas_info["canvas"]["left"]
        canvas_y = canvas_info["canvas"]["top"]
        canvas_w = canvas_info["canvas"]["width"]
        canvas_h = canvas_info["canvas"]["height"]

        draw.rectangle(
            [canvas_x, canvas_y, canvas_x + canvas_w, canvas_y + canvas_h],
            outline="blue",
            width=2,
        )

        # Add canvas info
        canvas_label = f"CANVAS: {canvas_w:.0f}x{canvas_h:.0f}"
        draw.text(
            (canvas_x + 10, canvas_y + 10), canvas_label, fill="blue", font=small_font
        )

        img.save(screenshot_path)
        print(f"✅ Designer proof saved: {screenshot_path}")

    except Exception as e:
        print(f"⚠️ Could not annotate screenshot: {e}")


def capture_preview_proof(driver, element_info):
    """Capture preview screenshot and analyze positioning"""
    print("📸 Capturing preview proof screenshot...")

    # Navigate to preview
    driver.get("http://localhost:5111/api/pdf-positioning/preview/1")
    time.sleep(4)  # Wait for PDF to load

    # Take screenshot
    screenshot_path = "proof_2_preview.png"
    driver.save_screenshot(screenshot_path)

    # Try to analyze the preview content
    try:
        page_text = driver.execute_script("return document.body.innerText;")
        if len(page_text) > 50:
            print("✅ Preview generated with content")
            print(f"   Content length: {len(page_text)} characters")

            # Look for our field content
            lines = page_text.split("\n")
            for i, line in enumerate(lines[:20]):
                if line.strip() and len(line.strip()) > 2:
                    print(
                        f"   Line {i+1}: '{line.strip()[:50]}{'...' if len(line.strip()) > 50 else ''}'"
                    )
        else:
            print("⚠️ Preview has minimal content")
    except Exception as e:
        print(f"⚠️ Could not analyze preview content: {e}")

    print(f"✅ Preview proof saved: {screenshot_path}")


def analyze_positioning_accuracy(element_info, canvas_info):
    """Analyze the positioning accuracy"""
    print("\n🔍 POSITIONING ACCURACY ANALYSIS:")
    print("=" * 60)

    # Canvas dimensions
    canvas_w = canvas_info["canvas"]["width"]
    canvas_h = canvas_info["canvas"]["height"]

    # Element position in canvas
    element_x = element_info["relative"]["x"]
    element_y = element_info["relative"]["y"]

    # Calculate relative position
    rel_x_percent = (element_x / canvas_w) * 100
    rel_y_percent = (element_y / canvas_h) * 100

    print(f"📐 Canvas Dimensions: {canvas_w:.1f} x {canvas_h:.1f}")
    print(f"📍 Element Position: ({element_x:.1f}, {element_y:.1f})")
    print(f"📊 Relative Position: ({rel_x_percent:.1f}%, {rel_y_percent:.1f}%)")
    print(
        f"🎯 PDF Coordinates: ({element_info['coordinates']['xInput']}, {element_info['coordinates']['yInput']})"
    )

    # Expected PDF position based on our coordinate conversion
    expected_pdf_x = element_x / (canvas_w / 612)
    expected_pdf_y = element_y / (canvas_h / 792)

    print(f"🧮 Expected PDF Position: ({expected_pdf_x:.1f}, {expected_pdf_y:.1f})")

    # Compare with actual stored coordinates
    actual_pdf_x = element_info["coordinates"]["xInput"]
    actual_pdf_y = element_info["coordinates"]["yInput"]

    x_diff = abs(expected_pdf_x - actual_pdf_x)
    y_diff = abs(expected_pdf_y - actual_pdf_y)

    print(f"📏 Coordinate Differences: X={x_diff:.1f}, Y={y_diff:.1f}")

    # Check if differences are acceptable (within 5 pixels)
    tolerance = 5
    x_ok = x_diff <= tolerance
    y_ok = y_diff <= tolerance

    print(
        f"✅ X coordinate {'OK' if x_ok else 'FAILED'} (diff: {x_diff:.1f} <= {tolerance})"
    )
    print(
        f"✅ Y coordinate {'OK' if y_ok else 'FAILED'} (diff: {y_diff:.1f} <= {tolerance})"
    )

    if x_ok and y_ok:
        print("🎉 POSITIONING ACCURACY: PASSED")
        return True
    else:
        print("💥 POSITIONING ACCURACY: FAILED")
        return False


def main():
    """Main test function"""
    print("🎯 VISUAL POSITIONING PROOF TEST")
    print("=" * 80)
    print("Creating proof images showing element placement accuracy")
    print()

    driver = setup_driver()

    try:
        # Step 1: Setup
        if not login_and_navigate(driver):
            print("❌ Failed to setup")
            return False

        # Step 2: Clear canvas
        clear_canvas(driver)

        # Step 3: Get canvas info
        canvas_info = get_canvas_info(driver)

        # Step 4: Place element at landmark
        element_info = place_element_at_landmark(driver, canvas_info)
        if not element_info:
            print("❌ Failed to place element")
            return False

        # Step 5: Save positioning data
        save_positioning_data(driver)

        # Step 6: Capture designer proof
        capture_designer_proof(driver, element_info, canvas_info)

        # Step 7: Capture preview proof
        capture_preview_proof(driver, element_info)

        # Step 8: Analyze accuracy
        accuracy_ok = analyze_positioning_accuracy(element_info, canvas_info)

        print("\n" + "=" * 80)
        print("🏆 VISUAL PROOF RESULTS")
        print("=" * 80)
        print("📸 Proof Images Created:")
        print("   • proof_1_designer.png - Shows element placement in designer")
        print("   • proof_2_preview.png - Shows element in PDF preview")
        print()
        if accuracy_ok:
            print("✅ POSITIONING ACCURACY: VALIDATED")
            print("   Coordinate conversion is working correctly")
        else:
            print("❌ POSITIONING ACCURACY: FAILED")
            print("   Coordinate conversion needs fixing")
        print("=" * 80)

        return accuracy_ok

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        driver.quit()


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
