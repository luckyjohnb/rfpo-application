#!/usr/bin/env python3
"""
MEASURE POSITIONING OFFSET
Analyze the exact pixel differences between designer and preview
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

def measure_positioning_offset():
    print("📏 MEASURING POSITIONING OFFSET")
    print("=" * 60)
    
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
        
        # Go to USCAR positioning editor
        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        time.sleep(5)
        
        # Wait for canvas to load
        canvas = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "pdf-canvas"))
        )
        
        print("✅ Canvas loaded")
        
        # Get detailed canvas and field information
        measurement_data = driver.execute_script("""
            const canvas = document.getElementById('pdf-canvas');
            const canvasRect = canvas.getBoundingClientRect();
            const canvasStyle = window.getComputedStyle(canvas);
            
            const fields = document.querySelectorAll('.pdf-field');
            const fieldData = [];
            
            fields.forEach(field => {
                const fieldRect = field.getBoundingClientRect();
                const fieldStyle = window.getComputedStyle(field);
                
                fieldData.push({
                    name: field.dataset.fieldName,
                    
                    // Visual positioning
                    rect: {
                        left: fieldRect.left,
                        top: fieldRect.top,
                        width: fieldRect.width,
                        height: fieldRect.height
                    },
                    
                    // CSS styling
                    style: {
                        left: field.style.left,
                        top: field.style.top,
                        fontSize: fieldStyle.fontSize,
                        fontFamily: fieldStyle.fontFamily
                    },
                    
                    // Position relative to canvas
                    relativeToCanvas: {
                        left: fieldRect.left - canvasRect.left,
                        top: fieldRect.top - canvasRect.top
                    },
                    
                    // Text content
                    textContent: field.textContent.trim()
                });
            });
            
            return {
                canvas: {
                    rect: {
                        left: canvasRect.left,
                        top: canvasRect.top,
                        width: canvasRect.width,
                        height: canvasRect.height
                    },
                    style: {
                        width: canvasStyle.width,
                        height: canvasStyle.height,
                        border: canvasStyle.border,
                        padding: canvasStyle.padding,
                        margin: canvasStyle.margin
                    },
                    computed: {
                        borderLeft: canvasStyle.borderLeftWidth,
                        borderTop: canvasStyle.borderTopWidth,
                        paddingLeft: canvasStyle.paddingLeft,
                        paddingTop: canvasStyle.paddingTop
                    }
                },
                fields: fieldData,
                positioningData: window.POSITIONING_DATA
            };
        """)
        
        print("\n📐 CANVAS MEASUREMENTS:")
        canvas_info = measurement_data['canvas']
        print(f"  Dimensions: {canvas_info['rect']['width']}x{canvas_info['rect']['height']}")
        print(f"  Border: {canvas_info['computed']['borderLeft']} (left), {canvas_info['computed']['borderTop']} (top)")
        print(f"  Padding: {canvas_info['computed']['paddingLeft']} (left), {canvas_info['computed']['paddingTop']} (top)")
        
        print("\n📍 FIELD MEASUREMENTS:")
        for field in measurement_data['fields']:
            stored_data = measurement_data['positioningData'].get(field['name'], {})
            
            print(f"\n  {field['name'].upper()}:")
            print(f"    Visual position: ({field['relativeToCanvas']['left']:.1f}, {field['relativeToCanvas']['top']:.1f})")
            print(f"    CSS style: {field['style']['left']}, {field['style']['top']}")
            print(f"    Stored coordinates: ({stored_data.get('x', 'N/A')}, {stored_data.get('y', 'N/A')})")
            print(f"    Text content: '{field['textContent']}'")
            print(f"    Font: {field['style']['fontSize']} {field['style']['fontFamily']}")
            
            # Calculate expected position from stored data
            if stored_data.get('x') is not None and stored_data.get('y') is not None:
                expected_screen_x = stored_data['x']
                expected_screen_y = 792 - stored_data['y']  # Convert PDF Y to screen Y
                
                actual_x = float(field['style']['left'].replace('px', ''))
                actual_y = float(field['style']['top'].replace('px', ''))
                
                offset_x = actual_x - expected_screen_x
                offset_y = actual_y - expected_screen_y
                
                print(f"    Expected position: ({expected_screen_x:.1f}, {expected_screen_y:.1f})")
                print(f"    Actual position: ({actual_x:.1f}, {actual_y:.1f})")
                print(f"    Offset: ({offset_x:.1f}, {offset_y:.1f}) pixels")
        
        print("\n🎯 OFFSET ANALYSIS:")
        print("Small offsets (< 5px) might be due to:")
        print("  - Canvas border/padding affecting coordinate calculations")
        print("  - Font rendering differences between canvas and PDF")
        print("  - Rounding errors in coordinate conversions")
        print("  - PDF text positioning vs HTML element positioning")
        
        return True
        
    except Exception as e:
        print(f"❌ Measurement failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        driver.quit()

if __name__ == "__main__":
    measure_positioning_offset()
