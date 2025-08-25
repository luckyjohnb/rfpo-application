#!/usr/bin/env python3
"""
DEBUG COORDINATE ISSUE
Print exactly what coordinates are being saved vs displayed
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

def debug_coordinates():
    print("🔍 DEBUGGING COORDINATE MISMATCH")
    print("=" * 50)
    
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1400,900")
    
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)
    
    try:
        print("📋 Login and navigate...")
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
        
        # Go to positioning editor
        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        time.sleep(5)
        
        canvas = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "pdf-canvas"))
        )
        
        print("✅ Page loaded")
        
        # Get canvas dimensions and position
        canvas_info = driver.execute_script("""
            const canvas = document.getElementById('pdf-canvas');
            const rect = canvas.getBoundingClientRect();
            return {
                rect: {
                    left: rect.left,
                    top: rect.top,
                    width: rect.width,
                    height: rect.height
                },
                style: {
                    width: canvas.style.width,
                    height: canvas.style.height
                },
                computed: {
                    width: window.getComputedStyle(canvas).width,
                    height: window.getComputedStyle(canvas).height
                }
            };
        """)
        
        print("📐 Canvas Information:")
        print(f"  Bounding Rect: {canvas_info['rect']}")
        print(f"  Style: {canvas_info['style']}")
        print(f"  Computed: {canvas_info['computed']}")
        
        # Check if there are any existing fields
        existing_fields = driver.execute_script("""
            const fields = document.querySelectorAll('.pdf-field');
            const results = [];
            fields.forEach(field => {
                const rect = field.getBoundingClientRect();
                const canvas = document.getElementById('pdf-canvas');
                const canvasRect = canvas.getBoundingClientRect();
                
                results.push({
                    name: field.dataset.fieldName,
                    style: {
                        left: field.style.left,
                        top: field.style.top
                    },
                    rect: {
                        left: rect.left,
                        top: rect.top,
                        width: rect.width,
                        height: rect.height
                    },
                    relativeToCanvas: {
                        left: rect.left - canvasRect.left,
                        top: rect.top - canvasRect.top
                    }
                });
            });
            return results;
        """)
        
        print("\n📍 Existing Fields:")
        for field in existing_fields:
            print(f"  {field['name']}:")
            print(f"    Style: {field['style']}")
            print(f"    Absolute Rect: {field['rect']}")
            print(f"    Relative to Canvas: {field['relativeToCanvas']}")
        
        # Get stored positioning data
        positioning_data = driver.execute_script("return window.POSITIONING_DATA;")
        if positioning_data:
            print("\n💾 Stored POSITIONING_DATA:")
            for field_name, data in positioning_data.items():
                print(f"  {field_name}: {data}")
        else:
            print("\n💾 No positioning data found")
        
        print("\n🎯 ANALYSIS:")
        if existing_fields:
            for field in existing_fields:
                field_name = field['name']
                style_left = int(field['style']['left'].replace('px', '')) if field['style']['left'] else 0
                style_top = int(field['style']['top'].replace('px', '')) if field['style']['top'] else 0
                
                if positioning_data and field_name in positioning_data:
                    stored_data = positioning_data[field_name]
                    stored_x = stored_data.get('x', 0)
                    stored_y = stored_data.get('y', 0)
                    
                    print(f"\n  {field_name}:")
                    print(f"    Visual Position: ({style_left}, {style_top})")
                    print(f"    Stored PDF Coords: ({stored_x}, {stored_y})")
                    print(f"    Expected Screen Y from PDF: {792 - stored_y}")
                    print(f"    Difference: Y visual={style_top} vs expected={792 - stored_y}")
                    
                    if abs(style_top - (792 - stored_y)) > 5:
                        print(f"    ❌ MISMATCH! Visual position doesn't match stored data")
                    else:
                        print(f"    ✅ Positions match")
        
        return True
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        driver.quit()

if __name__ == "__main__":
    debug_coordinates()
