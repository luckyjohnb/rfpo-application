#!/usr/bin/env python3
"""
Trigger PDF generation to see debug output
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

def test_pdf_debug():
    """Trigger PDF preview to see debug output"""
    driver = setup_driver()
    if not driver:
        return
    
    try:
        print("🔍 Triggering PDF generation to see debug output...")
        print("(Check server console for debug messages)")
        print("=" * 60)
        
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
        print("📄 Clicking preview to trigger PDF generation...")
        print("   (Watch server console for debug output)")
        
        # Click preview
        preview_btn = driver.find_element(By.ID, "preview-pdf")
        preview_btn.click()
        
        print("⏳ Waiting 10 seconds for PDF generation and debug output...")
        time.sleep(10)
        
        print("✅ Preview triggered - check server console for:")
        print("   🎯 PDF Generator initialization messages")
        print("   🔄 Position conversion messages")
        print("   📝 Field drawing messages")
        print("   ⚠️  Warning messages about coordinates")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    test_pdf_debug()
