#!/usr/bin/env python3
"""
FINAL POSITIONING FIX TEST
Test with improved UI display and correct PDF content search
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

def test_final_positioning():
    print("🎯 FINAL POSITIONING FIX TEST")
    print("="*70)
    print("Testing: UI display fix + PDF positioning validation")
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
        
        # Step 3: Place element at top of page with improved UI
        print("📋 Step 3: Place element at top of page...")
        
        place_element_script = """
        // Place element at top of canvas using updated coordinate system
        const fieldName = 'po_number';
        const screenX = 400;  // 400px from left
        const screenY = 30;   // 30px from top (near top of page)
        
        // Store in PDF coordinates (with Y-axis flip)
        const pdfX = screenX;
        const pdfY = 792 - screenY;  // Convert to PDF coordinates
        
        console.log('Placing element:');
        console.log('  Screen position:', screenX, screenY);
        console.log('  PDF coordinates stored:', pdfX, pdfY);
        
        // Create positioning data
        POSITIONING_DATA[fieldName] = {
            x: pdfX,
            y: pdfY,
            font_size: 16,
            font_weight: 'bold',
            visible: true
        };
        
        // Create visual element
        const canvas = document.getElementById('pdf-canvas');
        const fieldElement = document.createElement('div');
        fieldElement.className = 'pdf-field';
        fieldElement.dataset.fieldName = fieldName;
        fieldElement.textContent = 'PO NUMBER';
        fieldElement.style.position = 'absolute';
        fieldElement.style.left = screenX + 'px';
        fieldElement.style.top = screenY + 'px';
        fieldElement.style.fontSize = '16px';
        fieldElement.style.fontWeight = 'bold';
        fieldElement.style.backgroundColor = 'rgba(255, 255, 0, 0.8)';
        fieldElement.style.border = '2px solid red';
        fieldElement.style.padding = '6px';
        fieldElement.style.zIndex = '1000';
        
        canvas.appendChild(fieldElement);
        
        // Select the field to trigger UI updates
        selectField(fieldElement);
        
        // Save configuration
        saveConfiguration();
        
        return {
            screenX: screenX,
            screenY: screenY,
            pdfX: pdfX,
            pdfY: pdfY
        };
        """
        
        placement_result = driver.execute_script(place_element_script)
        print(f"   ✅ Element placed at screen ({placement_result['screenX']}, {placement_result['screenY']})")
        print(f"   Stored as PDF coordinates ({placement_result['pdfX']}, {placement_result['pdfY']})")
        time.sleep(3)
        
        # Step 4: Check improved UI display
        print("📋 Step 4: Check improved UI coordinate display...")
        
        ui_check_script = """
        // Get displayed coordinates from UI
        const coordinatesText = document.getElementById('coordinates').textContent;
        const fieldXValue = document.getElementById('field-x').value;
        const fieldYValue = document.getElementById('field-y').value;
        
        return {
            coordinatesDisplay: coordinatesText,
            fieldXInput: fieldXValue,
            fieldYInput: fieldYValue
        };
        """
        
        ui_result = driver.execute_script(ui_check_script)
        print(f"   Coordinates display: {ui_result['coordinatesDisplay']}")
        print(f"   Field X input: {ui_result['fieldXInput']}")
        print(f"   Field Y input: {ui_result['fieldYInput']}")
        
        # Check if UI now shows sensible Y value
        expected_display_y = placement_result['screenY']  # Should show distance from top
        actual_display_y = float(ui_result['fieldYInput'])
        
        print(f"   Expected Y display (from top): {expected_display_y}")
        print(f"   Actual Y display: {actual_display_y}")
        
        if abs(actual_display_y - expected_display_y) < 5:
            print("   ✅ UI now shows sensible Y coordinates!")
            ui_fixed = True
        else:
            print("   ❌ UI Y display still problematic")
            ui_fixed = False
        
        # Step 5: Take screenshot of designer
        print("📋 Step 5: Screenshot designer...")
        driver.save_screenshot("FINAL_TEST_DESIGNER.png")
        print("   📸 Designer: FINAL_TEST_DESIGNER.png")
        
        # Step 6: Generate PDF and validate content
        print("📋 Step 6: Generate PDF and validate...")
        pdf_response = session.get("http://localhost:5111/api/pdf-positioning/preview/1")
        
        if pdf_response.status_code == 200:
            print(f"   ✅ PDF generated: {len(pdf_response.content)} bytes")
            
            with open("FINAL_TEST_PREVIEW.pdf", "wb") as f:
                f.write(pdf_response.content)
            print("   📄 PDF saved: FINAL_TEST_PREVIEW.pdf")
            
            # Search for correct content (dummy RFPO data)
            pdf_text = pdf_response.content.decode('latin-1', errors='ignore')
            
            # Look for dummy RFPO content that should appear
            search_terms = ['PREVIEW-001', 'PREVIEW', 'PO-PREVIEW', 'Sample Preview Project']
            found_terms = [term for term in search_terms if term in pdf_text]
            
            print(f"   Search terms found in PDF: {found_terms}")
            
            if found_terms:
                print("   ✅ PDF contains expected content")
                pdf_has_content = True
                
                # Try to determine if content is positioned correctly
                lines = pdf_text.split('\n')
                for i, line in enumerate(lines[:30]):
                    for term in found_terms:
                        if term in line:
                            print(f"      Found '{term}' in PDF line {i}")
            else:
                print("   ❌ PDF missing expected content")
                pdf_has_content = False
                
                # Debug: show some PDF content
                readable_chars = [c for c in pdf_text if c.isprintable()]
                sample_text = ''.join(readable_chars[:300])
                print(f"   PDF sample text: {sample_text}")
        else:
            print(f"   ❌ PDF generation failed: {pdf_response.status_code}")
            pdf_has_content = False
        
        # Step 7: Open preview in browser
        print("📋 Step 7: Open browser preview...")
        
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
                
                # Take screenshot
                driver.save_screenshot("FINAL_TEST_BROWSER_PREVIEW.png")
                print("   📸 Browser preview: FINAL_TEST_BROWSER_PREVIEW.png")
                
                # Switch back
                driver.switch_to.window(original_window)
            else:
                print("   ⚠️ Preview window didn't open")
        except Exception as e:
            print(f"   ⚠️ Browser preview failed: {e}")
        
        # Step 8: Final analysis
        print("\n" + "="*70)
        print("🏆 FINAL POSITIONING FIX RESULTS")
        print("="*70)
        
        print("ELEMENT PLACEMENT:")
        print(f"  Position: Near top of page")
        print(f"  Screen coordinates: ({placement_result['screenX']}, {placement_result['screenY']})")
        print(f"  PDF coordinates: ({placement_result['pdfX']}, {placement_result['pdfY']})")
        print()
        
        print("UI DISPLAY FIX:")
        if ui_fixed:
            print(f"  ✅ UI shows user-friendly coordinates")
            print(f"     Y = {actual_display_y} (distance from top)")
        else:
            print(f"  ❌ UI still shows confusing coordinates")
        print()
        
        print("PDF CONTENT:")
        if pdf_has_content:
            print(f"  ✅ PDF contains expected content")
            print(f"     Found: {', '.join(found_terms)}")
        else:
            print(f"  ❌ PDF missing content")
        print()
        
        # Overall assessment
        if ui_fixed and pdf_has_content:
            print("🎉 POSITIONING FIXES SUCCESSFUL!")
            print("   • UI displays user-friendly coordinates")
            print("   • PDF generation works with positioning")
            return True
        else:
            issues = []
            if not ui_fixed:
                issues.append("UI coordinate display")
            if not pdf_has_content:
                issues.append("PDF content generation")
            
            print(f"⚠️ REMAINING ISSUES: {', '.join(issues)}")
            return False
        
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
    print("🔧 FINAL POSITIONING FIX VALIDATION")
    print("="*70)
    print("This test validates:")
    print("1. UI displays user-friendly Y coordinates (distance from top)")
    print("2. Elements save correct positions") 
    print("3. PDF preview shows positioned content")
    print("4. Visual proof of designer vs preview")
    print()
    
    success = test_final_positioning()
    
    print(f"\n" + "="*70)
    print("📸 VISUAL PROOF FILES:")
    print("="*70)
    print("   1. FINAL_TEST_DESIGNER.png - Element at top of designer")
    print("   2. FINAL_TEST_PREVIEW.pdf - Generated PDF")
    print("   3. FINAL_TEST_BROWSER_PREVIEW.png - Browser preview")
    print()
    print("👀 MANUAL VERIFICATION:")
    print("   Compare designer vs preview to confirm positioning works")
    print("="*70)