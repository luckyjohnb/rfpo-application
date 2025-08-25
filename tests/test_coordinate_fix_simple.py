#!/usr/bin/env python3
"""
SIMPLE COORDINATE FIX TEST
Test the createFieldElement coordinate conversion fix
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

def test_coordinate_fix():
    print("🔧 COORDINATE FIX TEST")
    print("="*60)
    print("Testing createFieldElement coordinate conversion fix")
    print()
    
    driver = setup_driver()
    session = requests.Session()
    
    try:
        # Login
        print("📋 Login...")
        driver.get("http://localhost:5111/login")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "email")))
        
        driver.find_element(By.NAME, "email").send_keys("admin@rfpo.com")
        driver.find_element(By.NAME, "password").send_keys("admin123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)
        
        login_data = {'email': 'admin@rfpo.com', 'password': 'admin123'}
        session.post('http://localhost:5111/login', data=login_data)
        print("   ✅ Logged in")
        
        # Navigate to designer
        print("📋 Navigate to designer...")
        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "pdf-canvas")))
        time.sleep(5)
        print("   ✅ Designer loaded")
        
        # Test coordinate conversion
        print("📋 Test coordinate conversion...")
        
        test_script = """
        // Clear any existing data
        Object.keys(POSITIONING_DATA).forEach(key => delete POSITIONING_DATA[key]);
        document.querySelectorAll('.pdf-field').forEach(el => el.remove());
        
        // Test data: element that should appear at top of screen
        const fieldName = 'po_number';
        const testPdfX = 300;   // 300px from left (PDF coordinates)
        const testPdfY = 700;   // 700 from bottom = 92 from top (PDF coordinates)
        
        console.log('=== TESTING COORDINATE CONVERSION ===');
        console.log('Test PDF coordinates:', testPdfX, testPdfY);
        console.log('Expected screen coordinates:', testPdfX, 792 - testPdfY);
        
        // Create positioning data (as if loaded from database)
        POSITIONING_DATA[fieldName] = {
            x: testPdfX,
            y: testPdfY,
            font_size: 14,
            font_weight: 'bold',
            visible: true
        };
        
        // Create field element (this should now convert coordinates correctly)
        const fieldElement = createFieldElement(fieldName, POSITIONING_DATA[fieldName]);
        
        // Get actual screen position
        const actualScreenX = parseInt(fieldElement.style.left);
        const actualScreenY = parseInt(fieldElement.style.top);
        
        console.log('Actual screen position:', actualScreenX, actualScreenY);
        console.log('Expected screen position:', testPdfX, 792 - testPdfY);
        
        // Select field to trigger UI updates
        selectField(fieldElement);
        
        return {
            testPdfX: testPdfX,
            testPdfY: testPdfY,
            expectedScreenX: testPdfX,
            expectedScreenY: 792 - testPdfY,
            actualScreenX: actualScreenX,
            actualScreenY: actualScreenY
        };
        """
        
        result = driver.execute_script(test_script)
        time.sleep(2)
        
        # Check results
        expected_x = result['expectedScreenX']
        expected_y = result['expectedScreenY']
        actual_x = result['actualScreenX']
        actual_y = result['actualScreenY']
        
        print(f"   Test PDF coordinates: ({result['testPdfX']}, {result['testPdfY']})")
        print(f"   Expected screen pos: ({expected_x}, {expected_y})")
        print(f"   Actual screen pos: ({actual_x}, {actual_y})")
        
        x_correct = abs(actual_x - expected_x) < 5
        y_correct = abs(actual_y - expected_y) < 5
        
        if x_correct and y_correct:
            print("   ✅ Coordinate conversion is working correctly!")
            conversion_fixed = True
        else:
            print("   ❌ Coordinate conversion still has issues")
            conversion_fixed = False
        
        # Check UI display
        ui_check_script = """
        return {
            coordinatesText: document.getElementById('coordinates').textContent,
            fieldYValue: document.getElementById('field-y').value
        };
        """
        
        ui_result = driver.execute_script(ui_check_script)
        print(f"   UI coordinates display: {ui_result['coordinatesText']}")
        print(f"   UI Y input: {ui_result['fieldYValue']}")
        
        # Take screenshot
        driver.save_screenshot("COORDINATE_FIX_TEST.png")
        print("   📸 Screenshot: COORDINATE_FIX_TEST.png")
        
        return conversion_fixed
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        driver.quit()

if __name__ == "__main__":
    # Start Flask app
    import subprocess
    import os
    
    # Kill any existing Flask process
    os.system("pkill -f 'python custom_admin.py' 2>/dev/null")
    time.sleep(2)
    
    # Start Flask app
    flask_process = subprocess.Popen(['python', 'custom_admin.py'], 
                                   stdout=subprocess.DEVNULL, 
                                   stderr=subprocess.DEVNULL)
    time.sleep(5)  # Wait for Flask to start
    
    try:
        success = test_coordinate_fix()
        
        print(f"\n" + "="*60)
        print("🏆 COORDINATE FIX TEST RESULTS")
        print("="*60)
        
        if success:
            print("🎉 COORDINATE CONVERSION FIX: SUCCESSFUL!")
            print("   Field elements now appear at correct screen positions")
            print("   Dragged elements should now show properly in preview")
        else:
            print("💥 COORDINATE CONVERSION FIX: INCOMPLETE")
            print("   Field positioning still has issues")
        
        print("="*60)
    finally:
        # Clean up Flask process
        flask_process.terminate()
        flask_process.wait()
