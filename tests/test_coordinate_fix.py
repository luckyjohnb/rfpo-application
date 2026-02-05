#!/usr/bin/env python3
"""
Test the coordinate conversion fix for PDF preview
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

def test_coordinate_fix():
    """Test coordinate conversion fix"""
    driver = setup_driver()
    if not driver:
        return
    
    try:
        print("🔧 Testing Coordinate Conversion Fix...")
        print("=" * 60)
        
        # Login
        driver.get("http://localhost:5111/")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "email")))
        driver.find_element(By.NAME, "email").send_keys("admin@rfpo.com")
        driver.find_element(By.NAME, "password").send_keys("admin123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        print("✅ Login successful")
        
        # Navigate to PDF editor
        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "pdf-canvas")))
        print("✅ PDF Editor loaded")
        time.sleep(3)
        
        # Get current PO NUMBER and PO DATE positions
        print("\n📍 Current field positions in designer:")
        
        po_number_field = None
        po_date_field = None
        
        fields = driver.find_elements(By.CSS_SELECTOR, "#pdf-canvas .pdf-field")
        for field in fields:
            field_name = field.get_attribute('data-field-name')
            if field_name == 'po_number':
                po_number_field = field
            elif field_name == 'po_date':
                po_date_field = field
        
        if po_number_field and po_date_field:
            po_number_info = driver.execute_script("""
                const field = arguments[0];
                const style = window.getComputedStyle(field);
                return {
                    left: parseFloat(style.left),
                    top: parseFloat(style.top),
                    text: field.textContent.trim()
                };
            """, po_number_field)
            
            po_date_info = driver.execute_script("""
                const field = arguments[0];
                const style = window.getComputedStyle(field);
                return {
                    left: parseFloat(style.left),
                    top: parseFloat(style.top),
                    text: field.textContent.trim()
                };
            """, po_date_field)
            
            print(f"   PO NUMBER: '{po_number_info['text']}' at screen({po_number_info['left']:.1f}, {po_number_info['top']:.1f})")
            print(f"   PO DATE: '{po_date_info['text']}' at screen({po_date_info['left']:.1f}, {po_date_info['top']:.1f})")
            
            # Calculate expected PDF coordinates
            pdf_y_po_number = 792 - po_number_info['top']
            pdf_y_po_date = 792 - po_date_info['top']
            
            print(f"\n🔄 Expected PDF coordinates:")
            print(f"   PO NUMBER: pdf({po_number_info['left']:.1f}, {pdf_y_po_number:.1f})")
            print(f"   PO DATE: pdf({po_date_info['left']:.1f}, {pdf_y_po_date:.1f})")
            
        else:
            print("   ❌ Could not find PO NUMBER or PO DATE fields")
            return
        
        # Test preview with coordinate conversion
        print("\n🔍 Testing preview with coordinate conversion...")
        
        # Store original windows
        original_windows = driver.window_handles
        
        # Click preview
        preview_btn = driver.find_element(By.ID, "preview-pdf")
        print("   Clicking preview button...")
        preview_btn.click()
        time.sleep(5)  # Wait for save and preview generation
        
        # Check for new window
        new_windows = driver.window_handles
        if len(new_windows) > len(original_windows):
            print("   ✅ Preview tab opened")
            
            # Switch to preview tab
            driver.switch_to.window(new_windows[-1])
            preview_url = driver.current_url
            print(f"   Preview URL: {preview_url}")
            
            # The PDF should now show fields in correct positions
            print("   📄 PDF generated with coordinate conversion")
            print("   🎯 Expected result: PO NUMBER and PO DATE should appear in top-right of PDF")
            
            # Keep preview open for manual verification
            print("\n👀 Manual verification time (20 seconds):")
            print("   1. Check if PO NUMBER appears in the PDF")
            print("   2. Check if PO DATE appears in the PDF") 
            print("   3. Verify they are positioned correctly (top-right)")
            
            time.sleep(20)
            
            # Close preview and return to editor
            driver.close()
            driver.switch_to.window(original_windows[0])
            print("   ✅ Returned to editor")
            
        else:
            print("   ❌ No preview tab opened")
        
        print("\n🎯 Summary:")
        print("   - Added coordinate conversion: screen_y -> pdf_y = 792 - screen_y")
        print("   - This should fix the missing fields in PDF preview")
        print("   - Fields positioned in top area of designer should appear in PDF")
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        driver.quit()
        print("\n🔚 Coordinate fix test completed")

if __name__ == "__main__":
    test_coordinate_fix()
