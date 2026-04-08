#!/usr/bin/env python3
"""Test script to verify RFPO content in the HTML response"""

import urllib.request
import re


def test_rfpo_content():
    try:
        # Get the HTML content
        response = urllib.request.urlopen("http://127.0.0.1:5000/app")
        content = response.read().decode("utf-8")

        # Check for RFPO-related content
        rfpo_found = "RFPO" in content
        rfpo_submenu = "showSection('rfpo-app')" in content
        rfpo_section = 'id="rfpo-app"' in content

        print("=== RFPO Content Test ===")
        print(f"RFPO text found: {rfpo_found}")
        print(f"RFPO submenu link found: {rfpo_submenu}")
        print(f"RFPO section found: {rfpo_section}")

        # Check Applications menu structure
        apps_menu = "toggleAppsMenu()" in content
        print(f"Applications menu toggle found: {apps_menu}")

        if all([rfpo_found, rfpo_submenu, rfpo_section, apps_menu]):
            print("✅ All RFPO components are present in HTML")
        else:
            print("❌ Some RFPO components are missing")

        # Look for the specific submenu HTML
        submenu_pattern = r'<div class="nav-submenu">.*?RFPO.*?</div>'
        submenu_match = re.search(submenu_pattern, content, re.DOTALL)
        print(f"Submenu HTML structure found: {submenu_match is not None}")

    except Exception as e:
        print(f"Error testing RFPO content: {e}")


if __name__ == "__main__":
    test_rfpo_content()
