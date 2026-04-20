"""
NAAMS Standards Site Crawler
Downloads the full site content including all PDFs, HTML pages, images, and other assets.
Produces a PDF index with file sizes and identifies 0-byte files.
"""

import os
import re
import json
import time
import hashlib
import logging
from urllib.parse import urljoin, urlparse, unquote
from collections import defaultdict

import requests
from bs4 import BeautifulSoup

# Configuration
BASE_URL = "https://www.naamsstandards.org/"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "naams_site_dump")
INDEX_FILE = os.path.join(OUTPUT_DIR, "_pdf_index.json")
REPORT_FILE = os.path.join(OUTPUT_DIR, "_crawl_report.txt")
ZERO_BYTE_REPORT = os.path.join(OUTPUT_DIR, "_zero_byte_pdfs.txt")

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("naams_crawler")

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NAAMS-Crawler/1.0"
})

visited_urls = set()
pdf_index = []  # list of dicts: {url, local_path, size_bytes, status}
all_downloaded = []  # all files downloaded
failed_downloads = []


def safe_local_path(url):
    """Convert a URL to a safe local file path."""
    parsed = urlparse(url)
    path = unquote(parsed.path).lstrip("/")
    if not path or path.endswith("/"):
        path = path + "index.html"
    # Replace any problematic characters
    path = path.replace("?", "_q_").replace("&", "_a_").replace("=", "_eq_")
    return os.path.join(OUTPUT_DIR, path)


def download_file(url, local_path):
    """Download a single file from URL to local_path."""
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    try:
        resp = SESSION.get(url, timeout=30, stream=True)
        resp.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        size = os.path.getsize(local_path)
        log.info(f"  Downloaded: {url} -> {local_path} ({size:,} bytes)")
        return size
    except Exception as e:
        log.warning(f"  FAILED: {url} -> {e}")
        failed_downloads.append({"url": url, "error": str(e)})
        return -1


def extract_links(html, page_url):
    """Extract all links from HTML page."""
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    
    # <a href=...>
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if href.startswith("mailto:") or href.startswith("javascript:"):
            continue
        full = urljoin(page_url, href)
        links.add(full)
    
    # <img src=...>
    for tag in soup.find_all("img", src=True):
        full = urljoin(page_url, tag["src"].strip())
        links.add(full)
    
    # <link href=...> (CSS etc.)
    for tag in soup.find_all("link", href=True):
        full = urljoin(page_url, tag["href"].strip())
        links.add(full)
    
    # <script src=...>
    for tag in soup.find_all("script", src=True):
        full = urljoin(page_url, tag["src"].strip())
        links.add(full)
    
    # <area href=...> (image maps)
    for tag in soup.find_all("area", href=True):
        href = tag["href"].strip()
        if href.startswith("mailto:") or href.startswith("javascript:"):
            continue
        full = urljoin(page_url, href)
        links.add(full)
    
    # <frame src=...> and <iframe src=...>
    for tag in soup.find_all(["frame", "iframe"], src=True):
        full = urljoin(page_url, tag["src"].strip())
        links.add(full)
    
    return links


def is_same_domain(url):
    """Check if URL belongs to naamsstandards.org."""
    parsed = urlparse(url)
    return parsed.netloc in ("www.naamsstandards.org", "naamsstandards.org", "")


def is_page(url):
    """Check if URL is an HTML page we should crawl."""
    parsed = urlparse(url)
    path = parsed.path.lower()
    return path.endswith((".htm", ".html", ".asp", ".php", "")) or "/" == path[-1:] if path else True


def crawl_page(url, depth=0, max_depth=5):
    """Recursively crawl a page and download all assets."""
    if url in visited_urls:
        return
    if depth > max_depth:
        return
    if not is_same_domain(url):
        return
    
    # Remove fragment
    url = url.split("#")[0]
    if url in visited_urls:
        return
    visited_urls.add(url)
    
    log.info(f"[Depth {depth}] Crawling: {url}")
    
    try:
        resp = SESSION.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        log.warning(f"  Could not fetch page: {url} -> {e}")
        failed_downloads.append({"url": url, "error": str(e)})
        return
    
    content_type = resp.headers.get("Content-Type", "").lower()
    local_path = safe_local_path(url)
    
    # If it's a PDF or binary, just save it
    if "pdf" in content_type or url.lower().endswith(".pdf"):
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(resp.content)
        size = len(resp.content)
        pdf_index.append({
            "url": url,
            "local_path": local_path,
            "size_bytes": size,
            "status": "ok" if size > 0 else "ZERO_BYTE"
        })
        all_downloaded.append({"url": url, "local_path": local_path, "size": size, "type": "pdf"})
        log.info(f"  PDF saved: {local_path} ({size:,} bytes)")
        return
    
    if "html" not in content_type and "text" not in content_type:
        # Binary file - just save
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(resp.content)
        size = len(resp.content)
        all_downloaded.append({"url": url, "local_path": local_path, "size": size, "type": "binary"})
        log.info(f"  Asset saved: {local_path} ({size:,} bytes)")
        return
    
    # It's HTML - save and extract links
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "wb") as f:
        f.write(resp.content)
    all_downloaded.append({"url": url, "local_path": local_path, "size": len(resp.content), "type": "html"})
    
    # Extract all links
    links = extract_links(resp.text, url)
    
    # Separate PDFs and pages
    for link in links:
        link_clean = link.split("#")[0]
        if not is_same_domain(link_clean):
            continue
        if link_clean in visited_urls:
            continue
        
        parsed = urlparse(link_clean)
        path_lower = parsed.path.lower()
        
        if path_lower.endswith(".pdf"):
            # Download PDF directly
            if link_clean not in visited_urls:
                visited_urls.add(link_clean)
                pdf_local = safe_local_path(link_clean)
                size = download_file(link_clean, pdf_local)
                if size >= 0:
                    pdf_index.append({
                        "url": link_clean,
                        "local_path": pdf_local,
                        "size_bytes": size,
                        "status": "ok" if size > 0 else "ZERO_BYTE"
                    })
                    all_downloaded.append({"url": link_clean, "local_path": pdf_local, "size": size, "type": "pdf"})
        elif path_lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".bmp", ".webp")):
            # Download image
            if link_clean not in visited_urls:
                visited_urls.add(link_clean)
                img_local = safe_local_path(link_clean)
                size = download_file(link_clean, img_local)
                if size >= 0:
                    all_downloaded.append({"url": link_clean, "local_path": img_local, "size": size, "type": "image"})
        elif path_lower.endswith((".css", ".js")):
            # Download static assets
            if link_clean not in visited_urls:
                visited_urls.add(link_clean)
                asset_local = safe_local_path(link_clean)
                size = download_file(link_clean, asset_local)
                if size >= 0:
                    all_downloaded.append({"url": link_clean, "local_path": asset_local, "size": size, "type": "asset"})
        elif path_lower.endswith((".xls", ".xlsx", ".csv", ".zip", ".doc", ".docx")):
            # Download documents
            if link_clean not in visited_urls:
                visited_urls.add(link_clean)
                doc_local = safe_local_path(link_clean)
                size = download_file(link_clean, doc_local)
                if size >= 0:
                    all_downloaded.append({"url": link_clean, "local_path": doc_local, "size": size, "type": "document"})
        elif path_lower.endswith((".htm", ".html", "")):
            # Recurse into HTML pages
            crawl_page(link_clean, depth + 1, max_depth)
        
        # Small delay to be respectful
        time.sleep(0.1)


def generate_reports():
    """Generate crawl report, PDF index, and zero-byte report."""
    
    # Sort PDF index by path
    pdf_index.sort(key=lambda x: x["url"])
    
    # Save JSON index
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(pdf_index, f, indent=2, default=str)
    log.info(f"PDF index saved to {INDEX_FILE}")
    
    # Generate text report
    zero_byte_pdfs = [p for p in pdf_index if p["size_bytes"] == 0]
    
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("NAAMS STANDARDS SITE CRAWL REPORT\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Total URLs visited: {len(visited_urls)}\n")
        f.write(f"Total files downloaded: {len(all_downloaded)}\n")
        f.write(f"Total PDFs found: {len(pdf_index)}\n")
        f.write(f"Zero-byte PDFs: {len(zero_byte_pdfs)}\n")
        f.write(f"Failed downloads: {len(failed_downloads)}\n\n")
        
        # File type breakdown
        type_counts = defaultdict(int)
        type_sizes = defaultdict(int)
        for item in all_downloaded:
            type_counts[item["type"]] += 1
            type_sizes[item["type"]] += item.get("size", 0)
        
        f.write("FILE TYPE BREAKDOWN:\n")
        f.write("-" * 40 + "\n")
        for t in sorted(type_counts.keys()):
            f.write(f"  {t:12s}: {type_counts[t]:5d} files  ({type_sizes[t]:>12,} bytes)\n")
        f.write("\n")
        
        f.write("=" * 80 + "\n")
        f.write("COMPLETE PDF INDEX (sorted by URL)\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"{'#':>4s}  {'Size':>12s}  {'Status':>10s}  URL\n")
        f.write("-" * 80 + "\n")
        for i, p in enumerate(pdf_index, 1):
            size_str = f"{p['size_bytes']:,}" if p['size_bytes'] >= 0 else "FAILED"
            f.write(f"{i:4d}  {size_str:>12s}  {p['status']:>10s}  {p['url']}\n")
        f.write("\n")
        
        if failed_downloads:
            f.write("=" * 80 + "\n")
            f.write("FAILED DOWNLOADS\n")
            f.write("=" * 80 + "\n\n")
            for item in failed_downloads:
                f.write(f"  {item['url']}\n    Error: {item['error']}\n\n")
    
    log.info(f"Crawl report saved to {REPORT_FILE}")
    
    # Zero-byte PDF report
    with open(ZERO_BYTE_REPORT, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("ZERO-BYTE PDF FILES ON NAAMS STANDARDS SITE\n")
        f.write("=" * 80 + "\n\n")
        
        if zero_byte_pdfs:
            f.write(f"Found {len(zero_byte_pdfs)} zero-byte PDF file(s):\n\n")
            for i, p in enumerate(zero_byte_pdfs, 1):
                f.write(f"  {i}. {p['url']}\n")
                f.write(f"     Local: {p['local_path']}\n\n")
        else:
            f.write("No zero-byte PDF files found.\n")
            f.write("All PDFs downloaded successfully with content.\n")
    
    log.info(f"Zero-byte report saved to {ZERO_BYTE_REPORT}")
    
    # Print summary to console
    print("\n" + "=" * 80)
    print("CRAWL COMPLETE - SUMMARY")
    print("=" * 80)
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Total URLs visited: {len(visited_urls)}")
    print(f"Total files downloaded: {len(all_downloaded)}")
    print(f"Total PDFs: {len(pdf_index)}")
    print(f"Zero-byte PDFs: {len(zero_byte_pdfs)}")
    print(f"Failed downloads: {len(failed_downloads)}")
    print()
    print("Reports generated:")
    print(f"  - PDF Index: {INDEX_FILE}")
    print(f"  - Full Report: {REPORT_FILE}")
    print(f"  - Zero-byte PDFs: {ZERO_BYTE_REPORT}")


def main():
    """Main entry point."""
    log.info(f"Starting NAAMS site crawl from {BASE_URL}")
    log.info(f"Output directory: {OUTPUT_DIR}")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Known entry pages to crawl
    entry_pages = [
        BASE_URL,
        BASE_URL + "NAAMSOverview.htm",
        BASE_URL + "publications/nascontents.htm",
        BASE_URL + "publications/nsscontents.htm",
    ]
    
    for page in entry_pages:
        crawl_page(page, depth=0, max_depth=5)
    
    generate_reports()


if __name__ == "__main__":
    main()
