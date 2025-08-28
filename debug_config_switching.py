#!/usr/bin/env python3
"""
DEBUG CONFIGURATION SWITCHING
Check if configurations are being loaded correctly for different consortiums
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

def debug_config_switching():
    print("🔄 DEBUGGING CONFIGURATION SWITCHING")
    print("=" * 60)
    
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1400,900")
    
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)
    
    try:
        print("📋 Login...")
        driver.get("http://localhost:5111/login")
        time.sleep(2)
        
        # Login
        email_field = driver.find_element(By.NAME, "email")
        password_field = driver.find_element(By.NAME, "password")
        email_field.send_keys("admin@rfpo.com")
        password_field.send_keys("admin123")
        
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        login_button.click()
        time.sleep(3)
        
        # Test different consortiums
        test_configs = [
            ("00000014", "USCAR"),
            ("00000009", "Materials TLC"),  
            ("00000013", "USAMP"),
        ]
        
        for consortium_id, name in test_configs:
            print(f"\n🔍 Testing {name} ({consortium_id})...")
            
            # Navigate to specific consortium editor
            url = f"http://localhost:5111/pdf-positioning/editor/{consortium_id}/po_template"
            driver.get(url)
            
            # Wait for canvas to load
            try:
                canvas = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "pdf-canvas"))
                )
                time.sleep(2)  # Extra wait for JavaScript to initialize
            except:
                print(f"  ❌ Canvas failed to load for {name}")
                continue
            
            # Get configuration data from JavaScript with better error handling
            config_data = driver.execute_script("""
                try {
                    return {
                        CONFIG_ID: typeof CONFIG_ID !== 'undefined' ? CONFIG_ID : null,
                        POSITIONING_DATA: typeof POSITIONING_DATA !== 'undefined' ? POSITIONING_DATA : null,
                        url: window.location.href,
                        ready: typeof CONFIG_ID !== 'undefined' && typeof POSITIONING_DATA !== 'undefined'
                    };
                } catch (e) {
                    return {
                        CONFIG_ID: null,
                        POSITIONING_DATA: null,
                        url: window.location.href,
                        error: e.toString(),
                        ready: false
                    };
                }
            """)
            
            print(f"  URL: {config_data['url']}")
            print(f"  CONFIG_ID: {config_data['CONFIG_ID']}")
            print(f"  POSITIONING_DATA: {config_data['POSITIONING_DATA']}")
            
            # Check if po_number field exists and its coordinates
            if config_data['POSITIONING_DATA'] and 'po_number' in config_data['POSITIONING_DATA']:
                po_data = config_data['POSITIONING_DATA']['po_number']
                print(f"  PO Number position: ({po_data.get('x')}, {po_data.get('y')})")
            else:
                print("  No PO Number field found")
        
        print("\n🎯 ANALYSIS:")
        print("Each consortium should have a different CONFIG_ID and positioning data.")
        print("If they're the same, there's a configuration switching issue.")
        
        return True
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        driver.quit()

if __name__ == "__main__":
    debug_config_switching()
