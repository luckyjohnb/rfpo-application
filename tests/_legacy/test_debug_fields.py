#!/usr/bin/env python3
"""
Debug the Available Fields loading issue
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


def debug_fields_loading():
    """Debug why Available Fields are not loading"""
    driver = setup_driver()
    if not driver:
        return

    try:
        print("🔍 Debugging Available Fields Loading...")

        # Login and navigate
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

        # Wait a bit for JavaScript to initialize
        time.sleep(3)

        # Check if Available Fields container exists
        try:
            fields_container = driver.find_element(By.ID, "fields-list")
            print("✅ fields-list container found")
        except:
            print("❌ fields-list container NOT found")
            return

        # Check what's in the container
        field_items = driver.find_elements(
            By.CSS_SELECTOR, "#fields-list .list-group-item"
        )
        print(f"📊 Current field items: {len(field_items)}")

        # Check JavaScript variables
        js_debug = driver.execute_script(
            """
            return {
                configId: typeof CONFIG_ID !== 'undefined' ? CONFIG_ID : 'undefined',
                positioningData: typeof POSITIONING_DATA !== 'undefined' ? Object.keys(POSITIONING_DATA) : 'undefined',
                fieldDescriptions: typeof FIELD_DESCRIPTIONS !== 'undefined' ? Object.keys(FIELD_DESCRIPTIONS) : 'undefined',
                populateFunction: typeof populateFieldsList === 'function',
                jsErrors: window.jsErrors || []
            };
        """
        )

        print(f"🔧 JavaScript Debug Info:")
        print(f"   CONFIG_ID: {js_debug['configId']}")
        print(f"   POSITIONING_DATA keys: {js_debug['positioningData']}")
        print(f"   FIELD_DESCRIPTIONS keys: {js_debug['fieldDescriptions']}")
        print(f"   populateFieldsList function exists: {js_debug['populateFunction']}")
        print(f"   JS Errors: {js_debug['jsErrors']}")

        # Check if the page loaded properly
        page_title = driver.title
        print(f"📄 Page Title: {page_title}")

        # Check for JavaScript errors in console
        try:
            logs = driver.get_log("browser")
            js_errors = [log for log in logs if log["level"] == "SEVERE"]
            if js_errors:
                print(f"❌ JavaScript Errors found:")
                for error in js_errors[:5]:  # Show first 5 errors
                    print(f"   {error['message']}")
            else:
                print("✅ No severe JavaScript errors found")
        except:
            print("   Could not retrieve console logs")

        # Check if template variables are being rendered
        template_check = driver.execute_script(
            """
            // Look for template syntax in the page source
            var pageSource = document.documentElement.outerHTML;
            return {
                hasTemplateVars: pageSource.includes('{{') || pageSource.includes('{%'),
                hasConfigObject: pageSource.includes('CONFIG_ID'),
                hasFieldDescriptions: pageSource.includes('FIELD_DESCRIPTIONS'),
                scriptTags: document.querySelectorAll('script').length
            };
        """
        )

        print(f"🔧 Template Check:")
        print(f"   Has unrendered template vars: {template_check['hasTemplateVars']}")
        print(f"   Has CONFIG_ID in page: {template_check['hasConfigObject']}")
        print(
            f"   Has FIELD_DESCRIPTIONS in page: {template_check['hasFieldDescriptions']}"
        )
        print(f"   Number of script tags: {template_check['scriptTags']}")

        # Try to manually fix the issue
        if js_debug["fieldDescriptions"] == "undefined":
            print("\n🔧 FIELD_DESCRIPTIONS is undefined, trying to fix...")

            # Check if we can get the config from the backend
            config_data = driver.execute_script(
                """
                return fetch('/api/pdf-positioning/1')
                    .then(response => response.json())
                    .then(data => data)
                    .catch(error => ({error: error.message}));
            """
            )

            print(f"   Backend config fetch result: {config_data}")

            # Define FIELD_DESCRIPTIONS manually and populate
            driver.execute_script(
                """
                window.FIELD_DESCRIPTIONS = {
                    'po_number': 'Purchase Order Number',
                    'po_date': 'Purchase Order Date',
                    'vendor_company': 'Vendor Company Name',
                    'vendor_contact': 'Vendor Contact Person',
                    'vendor_address': 'Vendor Address',
                    'vendor_phone': 'Vendor Phone Number',
                    'ship_to_name': 'Ship To Name',
                    'ship_to_address': 'Ship To Address',
                    'delivery_type': 'Delivery Type & Place',
                    'delivery_payment': 'Payment for Transportation'
                };
                
                // Clear and populate fields list
                const fieldsList = document.getElementById('fields-list');
                if (fieldsList) {
                    fieldsList.innerHTML = '';
                    
                    Object.keys(window.FIELD_DESCRIPTIONS).forEach(fieldName => {
                        const item = document.createElement('div');
                        item.className = 'list-group-item list-group-item-action';
                        item.draggable = true;
                        item.dataset.fieldName = fieldName;
                        
                        item.innerHTML = `
                            <div class="d-flex w-100 justify-content-between">
                                <h6 class="mb-1">${window.FIELD_DESCRIPTIONS[fieldName]}</h6>
                                <small class="text-muted">📋 Available</small>
                            </div>
                            <p class="mb-1 small text-muted">${fieldName}</p>
                            <small class="text-muted"><i class="fas fa-arrows-alt"></i> Drag to canvas</small>
                        `;
                        
                        // Add drag event listener
                        item.addEventListener('dragstart', function(e) {
                            e.dataTransfer.setData('text/plain', fieldName);
                            e.dataTransfer.effectAllowed = 'copy';
                            console.log('Started dragging field:', fieldName);
                        });
                        
                        fieldsList.appendChild(item);
                    });
                    
                    console.log('Manually populated', Object.keys(window.FIELD_DESCRIPTIONS).length, 'fields');
                }
            """
            )

            time.sleep(1)

            # Check if fields were created
            field_items_after = driver.find_elements(
                By.CSS_SELECTOR, "#fields-list .list-group-item"
            )
            print(f"✅ Fields after manual population: {len(field_items_after)}")

            if len(field_items_after) > 0:
                print("🎉 Successfully populated Available Fields!")

                # Show the first few fields
                for i, item in enumerate(field_items_after[:3]):
                    text = item.text.strip().replace("\n", " | ")
                    print(f"   {i+1}. {text}")
            else:
                print("❌ Manual population failed")

        print(f"\n👀 Keeping browser open for 60 seconds for manual inspection...")
        time.sleep(60)

    except Exception as e:
        print(f"❌ Error during debug: {e}")
        import traceback

        traceback.print_exc()

    finally:
        driver.quit()
        print("🔚 Debug completed")


if __name__ == "__main__":
    debug_fields_loading()
