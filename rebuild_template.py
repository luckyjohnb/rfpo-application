#!/usr/bin/env python3
"""
Rebuild po.pdf template with improved middle column layout.

Changes from original:
1. Middle column widened: right edge x=385 -> x=415 (30pt wider)
2. Ship-to box narrowed: left edge x=392 -> x=420 
3. PROJECT box: 2-row height (30pt instead of 18pt)
4. "DELIVERY:" label (date field) renamed to "DATE:"
5. Detail box (DELIVERY/Type/Payment/Routing) shrunk - tighter vertical spacing
6. Adjusted all boxes to maintain alignment
"""
import sys, os
sys.path.insert(0, '/app')

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# Read original template to extract ALL elements, then rebuild with modifications
import pdfplumber

orig = pdfplumber.open('/app/static/po_files/po.pdf')
page = orig.pages[0]
W, H = page.width, page.height  # 612 x 792

c = canvas.Canvas('/app/static/po_files/po_new.pdf', pagesize=letter)

# ============================================================
# HELPER: Draw a box (stroke only) using pdfplumber coords (top-left origin)
# Convert to PDF coords (bottom-left origin)
# ============================================================
def box(x0, top, x1, bottom, fill=False):
    """Draw rect. top/bottom are distances from page top (pdfplumber convention)."""
    pdf_y_bottom = H - bottom
    pdf_y_top = H - top
    height = pdf_y_top - pdf_y_bottom
    if fill:
        c.setFillColorRGB(0.95, 0.95, 0.95)
        c.rect(x0, pdf_y_bottom, x1 - x0, height, stroke=1, fill=1)
        c.setFillColorRGB(0, 0, 0)
    else:
        c.rect(x0, pdf_y_bottom, x1 - x0, height, stroke=1, fill=0)

def label(text, x, top, size=8, bold=False):
    """Draw label text. top = distance from page top."""
    pdf_y = H - top - size  # approximate baseline
    if bold:
        c.setFont("Helvetica-Bold", size)
    else:
        c.setFont("Helvetica", size)
    c.drawString(x, pdf_y, text)
    c.setFont("Helvetica", 8)  # reset

def label_at_pdf_y(text, x, pdf_y, size=8, bold=False):
    """Draw label at exact PDF y coordinate (baseline)."""
    if bold:
        c.setFont("Helvetica-Bold", size)
    else:
        c.setFont("Helvetica", size)
    c.drawString(x, pdf_y, text)
    c.setFont("Helvetica", 8)

# ============================================================
# Set line width to match original thin borders
# ============================================================
c.setLineWidth(0.5)
c.setStrokeColorRGB(0, 0, 0)

# ============================================================
# TOP SECTION - NUMBER, DATE OF ORDER (unchanged)
# ============================================================
# NUMBER: box  x=392-590, pdfplumber top=18, bottom=52
box(392, 18, 590, 52)
label_at_pdf_y("NUMBER:", 394, 764, size=8, bold=True)

# "Show this number..." small text
c.setFont("Helvetica", 5)
c.drawString(437, 742, "Show this number on all shipping and billing documents")
c.setFont("Helvetica", 8)

# DATE OF ORDER: box  x=392-590, top=52, bottom=72
box(392, 52, 590, 72)
label_at_pdf_y("DATE OF ORDER:", 394, 730, size=8, bold=True)

# ============================================================
# TITLE STRIP - PURCHASE ORDER
# ============================================================
# Strip: x=46-590, top=80, bottom=105
box(46, 80, 590, 105)
label_at_pdf_y("PURCHASE ORDER", 52, 690, size=16, bold=True)
label_at_pdf_y("PAGE", 505, 694, size=8)
label_at_pdf_y("OF", 545, 694, size=8)

# ============================================================ 
# MAIN FORM AREA - MODIFIED LAYOUT
# ============================================================
# Original layout:
#   VENDOR box:    x=46-244,  top=113, bottom=257 (144pt tall) -- KEEP
#   SHIP TO box:   x=392-590, top=113, bottom=257 (144pt tall) -- NARROW to x=420-590
#   Middle column: x=250-385 (4 sub-boxes)                     -- WIDEN to x=250-415
#
# New middle column sub-boxes (x=250-415, total height 113-257 = 144pt):
#   PROJECT:  top=113, bottom=145 (32pt tall - 2 rows)
#   DATE:     top=145, bottom=163 (18pt - renamed from DELIVERY)
#   PAYMENT:  top=163, bottom=181 (18pt)
#   Detail:   top=181, bottom=257 (76pt - DELIVERY/Type/Payment/Routing - slightly reduced)

# VENDOR box (unchanged)
box(46, 113, 244, 257)
label_at_pdf_y("VENDOR:", 49, 669, size=8, bold=True)

# Seller text (in vendor box area, small)
c.setFont("Helvetica", 5)
c.drawString(50, 544, "(Seller) will sell and deliver the supplies and services specified")
c.drawString(50, 536, "herein in accordance with the terms and conditions hereof.")
c.setFont("Helvetica", 8)

# SHIP TO box (narrowed - left edge from 392 to 420)
box(420, 113, 590, 257)
label_at_pdf_y("SHIP TO:", 424, 669, size=8, bold=True)

# Middle column sub-boxes (widened from 385 to 415)
MID_L = 250
MID_R = 415

# PROJECT box (taller - 32pt for 2 rows)
PROJ_TOP = 113
PROJ_BOT = 145
box(MID_L, PROJ_TOP, MID_R, PROJ_BOT)
label_at_pdf_y("PROJECT:", 253, 669, size=8, bold=True)

# DATE box (renamed from DELIVERY)
DATE_TOP = 145
DATE_BOT = 163
box(MID_L, DATE_TOP, MID_R, DATE_BOT)
label_at_pdf_y("DATE:", 253, 641, size=8, bold=True)

# PAYMENT box
PAY_TOP = 163
PAY_BOT = 181
box(MID_L, PAY_TOP, MID_R, PAY_BOT)
label_at_pdf_y("PAYMENT:", 253, 621, size=8, bold=True)

# Detail box (DELIVERY method / Type & Place / Payment for Transportation / Routing)
DET_TOP = 181
DET_BOT = 257
box(MID_L, DET_TOP, MID_R, DET_BOT)
# Labels inside detail box - tighter vertical spacing (10pt instead of ~12pt)
det_base_y = H - DET_TOP - 12  # first label baseline
c.setFont("Helvetica", 7)
c.drawString(253, det_base_y, "DELIVERY:")
c.drawString(253, det_base_y - 11, "Type & Place:")
c.drawString(253, det_base_y - 22, "Payment for Transportation:")
c.drawString(253, det_base_y - 33, "Routing:")
c.setFont("Helvetica", 8)

# ============================================================
# VENDOR IS / GOVERNMENT FUNDING strip
# ============================================================
# Left: x=46-244, top=259, bottom=280
box(46, 259, 244, 280)
label_at_pdf_y("VENDOR IS:", 49, 523, size=8, bold=True)
c.setFont("Helvetica", 7)
c.drawString(60, 514, "SMALL BUSINESS")
c.drawString(140, 514, "UNIVERSITY")
c.drawString(199, 514, "NON-PROFIT")
c.setFont("Helvetica", 8)

# Right: x=250-590, top=259, bottom=280
box(250, 259, 590, 280)
label_at_pdf_y("U.S. Government Funding", 253, 522, size=8)
label_at_pdf_y("under Agreement Number:", 253, 513, size=8)
c.setFont("Helvetica", 5)
c.drawString(504, 519, "(See Page 4 in Terms & Conditions)")
c.setFont("Helvetica", 8)

# ============================================================
# LINE ITEMS TABLE HEADERS
# ============================================================
# QTY header: x=46-85
box(46, 282, 85, 299)
label_at_pdf_y("QTY", 50, 496, size=8, bold=True)

# DESCRIPTION header: x=90-424 (match data column edges)
box(90, 282, 424, 299)
label_at_pdf_y("DESCRIPTION OF SUPPLIES OR SERVICES", 95, 496, size=8, bold=True)

# UNIT PRICE header: x=430-509 (match data column edges)
box(430, 282, 509, 299)
label_at_pdf_y("UNIT PRICE", 460, 496, size=8, bold=True)

# TOTAL PRICE header: x=515-589 (match data column edges)
box(515, 282, 589, 299)
label_at_pdf_y("TOTAL PRICE", 532, 496, size=8, bold=True)

# ============================================================
# LINE ITEMS BODY (empty columns)
# ============================================================
box(46, 299, 85, 616)     # QTY column (top flush with header bottom)
box(90, 299, 424, 616)    # Description column
box(430, 299, 509, 616)   # Unit price column
box(515, 299, 589, 616)   # Total price column

# ============================================================
# BOTTOM SECTION - REQUESTOR / INVOICE TO / APPROVED
# ============================================================
box(46, 624, 244, 750)
label_at_pdf_y("REQUESTOR:", 49, 156, size=8, bold=True)

box(249, 624, 447, 750)
label_at_pdf_y("INVOICE TO:", 252, 156, size=8, bold=True)

box(452, 624, 589, 750)
label_at_pdf_y("APPROVED:", 455, 156, size=8, bold=True)

# ============================================================
# SAVE
# ============================================================
c.save()
print("New template saved to /app/static/po_files/po_new.pdf")

# Verify with pdfplumber
verify = pdfplumber.open('/app/static/po_files/po_new.pdf')
vpage = verify.pages[0]
print(f"Page: {vpage.width}x{vpage.height}")
words = vpage.extract_words(keep_blank_chars=True, x_tolerance=2, y_tolerance=2)
print(f"Labels: {len(words)}")
for w in sorted(words, key=lambda ww: (ww['top'], ww['x0'])):
    pdf_y = vpage.height - w['bottom']
    print(f"  x={w['x0']:.0f}-{w['x1']:.0f}  pdfY={pdf_y:.0f}  {w['text'][:50]}")
