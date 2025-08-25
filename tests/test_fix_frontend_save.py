#!/usr/bin/env python3
"""
Fix the frontend save issue in the positioning editor
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.alert import Alert
from selenium.common.exceptions import TimeoutException

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

def test_fix_frontend_save():
    """Test and fix the frontend save issue"""
    driver = setup_driver()
    if not driver:
        return False
    
    try:
        print("🔧 FIXING FRONTEND SAVE ISSUE")
        print("=" * 50)
        
        # Login and navigate
        driver.get("http://localhost:5111/")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "email")))
        driver.find_element(By.NAME, "email").send_keys("admin@rfpo.com")
        driver.find_element(By.NAME, "password").send_keys("admin123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "pdf-canvas")))
        time.sleep(3)
        
        print("✅ Editor loaded")
        
        # Clear everything
        clear_btn = driver.find_element(By.ID, "clear-canvas")
        clear_btn.click()
        
        try:
            WebDriverWait(driver, 3).until(EC.alert_is_present())
            alert = Alert(driver)
            alert.accept()
            time.sleep(2)
        except TimeoutException:
            pass
        
        print("✅ Canvas cleared")
        
        # Create test field manually
        print("\n📋 Creating test field...")
        driver.execute_script("""
            const canvas = document.getElementById('pdf-canvas');
            const field = document.createElement('div');
            field.className = 'pdf-field';
            field.dataset.fieldName = 'frontend_test';
            field.textContent = 'FRONTEND TEST';
            field.style.position = 'absolute';
            field.style.left = '400px';
            field.style.top = '150px';
            field.style.padding = '8px 16px';
            field.style.fontSize = '14px';
            field.style.fontFamily = 'Arial, sans-serif';
            field.style.backgroundColor = 'rgba(0, 255, 0, 0.9)';
            field.style.border = '3px solid purple';
            field.style.borderRadius = '4px';
            field.style.zIndex = '1000';
            field.style.fontWeight = 'bold';
            
            canvas.appendChild(field);
            
            // Set positioning data
            window.POSITIONING_DATA = {
                'frontend_test': {
                    x: 400,
                    y: 150,
                    font_size: 14,
                    font_weight: 'bold',
                    visible: true
                }
            };
            
            console.log('Created frontend test field');
        """)
        
        time.sleep(2)
        
        # Verify field in DOM
        created_fields = driver.find_elements(By.CSS_SELECTOR, "#pdf-canvas .pdf-field")
        positioning_data = driver.execute_script("return window.POSITIONING_DATA;")
        
        print(f"   Fields in DOM: {len(created_fields)}")
        print(f"   Positioning data: {positioning_data}")
        
        if len(created_fields) == 1 and 'frontend_test' in positioning_data:
            print("   ✅ Field created successfully")
        else:
            print("   ❌ Field creation failed")
            return False
        
        # Test save functionality with debug
        print("\n💾 Testing save functionality...")
        
        # Check if save function exists and works
        save_result = driver.execute_script("""
            console.log('Testing save functionality...');
            console.log('CONFIG_ID:', window.CONFIG_ID);
            console.log('POSITIONING_DATA:', window.POSITIONING_DATA);
            
            // Test fetch manually
            return fetch(`/api/pdf-positioning/${window.CONFIG_ID}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    positioning_data: window.POSITIONING_DATA
                })
            })
            .then(response => response.json())
            .then(data => {
                console.log('Save response:', data);
                return data;
            })
            .catch(error => {
                console.error('Save error:', error);
                return {success: false, error: error.toString()};
            });
        """)
        
        time.sleep(3)  # Wait for promise to resolve
        
        # Get the actual result
        save_response = driver.execute_script("return window.lastSaveResponse || null;")
        print(f"   Save response: {save_response}")
        
        # Alternative: Click the save button and check network
        print("\n🔘 Testing save button click...")
        save_btn = driver.find_element(By.ID, "save-config")
        save_btn.click()
        time.sleep(3)
        
        # Check if save succeeded by checking server
        print("\n🔍 Verifying save on server...")
        verify_result = driver.execute_script("""
            return fetch(`/api/pdf-positioning/${window.CONFIG_ID}`)
                .then(response => response.json())
                .then(data => {
                    console.log('Verification response:', data);
                    const hasTestField = data.positioning_data && 'frontend_test' in data.positioning_data;
                    return {
                        success: true,
                        hasTestField: hasTestField,
                        fieldData: hasTestField ? data.positioning_data['frontend_test'] : null
                    };
                })
                .catch(error => ({success: false, error: error.toString()}));
        """)
        
        time.sleep(2)
        
        # Check verification result
        verification = driver.execute_script("return window.lastVerification || null;")
        print(f"   Verification: {verification}")
        
        # Manual verification - make API call
        import requests
        session = requests.Session()
        login_data = {'email': 'admin@rfpo.com', 'password': 'admin123'}
        session.post('http://localhost:5111/login', data=login_data)
        
        get_response = session.get('http://localhost:5111/api/pdf-positioning/1')
        if get_response.status_code == 200:
            server_data = get_response.json()
            positioning_data = server_data.get('positioning_data', {})
            
            if 'frontend_test' in positioning_data:
                field_data = positioning_data['frontend_test']
                print(f"   ✅ Field saved to server: x={field_data['x']}, y={field_data['y']}, visible={field_data['visible']}")
                
                # Now test preview
                print(f"\n📄 Testing preview with saved field...")
                original_windows = driver.window_handles
                preview_btn = driver.find_element(By.ID, "preview-pdf")
                preview_btn.click()
                time.sleep(8)
                
                if len(driver.window_handles) > len(original_windows):
                    driver.switch_to.window(driver.window_handles[-1])
                    
                    # Check for content
                    try:
                        page_text = driver.execute_script("return document.body.innerText || '';")
                        if "FRONTEND TEST" in page_text or any(x in page_text for x in ["frontend_test", "FRONTEND", "TEST"]):
                            print(f"   ✅ SUCCESS: Field content found in PDF!")
                            preview_success = True
                        else:
                            print(f"   ⚠️  Field content not found in PDF")
                            print(f"   PDF preview content: {page_text[:200]}...")
                            preview_success = False
                    except Exception as e:
                        print(f"   ❌ Error checking PDF: {e}")
                        preview_success = False
                    
                    time.sleep(5)
                    driver.close()
                    driver.switch_to.window(original_windows[0])
                    
                    return preview_success
                else:
                    print(f"   ❌ Preview failed to open")
                    return False
            else:
                print(f"   ❌ Field NOT saved to server")
                print(f"   Available fields: {list(positioning_data.keys())}")
                return False
        else:
            print(f"   ❌ Server verification failed: {get_response.status_code}")
            return False
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    success = test_fix_frontend_save()
    if success:
        print(f"\n🎉 FRONTEND SAVE AND PREVIEW: WORKING")
    else:
        print(f"\n💥 FRONTEND SAVE OR PREVIEW: STILL BROKEN")
