#!/usr/bin/env python3
"""
TEST UI DISPLAY FIX
Quick test to verify UI now shows user-friendly coordinates
"""
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--window-size=1400,1000")
    return webdriver.Chrome(options=chrome_options)


def test_ui_display_fix():
    print("🧪 UI DISPLAY FIX TEST")
    print("=" * 50)

    driver = setup_driver()
    session = requests.Session()

    try:
        # Login
        print("📋 Login...")
        driver.get("http://localhost:5111/login")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "email"))
        )

        driver.find_element(By.NAME, "email").send_keys("admin@rfpo.com")
        driver.find_element(By.NAME, "password").send_keys("admin123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)

        login_data = {"email": "admin@rfpo.com", "password": "admin123"}
        session.post("http://localhost:5111/login", data=login_data)
        print("   ✅ Logged in")

        # Navigate to designer
        print("📋 Navigate to designer...")
        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "pdf-canvas"))
        )
        time.sleep(5)

        # Test different positions
        test_positions = [
            {"name": "Top", "screen_y": 30, "description": "Near top of page"},
            {"name": "Middle", "screen_y": 300, "description": "Middle of page"},
            {"name": "Bottom", "screen_y": 700, "description": "Near bottom of page"},
        ]

        for pos in test_positions:
            print(f"\n📋 Testing {pos['name']} position ({pos['description']})...")

            # Clear and place element
            clear_and_place_script = f"""
            // Clear existing
            Object.keys(POSITIONING_DATA).forEach(key => delete POSITIONING_DATA[key]);
            document.querySelectorAll('.pdf-field').forEach(el => el.remove());
            
            // Place element at test position
            const fieldName = 'po_number';
            const screenX = 350;
            const screenY = {pos['screen_y']};
            const pdfX = screenX;
            const pdfY = 792 - screenY;
            
            POSITIONING_DATA[fieldName] = {{
                x: pdfX,
                y: pdfY,
                font_size: 14,
                font_weight: 'bold',
                visible: true
            }};
            
            // Create visual element
            const canvas = document.getElementById('pdf-canvas');
            const fieldElement = document.createElement('div');
            fieldElement.className = 'pdf-field';
            fieldElement.dataset.fieldName = fieldName;
            fieldElement.textContent = 'PO NUMBER';
            fieldElement.style.position = 'absolute';
            fieldElement.style.left = screenX + 'px';
            fieldElement.style.top = screenY + 'px';
            fieldElement.style.fontSize = '14px';
            fieldElement.style.fontWeight = 'bold';
            fieldElement.style.backgroundColor = 'rgba(255, 255, 0, 0.8)';
            fieldElement.style.border = '2px solid blue';
            fieldElement.style.padding = '4px';
            
            canvas.appendChild(fieldElement);
            
            // Select the field to trigger UI update
            selectField(fieldElement);
            
            return {{
                screenX: screenX,
                screenY: screenY,
                pdfX: pdfX,
                pdfY: pdfY
            }};
            """

            result = driver.execute_script(clear_and_place_script)
            time.sleep(2)

            # Check UI display
            ui_check_script = """
            return {
                coordinatesText: document.getElementById('coordinates').textContent,
                fieldXValue: document.getElementById('field-x').value,
                fieldYValue: document.getElementById('field-y').value
            };
            """

            ui_result = driver.execute_script(ui_check_script)

            print(f"   Placed at screen Y: {result['screenY']}")
            print(f"   Stored as PDF Y: {result['pdfY']}")
            print(f"   UI coordinates display: {ui_result['coordinatesText']}")
            print(f"   UI Y input shows: {ui_result['fieldYValue']}")

            # Check if UI shows sensible Y value
            expected_ui_y = result["screenY"]  # Should show distance from top
            actual_ui_y = float(ui_result["fieldYValue"])

            if abs(actual_ui_y - expected_ui_y) < 5:
                print(f"   ✅ UI correctly shows {actual_ui_y} (distance from top)")
            else:
                print(f"   ❌ UI shows {actual_ui_y}, expected ~{expected_ui_y}")

        print(f"\n📸 Taking final screenshot...")
        driver.save_screenshot("UI_DISPLAY_FIX_TEST.png")
        print(f"   Screenshot: UI_DISPLAY_FIX_TEST.png")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        driver.quit()


if __name__ == "__main__":
    success = test_ui_display_fix()

    print(f"\n" + "=" * 50)
    print("🏆 UI DISPLAY FIX RESULTS")
    print("=" * 50)

    if success:
        print("✅ UI Display fix tested")
        print("   Check output above to see if Y coordinates are user-friendly")
    else:
        print("❌ UI Display test failed")

    print("=" * 50)
