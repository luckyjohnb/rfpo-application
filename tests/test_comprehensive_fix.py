#!/usr/bin/env python3
"""
Comprehensive test to identify and fix all PDF positioning editor issues
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


def test_comprehensive_fix():
    """Test all fixes comprehensively"""
    driver = setup_driver()
    if not driver:
        return

    try:
        print("🔍 Testing Comprehensive PDF Editor Fixes...")

        # Login
        driver.get("http://localhost:5111/")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "email"))
        )
        driver.find_element(By.NAME, "email").send_keys("admin@rfpo.com")
        driver.find_element(By.NAME, "password").send_keys("admin123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        print("✅ Login successful")

        # Navigate to PDF editor
        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "pdf-canvas"))
        )
        print("✅ PDF Editor loaded")

        # Wait for initialization
        time.sleep(3)

        # Test 1: Check for JavaScript errors
        print("\n🔧 Test 1: JavaScript Errors")
        try:
            logs = driver.get_log("browser")
            js_errors = [log for log in logs if log["level"] == "SEVERE"]
            if js_errors:
                print(f"❌ JavaScript Errors found:")
                for error in js_errors[:3]:
                    print(f"   {error['message'][:100]}...")
            else:
                print("✅ No severe JavaScript errors")
        except:
            print("   Could not retrieve console logs")

        # Test 2: Check template variables
        print("\n🔧 Test 2: Template Variables")
        js_vars = driver.execute_script(
            """
            return {
                configId: typeof CONFIG_ID !== 'undefined' ? CONFIG_ID : 'undefined',
                positioningData: typeof POSITIONING_DATA !== 'undefined' ? 'defined' : 'undefined',
                fieldDescriptions: typeof FIELD_DESCRIPTIONS !== 'undefined' ? Object.keys(FIELD_DESCRIPTIONS).length : 'undefined'
            };
        """
        )

        print(f"   CONFIG_ID: {js_vars['configId']}")
        print(f"   POSITIONING_DATA: {js_vars['positioningData']}")
        print(f"   FIELD_DESCRIPTIONS: {js_vars['fieldDescriptions']} fields")

        if (
            js_vars["configId"] != "undefined"
            and js_vars["positioningData"] != "undefined"
        ):
            print("✅ Template variables properly loaded")
        else:
            print("❌ Template variables missing")

        # Test 3: Check Available Fields population
        print("\n🔧 Test 3: Available Fields")
        try:
            fields_container = driver.find_element(By.ID, "fields-list")
            field_items = driver.find_elements(
                By.CSS_SELECTOR, "#fields-list .list-group-item"
            )
            print(f"   Available fields count: {len(field_items)}")

            if len(field_items) > 0:
                print("✅ Available fields populated")
                for i, item in enumerate(field_items[:3]):
                    text = item.text.strip().replace("\n", " | ")[:50]
                    print(f"     {i+1}. {text}...")
            else:
                print("❌ No available fields found")

                # Try to populate them manually
                print("   Attempting manual population...")
                driver.execute_script(
                    """
                    if (typeof FIELD_DESCRIPTIONS !== 'undefined' && document.getElementById('fields-list')) {
                        const fieldsList = document.getElementById('fields-list');
                        fieldsList.innerHTML = '';
                        
                        Object.keys(FIELD_DESCRIPTIONS).forEach(fieldName => {
                            const item = document.createElement('div');
                            item.className = 'list-group-item list-group-item-action';
                            item.draggable = true;
                            item.dataset.fieldName = fieldName;
                            
                            item.innerHTML = `
                                <div class="d-flex w-100 justify-content-between">
                                    <h6 class="mb-1">${FIELD_DESCRIPTIONS[fieldName]}</h6>
                                    <small class="text-muted">📋 Available</small>
                                </div>
                                <p class="mb-1 small text-muted">${fieldName}</p>
                                <small class="text-muted"><i class="fas fa-arrows-alt"></i> Drag to canvas</small>
                            `;
                            
                            item.addEventListener('dragstart', function(e) {
                                e.dataTransfer.setData('text/plain', fieldName);
                                e.dataTransfer.effectAllowed = 'copy';
                                console.log('Started dragging field:', fieldName);
                            });
                            
                            fieldsList.appendChild(item);
                        });
                        
                        console.log('Manually populated fields');
                        return Object.keys(FIELD_DESCRIPTIONS).length;
                    }
                    return 0;
                """
                )
                time.sleep(1)
                field_items_after = driver.find_elements(
                    By.CSS_SELECTOR, "#fields-list .list-group-item"
                )
                print(f"   Fields after manual population: {len(field_items_after)}")
        except Exception as e:
            print(f"❌ Error checking fields: {e}")

        # Test 4: Check PDF background
        print("\n🔧 Test 4: PDF Background")
        canvas = driver.find_element(By.ID, "pdf-canvas")
        canvas_style = driver.execute_script(
            """
            const canvas = document.getElementById('pdf-canvas');
            const style = window.getComputedStyle(canvas);
            return {
                backgroundImage: style.backgroundImage,
                backgroundSize: style.backgroundSize,
                width: canvas.offsetWidth,
                height: canvas.offsetHeight
            };
        """
        )

        print(f"   Canvas dimensions: {canvas_style['width']}x{canvas_style['height']}")
        print(f"   Background image: {canvas_style['backgroundImage'][:50]}...")
        print(f"   Background size: {canvas_style['backgroundSize']}")

        if canvas_style["backgroundImage"] != "none":
            print("✅ PDF background image loaded")
        else:
            print("❌ PDF background image not loaded")

            # Try to reload background
            print("   Attempting to reload background...")
            driver.execute_script(
                """
                const canvas = document.getElementById('pdf-canvas');
                const imageUrl = '/api/pdf-template-image/po_template?v=' + Date.now();
                console.log('Loading background:', imageUrl);
                canvas.style.backgroundImage = `url('${imageUrl}')`;
            """
            )
            time.sleep(2)

            canvas_style_after = driver.execute_script(
                """
                const canvas = document.getElementById('pdf-canvas');
                const style = window.getComputedStyle(canvas);
                return style.backgroundImage;
            """
            )
            print(f"   Background after reload: {canvas_style_after[:50]}...")

        # Test 5: Check existing positioned fields
        print("\n🔧 Test 5: Existing Positioned Fields")
        positioned_fields = driver.find_elements(
            By.CSS_SELECTOR, "#pdf-canvas .pdf-field"
        )
        print(f"   Positioned fields on canvas: {len(positioned_fields)}")

        if len(positioned_fields) > 0:
            print("✅ Found positioned fields")
            for i, field in enumerate(positioned_fields[:3]):
                field_info = driver.execute_script(
                    """
                    const field = arguments[0];
                    const style = window.getComputedStyle(field);
                    return {
                        text: field.textContent,
                        left: style.left,
                        top: style.top,
                        background: style.backgroundColor,
                        border: style.border,
                        zIndex: style.zIndex
                    };
                """,
                    field,
                )
                print(
                    f"     {i+1}. '{field_info['text'][:20]}' at {field_info['left']},{field_info['top']}"
                )
                print(
                    f"         Style: bg={field_info['background'][:20]}, border={field_info['border'][:20]}, z-index={field_info['zIndex']}"
                )
        else:
            print("❌ No positioned fields found")

        # Test 6: Test button functionality
        print("\n🔧 Test 6: Button Functionality")
        try:
            save_btn = driver.find_element(By.ID, "save-config")
            preview_btn = driver.find_element(By.ID, "preview-pdf")
            clear_btn = driver.find_element(By.ID, "clear-canvas")
            refresh_btn = driver.find_element(
                By.CSS_SELECTOR, "button[onclick='refreshBackground()']"
            )

            print(f"   Save button: {'✅ Found' if save_btn else '❌ Missing'}")
            print(f"   Preview button: {'✅ Found' if preview_btn else '❌ Missing'}")
            print(f"   Clear button: {'✅ Found' if clear_btn else '❌ Missing'}")
            print(f"   Refresh button: {'✅ Found' if refresh_btn else '❌ Missing'}")

            # Test save button click
            print("   Testing save button...")
            driver.execute_script("arguments[0].click();", save_btn)
            time.sleep(1)
            print("   Save button clicked successfully")

        except Exception as e:
            print(f"❌ Error testing buttons: {e}")

        print(f"\n👀 Keeping browser open for 30 seconds for manual inspection...")
        time.sleep(30)

    except Exception as e:
        print(f"❌ Error during comprehensive test: {e}")
        import traceback

        traceback.print_exc()

    finally:
        driver.quit()
        print("🔚 Comprehensive test completed")


if __name__ == "__main__":
    test_comprehensive_fix()
