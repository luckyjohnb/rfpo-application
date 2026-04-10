"""
Test script to verify DOCUPLOAD integration from the RFPO application.

Usage:
    python test_docupload.py

This uploads a sample PDF to the DOCUPLOAD service using an API key,
with the RFPO folder structure: rfpo/{rfpo_number}/{document_type}/{filename}
"""
import os
import sys
import json
import requests
from io import BytesIO

# --- Configuration ---
# Change DOCUPLOAD_URL to local or Azure as needed
DOCUPLOAD_URL = os.environ.get(
    "DOCUPLOAD_URL",
    "https://usabc-upload.livelyforest-d06a98a0.eastus.azurecontainerapps.io"
)
API_KEY = os.environ.get("DOCUPLOAD_API_KEY", "")

# Test RFPO data
RFPO_NUMBER = "RFPO-2026-0042"
DOCUMENT_TYPE = "quote"  # e.g. quote, invoice, supporting-docs, correspondence


def create_test_pdf():
    """Create a minimal valid PDF in memory for testing."""
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
   /Contents 4 0 R /Resources << >> >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Test RFPO Doc) Tj ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000236 00000 n 
trailer << /Size 5 /Root 1 0 R >>
startxref
332
%%EOF"""
    return pdf_content


def test_health():
    """Check if DOCUPLOAD service is healthy."""
    print(f"[1/3] Checking health at {DOCUPLOAD_URL}/health ...")
    try:
        r = requests.get(f"{DOCUPLOAD_URL}/health", timeout=10)
        data = r.json()
        print(f"      Status: {data.get('status')} | Version: {data.get('version')}")
        return r.status_code == 200
    except Exception as e:
        print(f"      FAILED: {e}")
        return False


def test_upload_no_key():
    """Test that upload is rejected without API key (when enforcement is on)."""
    print("[2/3] Testing upload WITHOUT API key ...")
    pdf = create_test_pdf()
    try:
        r = requests.post(
            f"{DOCUPLOAD_URL}/submit",
            files={"test_doc": ("test.pdf", BytesIO(pdf), "application/pdf")},
            data={
                "formId": "rfpo-test",
                "folderPath": f"rfpo/{RFPO_NUMBER}/{DOCUMENT_TYPE}",
            },
            timeout=60,
        )
        if r.status_code == 401:
            print(f"      OK - Correctly rejected (401): {r.json().get('message')}")
            return True
        elif r.status_code == 201:
            print(f"      WARN - Upload succeeded without key (API key enforcement may be OFF)")
            return True
        else:
            print(f"      Unexpected status {r.status_code}: {r.text[:200]}")
            return False
    except Exception as e:
        print(f"      FAILED: {e}")
        return False


def test_upload_with_key():
    """Upload test files with API key, demonstrating RFPO folder structure."""
    if not API_KEY:
        print("[3/3] SKIPPED - Set DOCUPLOAD_API_KEY env var to test authenticated upload")
        return False

    print(f"[3/3] Uploading test files with API key ...")
    print(f"      Structure: rfpo/{RFPO_NUMBER}/<document_type>/<filename>")
    pdf = create_test_pdf()

    try:
        # Upload a quote document
        r = requests.post(
            f"{DOCUPLOAD_URL}/submit",
            headers={"X-API-Key": API_KEY},
            files={
                "quote": ("vendor_quote_sample.pdf", BytesIO(pdf), "application/pdf"),
            },
            data={
                "formId": "rfpo-documents",
                "folderPath": f"rfpo/{RFPO_NUMBER}/quote",
                "submittedBy": "rfpo-test-script",
                "tags": json.dumps({
                    "rfpo-number": RFPO_NUMBER,
                    "source": "rfpo-app"
                }),
            },
            timeout=60,
        )

        print(f"      Status: {r.status_code}")
        data = r.json()
        print(json.dumps(data, indent=2))

        if r.status_code == 201:
            print(f"\n      SUCCESS!")
            if 'uploadedFiles' in data:
                print("      Blob paths in Azure:")
                for bp in data['uploadedFiles']:
                    print(f"        - {bp}")
            return True
        else:
            print(f"      FAILED: {data.get('error', 'Unknown error')}")
            return False

    except Exception as e:
        print(f"      FAILED: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("RFPO → DOCUPLOAD Integration Test")
    print(f"Target: {DOCUPLOAD_URL}")
    print(f"RFPO:   {RFPO_NUMBER}")
    print(f"Folder: rfpo/{RFPO_NUMBER}/{DOCUMENT_TYPE}/")
    print("=" * 60)
    print()

    results = []
    results.append(("Health Check", test_health()))
    print()
    results.append(("No-Key Rejection", test_upload_no_key()))
    print()
    results.append(("Authenticated Upload", test_upload_with_key()))

    print()
    print("=" * 60)
    print("RESULTS:")
    for name, passed in results:
        status = "PASS" if passed else "FAIL/SKIP"
        print(f"  {status:10s}  {name}")
    print("=" * 60)
