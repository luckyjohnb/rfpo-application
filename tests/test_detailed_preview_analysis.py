#!/usr/bin/env python3
"""
DETAILED PREVIEW ANALYSIS
More thorough investigation of what's actually happening in the preview
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--window-size=1400,1000")
    return webdriver.Chrome(options=chrome_options)

def detailed_preview_analysis():
    print("🔍 DETAILED PREVIEW ANALYSIS")
    print("="*80)
    
    driver = setup_driver()
    
    try:
        # Login and navigate
        print("📋 Setup...")
        driver.get("http://localhost:5111/login")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "email")))
        
        driver.find_element(By.NAME, "email").send_keys("admin@rfpo.com")
        driver.find_element(By.NAME, "password").send_keys("admin123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)
        
        driver.get("http://localhost:5111/pdf-positioning/editor/00000014/po_template")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "pdf-canvas")))
        time.sleep(5)
        
        # Clear elements
        print("📋 Clearing all elements...")
        try:
            clear_button = driver.find_element(By.ID, "clear-canvas")
            clear_button.click()
            time.sleep(1)
            driver.switch_to.alert.accept()
            time.sleep(2)
        except:
            pass
        
        # Save configuration
        save_button = driver.find_element(By.ID, "save-config")
        driver.execute_script("arguments[0].click();", save_button)
        time.sleep(3)
        
        # Check what URL the preview actually goes to
        print("📋 Analyzing preview URL and content...")
        
        # Get the preview URL directly
        preview_url = "http://localhost:5111/api/pdf-positioning/preview/1"
        print(f"   Preview URL: {preview_url}")
        
        # Navigate directly to preview
        driver.get(preview_url)
        time.sleep(5)
        
        # Analyze the page thoroughly
        page_info = driver.execute_script("""
            return {
                url: window.location.href,
                title: document.title,
                bodyHTML: document.body.innerHTML,
                bodyText: document.body.innerText,
                documentHTML: document.documentElement.outerHTML.substring(0, 1000),
                readyState: document.readyState,
                contentType: document.contentType || 'unknown',
                hasEmbedElements: document.querySelectorAll('embed').length,
                hasObjectElements: document.querySelectorAll('object').length,
                hasIframeElements: document.querySelectorAll('iframe').length,
                bodyChildren: document.body.children.length
            };
        """)
        
        print(f"   Current URL: {page_info['url']}")
        print(f"   Page title: '{page_info['title']}'")
        print(f"   Content type: {page_info['contentType']}")
        print(f"   Ready state: {page_info['readyState']}")
        print(f"   Body children: {page_info['bodyChildren']}")
        print(f"   Embed elements: {page_info['hasEmbedElements']}")
        print(f"   Object elements: {page_info['hasObjectElements']}")
        print(f"   Iframe elements: {page_info['hasIframeElements']}")
        
        print(f"   Body text length: {len(page_info['bodyText'])}")
        print(f"   Body HTML length: {len(page_info['bodyHTML'])}")
        
        if page_info['bodyText']:
            print(f"   Body text sample: '{page_info['bodyText'][:200]}{'...' if len(page_info['bodyText']) > 200 else ''}'")
        
        if page_info['bodyHTML']:
            print(f"   Body HTML sample: '{page_info['bodyHTML'][:200]}{'...' if len(page_info['bodyHTML']) > 200 else ''}'")
        
        print(f"   Document HTML sample: '{page_info['documentHTML']}'")
        
        # Take screenshot
        driver.save_screenshot("DETAILED_PREVIEW_ANALYSIS.png")
        print("   📸 Screenshot: DETAILED_PREVIEW_ANALYSIS.png")
        
        # Check if this is actually a PDF or just a blank page
        is_pdf = (
            page_info['contentType'] == 'application/pdf' or
            'pdf' in page_info['url'].lower() or
            page_info['hasEmbedElements'] > 0 or
            page_info['hasObjectElements'] > 0
        )
        
        is_blank = (
            len(page_info['bodyText'].strip()) == 0 and
            len(page_info['bodyHTML'].strip()) == 0
        )
        
        print(f"\n📊 ANALYSIS RESULTS:")
        print(f"   Is PDF: {'✅' if is_pdf else '❌'}")
        print(f"   Is blank page: {'✅' if is_blank else '❌'}")
        
        if is_blank and not is_pdf:
            print("   🔍 This appears to be a blank HTML page, not a PDF!")
            print("   The preview might not be generating properly.")
        elif is_pdf:
            print("   🔍 This appears to be a PDF document.")
        else:
            print("   🔍 This appears to be an HTML page with content.")
        
        # Try to check the actual HTTP response
        print("\n📋 Checking HTTP response...")
        try:
            # Navigate again and check for errors in console
            logs = driver.get_log('browser')
            if logs:
                print("   Browser console logs:")
                for log in logs[-10:]:  # Last 10 logs
                    print(f"      {log['level']}: {log['message']}")
            else:
                print("   No browser console errors")
        except Exception as e:
            print(f"   Could not get browser logs: {e}")
        
        return {
            'is_pdf': is_pdf,
            'is_blank': is_blank,
            'content_length': len(page_info['bodyText']),
            'url': page_info['url']
        }
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        driver.quit()

if __name__ == "__main__":
    result = detailed_preview_analysis()
    
    print(f"\n" + "="*80)
    print("🏆 DETAILED PREVIEW ANALYSIS RESULTS")
    print("="*80)
    
    if result:
        print(f"📊 FINDINGS:")
        print(f"   • URL: {result['url']}")
        print(f"   • Is PDF: {'Yes' if result['is_pdf'] else 'No'}")
        print(f"   • Is blank: {'Yes' if result['is_blank'] else 'No'}")
        print(f"   • Content length: {result['content_length']} characters")
        print()
        
        if result['is_blank'] and not result['is_pdf']:
            print("🔍 CONCLUSION: Preview is loading a blank HTML page")
            print("   This suggests the PDF generation might be failing")
            print("   or the preview route is not working correctly.")
        elif result['is_pdf']:
            print("🔍 CONCLUSION: Preview is loading a PDF")
            print("   Need to investigate PDF content further.")
        else:
            print("🔍 CONCLUSION: Preview has HTML content")
            print("   This might indicate an error page or unexpected response.")
            
    print("\n📸 Check DETAILED_PREVIEW_ANALYSIS.png for visual confirmation")
    print("="*80)
