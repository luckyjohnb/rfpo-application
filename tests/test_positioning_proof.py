#!/usr/bin/env python3
"""
POSITIONING PROOF TEST
Generate visual proof of positioning issue without complex interactions
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

def positioning_proof_test():
    print("🔍 POSITIONING PROOF TEST")
    print("="*70)
    print("Goal: Generate visual proof of designer vs preview positioning")
    print()
    
    driver = setup_driver()
    session = requests.Session()
    
    try:
        # Step 1: Login
        print("📋 Step 1: Login...")
        driver.get("http://localhost:5111/login")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "email")))
        
        driver.find_element(By.NAME, "email").send_keys("admin@rfpo.com")
        driver.find_element(By.NAME, "password").send_keys("admin123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)
        
        # Login with requests too
        login_data = {'email': 'admin@rfpo.com', 'password': 'admin123'}
        session.post('http://localhost:5111/login', data=login_data)
        print("   ✅ Logged in")
        
        # Step 2: Navigate to designer and clear
        print("📋 Step 2: Navigate to designer...")
        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "pdf-canvas")))
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
        
        # Step 3: Place element using JavaScript (avoid UI interaction issues)
        print("📋 Step 3: Place element at top-right corner...")
        
        place_and_analyze_script = """
        // Clear any existing data first
        Object.keys(POSITIONING_DATA).forEach(key => delete POSITIONING_DATA[key]);
        
        // Place element at top-right corner of canvas
        const fieldName = 'po_number';
        
        // Target position: top-right area
        const targetScreenX = 450;  // 450px from left edge of canvas
        const targetScreenY = 50;   // 50px from top edge of canvas
        
        // Convert to PDF coordinates using the conversion logic
        const pdfX = targetScreenX;
        const pdfY = 792 - targetScreenY;  // Convert Y: screen to PDF
        
        console.log('=== ELEMENT PLACEMENT ===');
        console.log('Target screen position:', targetScreenX, targetScreenY);
        console.log('Calculated PDF position:', pdfX, pdfY);
        
        // Create positioning data
        POSITIONING_DATA[fieldName] = {
            x: pdfX,
            y: pdfY,
            font_size: 14,
            font_weight: 'bold',
            visible: true
        };
        
        // Create the visual element
        const canvas = document.getElementById('pdf-canvas');
        const fieldElement = document.createElement('div');
        fieldElement.className = 'pdf-field';
        fieldElement.dataset.fieldName = fieldName;
        fieldElement.textContent = 'PO NUMBER';
        fieldElement.style.position = 'absolute';
        fieldElement.style.left = targetScreenX + 'px';  // Screen position for display
        fieldElement.style.top = targetScreenY + 'px';   // Screen position for display
        fieldElement.style.fontSize = '14px';
        fieldElement.style.fontWeight = 'bold';
        fieldElement.style.backgroundColor = 'rgba(255, 255, 0, 0.7)';
        fieldElement.style.border = '2px solid red';
        fieldElement.style.padding = '4px';
        fieldElement.style.zIndex = '1000';
        
        canvas.appendChild(fieldElement);
        
        // Save configuration
        saveConfiguration();
        
        // Return analysis data
        return {
            fieldName: fieldName,
            targetScreenX: targetScreenX,
            targetScreenY: targetScreenY,
            calculatedPdfX: pdfX,
            calculatedPdfY: pdfY,
            positioningData: POSITIONING_DATA[fieldName]
        };
        """
        
        result = driver.execute_script(place_and_analyze_script)
        print(f"   ✅ Placed {result['fieldName']}")
        print(f"   Target screen position: ({result['targetScreenX']}, {result['targetScreenY']})")
        print(f"   Calculated PDF position: ({result['calculatedPdfX']}, {result['calculatedPdfY']})")
        time.sleep(3)
        
        # Step 4: Check UI coordinate display via JavaScript
        print("📋 Step 4: Check UI coordinate display...")
        
        ui_check_script = """
        // Select the field
        const field = document.querySelector('.pdf-field');
        if (field) {
            selectField(field);
            
            // Get displayed coordinates
            const coordinatesText = document.getElementById('coordinates').textContent;
            const fieldXValue = document.getElementById('field-x').value;
            const fieldYValue = document.getElementById('field-y').value;
            
            return {
                coordinatesDisplay: coordinatesText,
                fieldXInput: fieldXValue,
                fieldYInput: fieldYValue,
                fieldVisible: field.style.display !== 'none'
            };
        }
        return { error: 'Field not found' };
        """
        
        ui_result = driver.execute_script(ui_check_script)
        if 'error' not in ui_result:
            print(f"   Coordinates display: {ui_result['coordinatesDisplay']}")
            print(f"   Field X input: {ui_result['fieldXInput']}")
            print(f"   Field Y input: {ui_result['fieldYInput']}")
            
            # Analyze if the Y value makes sense
            expected_y = result['calculatedPdfY']  # Should be around 742
            actual_y = float(ui_result['fieldYInput'])
            
            print(f"   Expected Y in UI: {expected_y}")
            print(f"   Actual Y in UI: {actual_y}")
            
            if actual_y > 700:  # High Y value when element is at top
                print("   ❌ CONFIRMED BUG: High Y value when element is at top!")
                ui_bug_confirmed = True
            else:
                print("   ✅ Y value seems reasonable")
                ui_bug_confirmed = False
        else:
            print(f"   ❌ {ui_result['error']}")
            ui_bug_confirmed = False
        
        # Step 5: Take screenshot of designer
        print("📋 Step 5: Screenshot designer...")
        driver.save_screenshot("PROOF_DESIGNER_POSITIONED.png")
        print("   📸 Designer screenshot: PROOF_DESIGNER_POSITIONED.png")
        
        # Step 6: Check API data
        print("📋 Step 6: Verify API data...")
        api_response = session.get("http://localhost:5111/api/pdf-positioning/1")
        
        if api_response.status_code == 200:
            data = api_response.json()
            api_field_data = data['positioning_data'].get('po_number', {})
            api_x = api_field_data.get('x', 0)
            api_y = api_field_data.get('y', 0)
            print(f"   API stored position: x={api_x}, y={api_y}")
            
            # Check if API data matches what we intended
            if abs(api_x - result['calculatedPdfX']) < 5 and abs(api_y - result['calculatedPdfY']) < 5:
                print("   ✅ API data matches calculated position")
                api_correct = True
            else:
                print("   ❌ API data doesn't match calculated position!")
                api_correct = False
        else:
            print("   ❌ Failed to get API data")
            api_correct = False
        
        # Step 7: Generate preview
        print("📋 Step 7: Generate and check preview...")
        
        # Generate PDF via API
        pdf_response = session.get("http://localhost:5111/api/pdf-positioning/preview/1")
        
        if pdf_response.status_code == 200:
            print(f"   ✅ PDF generated: {len(pdf_response.content)} bytes")
            
            with open("PROOF_PREVIEW.pdf", "wb") as f:
                f.write(pdf_response.content)
            print("   📄 PDF saved: PROOF_PREVIEW.pdf")
            
            # Check if field content appears in PDF
            pdf_text = pdf_response.content.decode('latin-1', errors='ignore')
            if 'PO NUMBER' in pdf_text.upper():
                print("   ✅ PO NUMBER found in PDF")
                pdf_has_field = True
            else:
                print("   ❌ PO NUMBER not found in PDF")
                pdf_has_field = False
        else:
            print(f"   ❌ PDF generation failed: {pdf_response.status_code}")
            pdf_has_field = False
        
        # Step 8: Open preview in browser for visual verification
        print("📋 Step 8: Open preview in browser...")
        
        try:
            original_window = driver.current_window_handle
            preview_button = driver.find_element(By.ID, "preview-pdf")
            preview_button.click()
            time.sleep(5)
            
            # Find preview window
            preview_window = None
            for window in driver.window_handles:
                if window != original_window:
                    preview_window = window
                    break
            
            if preview_window:
                driver.switch_to.window(preview_window)
                time.sleep(4)
                
                # Take screenshot of preview
                driver.save_screenshot("PROOF_PREVIEW_BROWSER.png")
                print("   📸 Browser preview: PROOF_PREVIEW_BROWSER.png")
                
                # Switch back
                driver.switch_to.window(original_window)
            else:
                print("   ⚠️ Preview window didn't open")
        except Exception as e:
            print(f"   ⚠️ Preview browser capture failed: {e}")
        
        # Step 9: Final analysis
        print("\n" + "="*70)
        print("🔍 POSITIONING ANALYSIS RESULTS")
        print("="*70)
        
        print("ELEMENT PLACEMENT:")
        print(f"  Field: {result['fieldName']}")
        print(f"  Intended position: top-right corner")
        print(f"  Screen coordinates: ({result['targetScreenX']}, {result['targetScreenY']})")
        print(f"  PDF coordinates: ({result['calculatedPdfX']}, {result['calculatedPdfY']})")
        print()
        
        print("ISSUES DETECTED:")
        issues = []
        
        if ui_bug_confirmed:
            issues.append("UI displays high Y value when element is at top")
            print(f"  ❌ UI Y display: {ui_result['fieldYInput']} (should be lower for top position)")
        
        if not api_correct:
            issues.append("API storage doesn't match calculated position")
            print(f"  ❌ API position mismatch")
        
        if not pdf_has_field:
            issues.append("PDF doesn't contain field")
            print(f"  ❌ Field missing from PDF")
        
        if len(issues) == 0:
            print("  ✅ No issues detected")
        
        print("\n📸 VISUAL PROOF FILES:")
        print("  1. PROOF_DESIGNER_POSITIONED.png - Designer with element at top-right")
        print("  2. PROOF_PREVIEW.pdf - Generated PDF")
        print("  3. PROOF_PREVIEW_BROWSER.png - Browser preview")
        print()
        print("👀 MANUAL VERIFICATION NEEDED:")
        print("  • Check if element appears in same relative position in designer vs preview")
        print("  • Verify element is actually in top-right corner in both views")
        
        return len(issues) == 0
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
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
    success = positioning_proof_test()
    
    print(f"\n" + "="*70)
    print("🏆 POSITIONING PROOF TEST RESULTS")
    print("="*70)
    
    if success:
        print("✅ No issues detected in automated checks")
        print("   Manual verification of proof files still needed")
    else:
        print("❌ Issues detected - positioning needs fixing")
    
    print("\n🔍 NEXT STEPS:")
    print("1. Examine proof images side-by-side")
    print("2. Verify element appears in same relative position")
    print("3. Check if UI coordinate display makes sense")
    print("="*70)
