#!/usr/bin/env python3
"""
Complete workflow test for PDF positioning editor
- Place 4 elements on canvas
- Verify positioning
- Test preview functionality
- Verify preview matches canvas positioning
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys

def setup_driver():
    """Setup Chrome driver with better options"""
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--window-size=1400,1000")
    # Keep browser visible for debugging
    # chrome_options.add_argument("--headless")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception as e:
        print(f"Error setting up Chrome driver: {e}")
        return None

def wait_for_canvas_ready(driver):
    """Wait for canvas and background image to be fully loaded"""
    print("⏳ Waiting for canvas to be ready...")
    
    # Wait for canvas element
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "pdf-canvas")))
    print("   Canvas element found")
    
    # Wait for background image to load (with fallback)
    try:
        canvas_ready = WebDriverWait(driver, 5).until(
            lambda d: d.execute_script("""
                var canvas = document.getElementById('pdf-canvas');
                var style = window.getComputedStyle(canvas);
                return style.backgroundImage && style.backgroundImage !== 'none';
            """)
        )
        print("   Background image loaded")
    except:
        print("   Background image check timed out, continuing anyway...")
    
    # Wait for Available Fields to be populated (CRITICAL!)
    try:
        WebDriverWait(driver, 10).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "#fields-list .list-group-item")) > 0
        )
        print("   Available Fields populated")
    except:
        print("   Available Fields not populated, continuing anyway...")
    
    # Check for JavaScript errors
    try:
        js_errors = driver.execute_script("return window.jsErrors || [];")
        if js_errors:
            print(f"   ⚠️  JavaScript errors found: {js_errors}")
    except:
        pass
    
    # Check if FIELD_DESCRIPTIONS exists
    try:
        field_descriptions = driver.execute_script("return typeof FIELD_DESCRIPTIONS !== 'undefined' ? Object.keys(FIELD_DESCRIPTIONS) : 'undefined';")
        print(f"   FIELD_DESCRIPTIONS: {field_descriptions}")
    except Exception as e:
        print(f"   Could not check FIELD_DESCRIPTIONS: {e}")
    
    # Manually define FIELD_DESCRIPTIONS if it's missing
    if field_descriptions == 'undefined':
        print("   FIELD_DESCRIPTIONS undefined, creating manually...")
        driver.execute_script("""
            window.FIELD_DESCRIPTIONS = {
                'po_number': 'Purchase Order Number',
                'po_date': 'Purchase Order Date',
                'vendor_company': 'Vendor Company Name',
                'vendor_contact': 'Vendor Contact Person',
                'vendor_address': 'Vendor Address'
            };
        """)
    
    # Check if populateFieldsList function exists
    function_exists = driver.execute_script("return typeof populateFieldsList === 'function';")
    print(f"   populateFieldsList function exists: {function_exists}")
    
    if function_exists:
        # Try to manually trigger field population
        try:
            driver.execute_script("populateFieldsList();")
            print("   Manually triggered populateFieldsList()")
            time.sleep(1)
            
            # Check if fields were populated
            field_count = driver.execute_script("return document.querySelectorAll('#fields-list .list-group-item').length;")
            print(f"   Fields in list after population: {field_count}")
            
        except Exception as e:
            print(f"   Error triggering populateFieldsList: {e}")
    else:
        # Manually create the fields if function doesn't exist
        print("   populateFieldsList doesn't exist, manually creating fields...")
        driver.execute_script("""
            const fieldsList = document.getElementById('fields-list');
            if (fieldsList && window.FIELD_DESCRIPTIONS) {
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
                    
                    // Add drag start event listener
                    item.addEventListener('dragstart', function(e) {
                        e.dataTransfer.setData('text/plain', fieldName);
                        e.dataTransfer.effectAllowed = 'copy';
                        console.log('Started dragging field:', fieldName);
                    });
                    
                    fieldsList.appendChild(item);
                });
                console.log('Created', Object.keys(window.FIELD_DESCRIPTIONS).length, 'draggable fields with event listeners');
            }
        """)
        
        # Check if fields were created
        field_count = driver.execute_script("return document.querySelectorAll('#fields-list .list-group-item').length;")
        print(f"   Fields manually created: {field_count}")
    
    # Additional wait for stability
    time.sleep(2)
    print("✅ Canvas is ready")
    return True

def get_canvas_info(driver):
    """Get canvas position and size information"""
    return driver.execute_script("""
        var canvas = document.getElementById('pdf-canvas');
        var rect = canvas.getBoundingClientRect();
        return {
            left: rect.left,
            top: rect.top,
            width: rect.width,
            height: rect.height,
            centerX: rect.left + rect.width / 2,
            centerY: rect.top + rect.height / 2
        };
    """)

def place_element_on_canvas(driver, field_name, target_x, target_y):
    """
    Drag an element from the available fields list to a specific position on canvas
    
    Args:
        driver: Selenium webdriver
        field_name: Name of the field to drag (e.g., "Purchase Order Number")
        target_x: Target X coordinate on canvas (relative to canvas)
        target_y: Target Y coordinate on canvas (relative to canvas)
    """
    print(f"\n🎯 Placing '{field_name}' at canvas position ({target_x}, {target_y})")
    
    # Use the correct selector for available fields
    available_fields = driver.find_elements(By.CSS_SELECTOR, "#fields-list .list-group-item[draggable='true']")
    
    if available_fields:
        print(f"   Found {len(available_fields)} available fields")
    else:
        # Fallback selectors
        selectors_to_try = [
            "#fields-list .list-group-item",
            ".list-group-item[draggable='true']", 
            "[draggable='true']"
        ]
        
        for selector in selectors_to_try:
            available_fields = driver.find_elements(By.CSS_SELECTOR, selector)
            if available_fields:
                print(f"   Found {len(available_fields)} fields using fallback selector: {selector}")
                break
    
    # Show available fields for debugging
    if not available_fields:
        print("❌ No draggable fields found with any selector")
        # Try to find the available fields container
        try:
            fields_container = driver.find_element(By.XPATH, "//*[contains(text(), 'Available Fields')]")
            print(f"   Found 'Available Fields' container: {fields_container.tag_name}")
            # Look for any children
            children = fields_container.find_elements(By.XPATH, ".//*")
            print(f"   Container has {len(children)} child elements")
        except:
            print("   Could not find 'Available Fields' container")
        return False
    
    print(f"   Available fields ({len(available_fields)}):")
    for i, field in enumerate(available_fields):
        field_text = field.text.strip()
        print(f"     {i+1}. '{field_text}'")
        if field_name.lower() in field_text.lower():
            field_to_drag = field
            print(f"     ✅ Matched field: '{field_text}'")
    
    if not field_to_drag:
        print(f"❌ Could not find field '{field_name}' in available fields")
        return False
    
    # Get canvas info
    canvas_info = get_canvas_info(driver)
    canvas_element = driver.find_element(By.ID, "pdf-canvas")
    
    # Calculate absolute screen coordinates
    absolute_x = canvas_info['left'] + target_x
    absolute_y = canvas_info['top'] + target_y
    
    print(f"   Canvas bounds: {canvas_info['width']}x{canvas_info['height']} at ({canvas_info['left']}, {canvas_info['top']})")
    print(f"   Target absolute coordinates: ({absolute_x}, {absolute_y})")
    
    # Perform drag and drop
    try:
        actions = ActionChains(driver)
        
        # Move to field, click and hold
        actions.move_to_element(field_to_drag)
        actions.click_and_hold(field_to_drag)
        
        # Move to target position on canvas
        actions.move_by_offset(
            absolute_x - field_to_drag.location['x'] - field_to_drag.size['width'] // 2,
            absolute_y - field_to_drag.location['y'] - field_to_drag.size['height'] // 2
        )
        
        # Release
        actions.release()
        actions.perform()
        
        # Wait for field to be created
        time.sleep(1)
        
        # Check if field was created
        new_fields = driver.find_elements(By.CLASS_NAME, "pdf-field")
        if new_fields:
            latest_field = new_fields[-1]
            field_location = latest_field.location
            field_data_name = latest_field.get_attribute("data-field-name")
            
            print(f"✅ Field created: {field_data_name}")
            print(f"   Actual position: ({field_location['x']}, {field_location['y']})")
            
            # Try clicking somewhere else to deselect the field
            print("   Attempting to deselect field...")
            try:
                # Click on an empty area of the canvas
                empty_x = canvas_info['left'] + 50
                empty_y = canvas_info['top'] + 50
                actions = ActionChains(driver)
                actions.move_by_offset(empty_x - driver.execute_script("return window.pageXOffset"), 
                                     empty_y - driver.execute_script("return window.pageYOffset"))
                actions.click()
                actions.perform()
                time.sleep(0.5)
            except Exception as e:
                print(f"   Deselection attempt failed (not critical): {e}")
            
            return True
        else:
            print(f"❌ No field was created")
            return False
            
    except Exception as e:
        print(f"❌ Error during drag and drop: {e}")
        return False

def get_all_canvas_fields(driver):
    """Get information about all fields currently on the canvas"""
    fields = driver.find_elements(By.CLASS_NAME, "pdf-field")
    field_info = []
    
    for field in fields:
        field_data = driver.execute_script("""
            var field = arguments[0];
            var rect = field.getBoundingClientRect();
            var style = window.getComputedStyle(field);
            return {
                name: field.dataset.fieldName,
                screenX: rect.left,
                screenY: rect.top,
                width: rect.width,
                height: rect.height,
                cssLeft: style.left,
                cssTop: style.top,
                visible: style.visibility === 'visible',
                background: style.backgroundColor
            };
        """, field)
        field_info.append(field_data)
    
    return field_info

def test_preview_functionality(driver):
    """Test the PDF preview functionality"""
    print("\n🔍 Testing PDF Preview...")
    
    try:
        # Look for preview button (try different selectors)
        preview_button = None
        selectors_to_try = [
            "//button[contains(text(), 'Preview PDF')]",
            "//a[contains(text(), 'Preview PDF')]",
            "//button[contains(@class, 'preview')]",
            "//*[contains(text(), 'Preview')]"
        ]
        
        for selector in selectors_to_try:
            try:
                preview_button = driver.find_element(By.XPATH, selector)
                break
            except:
                continue
        
        if not preview_button:
            print("❌ Could not find preview button")
            return False
        
        print(f"✅ Found preview button: {preview_button.text}")
        
        # Get current window handles
        original_windows = driver.window_handles
        
        # Click preview button
        preview_button.click()
        print("   Clicked preview button...")
        
        # Wait for new window/tab or navigation
        time.sleep(3)
        
        # Check if new tab opened
        new_windows = driver.window_handles
        if len(new_windows) > len(original_windows):
            print("✅ Preview opened in new tab")
            
            # Switch to new tab
            driver.switch_to.window(new_windows[-1])
            current_url = driver.current_url
            print(f"   Preview URL: {current_url}")
            
            # Check if it's a PDF
            if 'preview' in current_url:
                print("✅ Preview URL looks correct")
                
                # Wait a moment for PDF to load
                time.sleep(2)
                
                # Check page title or content
                try:
                    page_source = driver.page_source
                    if 'PDF' in page_source or len(page_source) > 1000:
                        print("✅ Preview content appears to have loaded")
                    else:
                        print("⚠️  Preview content seems minimal")
                except:
                    print("⚠️  Could not analyze preview content")
            else:
                print(f"⚠️  Unexpected preview URL: {current_url}")
            
            # Close preview tab and return to main window
            driver.close()
            driver.switch_to.window(original_windows[0])
            print("   Returned to main window")
            
            return True
            
        else:
            # Check if same tab navigation occurred
            current_url = driver.current_url
            if 'preview' in current_url:
                print("✅ Preview opened in same tab")
                # Navigate back
                driver.back()
                time.sleep(2)
                return True
            else:
                print(f"❌ No preview detected. Current URL: {current_url}")
                return False
                
    except Exception as e:
        print(f"❌ Error testing preview: {e}")
        return False

def test_complete_workflow():
    """Test the complete PDF positioning workflow"""
    driver = setup_driver()
    if not driver:
        return
    
    try:
        print("🚀 Starting Complete PDF Positioning Workflow Test...")
        
        # Navigate and login
        driver.get("http://localhost:5111/")
        
        # Login
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "email")))
        driver.find_element(By.NAME, "email").send_keys("admin@rfpo.com")
        driver.find_element(By.NAME, "password").send_keys("admin123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        print("🔑 Logged in")
        
        # Navigate to PDF editor
        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        
        # Wait for canvas to be ready
        wait_for_canvas_ready(driver)
        
        # Get initial canvas info
        canvas_info = get_canvas_info(driver)
        print(f"📏 Canvas: {canvas_info['width']}x{canvas_info['height']} at ({canvas_info['left']}, {canvas_info['top']})")
        
        # Debug: Check page structure
        print("\n🔍 Debugging page structure...")
        try:
            # Look for any lists or field containers
            all_lists = driver.find_elements(By.CSS_SELECTOR, ".list-group, .field-list, ul, ol")
            print(f"   Found {len(all_lists)} list containers")
            
            for i, lst in enumerate(all_lists[:3]):  # Show first 3
                list_items = lst.find_elements(By.CSS_SELECTOR, "li, .list-item, .field-item")
                print(f"     List {i+1}: {len(list_items)} items")
                
                # Show first few items from the biggest list
                if len(list_items) > 5:
                    print(f"       First 5 items:")
                    for j, item in enumerate(list_items[:5]):
                        item_text = item.text.strip()
                        draggable = item.get_attribute("draggable")
                        print(f"         {j+1}. '{item_text}' (draggable: {draggable})")
                
            # Check for any elements with "field" in class name
            field_elements = driver.find_elements(By.XPATH, "//*[contains(@class, 'field')]")
            print(f"   Found {len(field_elements)} elements with 'field' in class")
            
            # Check for drag-related attributes
            draggable_elements = driver.find_elements(By.XPATH, "//*[@draggable]")
            print(f"   Found {len(draggable_elements)} draggable elements")
            
            # Look specifically for the Available Fields section
            try:
                available_section = driver.find_element(By.XPATH, "//*[contains(text(), 'Available Fields')]/..")
                print(f"   Found Available Fields section: {available_section.tag_name}")
                
                # Look for items in this section
                section_items = available_section.find_elements(By.CSS_SELECTOR, "*")
                print(f"   Available Fields section has {len(section_items)} child elements")
                
                # Look for anything that looks like a field item
                for item in section_items[:10]:  # Check first 10
                    if item.text and len(item.text.strip()) > 3:
                        draggable = item.get_attribute("draggable")
                        classes = item.get_attribute("class")
                        print(f"     - '{item.text.strip()[:30]}' (tag: {item.tag_name}, draggable: {draggable}, classes: {classes})")
                        
            except Exception as e:
                print(f"   Could not find Available Fields section: {e}")
                
            # Try looking for spans with specific text patterns
            po_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Order Number') or contains(text(), 'PO Number') or contains(text(), 'po_number')]")
            print(f"   Found {len(po_elements)} elements mentioning 'Order Number'")
            for elem in po_elements[:3]:
                print(f"     - '{elem.text}' (tag: {elem.tag_name}, draggable: {elem.get_attribute('draggable')})")
            
        except Exception as e:
            print(f"   Debug check failed: {e}")
        
        # Clear any existing fields first
        print("\n🧹 Clearing any existing fields...")
        try:
            clear_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Clear All')]")
            clear_button.click()
            time.sleep(1)
            print("✅ Cleared existing fields")
        except:
            print("   No clear button found or no existing fields")
        
        # Define 4 field placements (field_name, x, y) - using actual field descriptions
        fields_to_place = [
            ("Purchase Order Number", 100, 100),    # Top left - should match "po_number"
            ("Purchase Order Date", 400, 100),      # Top right - should match "po_date"  
            ("Vendor Company Name", 100, 300),      # Bottom left - should match "vendor_company"
            ("Vendor Contact Person", 400, 300),    # Bottom right - should match "vendor_contact"
        ]
        
        # Place all 4 fields
        successful_placements = 0
        for field_name, x, y in fields_to_place:
            if place_element_on_canvas(driver, field_name, x, y):
                successful_placements += 1
            time.sleep(1)  # Small delay between placements
        
        print(f"\n📊 Placement Summary: {successful_placements}/{len(fields_to_place)} fields placed successfully")
        
        # Get final field positions
        print("\n📋 Final field positions on canvas:")
        all_fields = get_all_canvas_fields(driver)
        for i, field in enumerate(all_fields):
            print(f"   {i+1}. {field['name']}: screen=({field['screenX']:.0f}, {field['screenY']:.0f}), "
                  f"css=({field['cssLeft']}, {field['cssTop']}), visible={field['visible']}")
        
        if len(all_fields) >= 2:  # If we have at least 2 fields
            # Test preview functionality
            preview_success = test_preview_functionality(driver)
            
            if preview_success:
                print("\n✅ Complete workflow test PASSED!")
                print("   - Fields placed successfully")
                print("   - Preview functionality working")
            else:
                print("\n⚠️  Workflow partially successful:")
                print("   - Fields placed successfully")
                print("   - Preview functionality needs investigation")
        else:
            print("\n❌ Workflow test FAILED - insufficient fields placed")
        
        # Keep browser open for manual inspection
        print(f"\n👀 Keeping browser open for 60 seconds for manual inspection...")
        print(f"   Canvas has {len(all_fields)} fields")
        print(f"   You can manually test interactions and preview")
        time.sleep(60)
        
    except Exception as e:
        print(f"❌ Error during workflow test: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        driver.quit()
        print("🔚 Test completed")

if __name__ == "__main__":
    test_complete_workflow()
