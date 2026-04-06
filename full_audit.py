#!/usr/bin/env python3
"""Complete audit of PO template and overlay alignment"""
import sys, os
sys.path.insert(0, '/app')
os.environ['FLASK_APP'] = 'custom_admin'
import pdfplumber

# ========== STEP 1: Full template analysis ==========
print("=" * 80)
print("STEP 1: TEMPLATE LAYOUT ANALYSIS (po.pdf)")
print("=" * 80)

tpdf = pdfplumber.open('/app/static/po_files/po.pdf')
tpage = tpdf.pages[0]
print(f"Page: {tpage.width}x{tpage.height}")

print("\n--- RECTANGLES (boxes/cells) sorted top-to-bottom ---")
rects = tpage.rects
for r in sorted(rects, key=lambda r: (r['top'], r['x0'])):
    x0, y0, x1, y1 = r['x0'], r['y0'], r['x1'], r['y1']
    w, h = x1 - x0, y1 - y0
    if w > 25 and h > 8:
        pdf_bot = tpage.height - y1
        pdf_top = tpage.height - y0
        print(f"  [{x0:5.0f},{pdf_bot:5.0f}]-[{x1:5.0f},{pdf_top:5.0f}]  {w:5.0f}x{h:4.0f}")

print("\n--- TEXT LABELS sorted top-to-bottom ---")
words = tpage.extract_words(keep_blank_chars=True, x_tolerance=2, y_tolerance=2)
for w in sorted(words, key=lambda w: (w['top'], w['x0'])):
    pdf_y = tpage.height - w['bottom']
    print(f"  x={w['x0']:6.1f}-{w['x1']:6.1f}  pdfY={pdf_y:6.1f}  '{w['text'][:55]}'")

# ========== STEP 2: Generate RFPO #28 proof ==========
print("\n" + "=" * 80)
print("STEP 2: GENERATE RFPO #28 PROOF")
print("=" * 80)

from custom_admin import create_app
app = create_app()

with app.app_context():
    from models import db, RFPO, Project, Consortium, Vendor, VendorSite, PDFPositioning
    from pdf_generator import RFPOPDFGenerator

    rfpo = RFPO.query.get(28)
    project = Project.query.filter_by(project_id=rfpo.project_id).first()
    consortium = Consortium.query.filter_by(consort_id=rfpo.consortium_id).first()
    vendor = Vendor.query.get(rfpo.vendor_id) if rfpo.vendor_id else None
    vendor_site = None
    if rfpo.vendor_site_id:
        try: vendor_site = VendorSite.query.get(int(rfpo.vendor_site_id))
        except: pass

    print(f"RFPO ID: {rfpo.rfpo_id}")
    print(f"PO#: {rfpo.po_number}")
    print(f"Project: [{project.ref}] {project.name}")
    print(f"Vendor: {vendor.company_name if vendor else 'None'}")
    if vendor:
        print(f"  Contact: {vendor.contact_name}")
        print(f"  Address: {vendor.contact_address}")
        print(f"  City/St/Zip: {vendor.contact_city}, {vendor.contact_state} {vendor.contact_zip}")
        print(f"  Phone: {vendor.contact_tel}")
    if vendor_site:
        print(f"  Site Contact: {vendor_site.contact_name}")
        print(f"  Site Address: {vendor_site.contact_address}")
    print(f"Ship To: {rfpo.shipto_name}")
    print(f"Ship Addr: {repr(rfpo.shipto_address)}")
    print(f"Delivery: {rfpo.delivery_date}")
    print(f"Govt Agreement: {repr(rfpo.government_agreement_number)}")
    print(f"Items: {len(rfpo.line_items)}")
    for li in rfpo.line_items:
        print(f"  qty={li.quantity} '{li.description}' ${li.unit_price} = ${li.total_price} cap={li.is_capital_equipment}")
    print(f"Subtotal: ${rfpo.subtotal}  CostShare: {rfpo.cost_share_amount}  Total: ${rfpo.total_amount}")
    print(f"Requestor: {rfpo.requestor_id}")
    print(f"Invoice: {repr(rfpo.invoice_address)}")

    generator = RFPOPDFGenerator(positioning_config=None)
    pdf_buffer = generator.generate_po_pdf(rfpo, consortium, project, vendor, vendor_site)
    with open('/app/audit_proof.pdf', 'wb') as f:
        f.write(pdf_buffer.getvalue())

# ========== STEP 3: Full overlay analysis ==========
print("\n" + "=" * 80)
print("STEP 3: OVERLAY POSITION AUDIT")
print("=" * 80)

pdf = pdfplumber.open('/app/audit_proof.pdf')
page = pdf.pages[0]
pwords = page.extract_words(keep_blank_chars=True, x_tolerance=2, y_tolerance=2)
template_texts = set(w['text'][:40] for w in words)

print("\n--- ALL OVERLAY TEXT (non-template) ---")
for w in sorted(pwords, key=lambda w: (w['top'], w['x0'])):
    pdf_y = page.height - w['bottom']
    text = w['text'][:60]
    if w['text'][:40] not in template_texts:
        print(f"  x={w['x0']:6.1f}-{w['x1']:6.1f}  pdfY={pdf_y:6.1f}  '{text}'")

# ========== STEP 4: Check every overlay against its target box ==========
print("\n" + "=" * 80)
print("STEP 4: BOX CONTAINMENT CHECK")
print("=" * 80)

# Build box map from template rects
boxes = []
for r in rects:
    x0, y0, x1, y1 = r['x0'], r['y0'], r['x1'], r['y1']
    w, h = x1 - x0, y1 - y0
    if w > 25 and h > 8:
        pdf_bot = tpage.height - y1
        pdf_top = tpage.height - y0
        boxes.append({'x0': x0, 'y0': pdf_bot, 'x1': x1, 'y1': pdf_top, 'w': w, 'h': h})

for w in sorted(pwords, key=lambda w: (w['top'], w['x0'])):
    pdf_y = page.height - w['bottom']
    text = w['text'][:50]
    if w['text'][:40] not in template_texts:
        x0, x1 = w['x0'], w['x1']
        # Find which box(es) contain or overlap this text
        containing = []
        overflows = []
        for i, b in enumerate(boxes):
            # Check if text baseline is in box vertically
            if b['y0'] <= pdf_y <= b['y1']:
                if b['x0'] <= x0 and x1 <= b['x1']:
                    containing.append(f"box[{b['x0']:.0f},{b['y0']:.0f}]-[{b['x1']:.0f},{b['y1']:.0f}]")
                elif b['x0'] <= x0 <= b['x1']:
                    overflows.append(f"OVERFLOW right by {x1-b['x1']:.0f}px from box[{b['x0']:.0f},{b['y0']:.0f}]-[{b['x1']:.0f},{b['y1']:.0f}]")
        
        status = ""
        if containing:
            status = f"IN {containing[0]}"
        elif overflows:
            status = overflows[0]
        else:
            status = "NOT IN ANY BOX"
        
        flag = "  " if containing else "**"
        print(f"  {flag} '{text}' at x={x0:.0f}-{x1:.0f} y={pdf_y:.0f}: {status}")

# ========== STEP 5: Label-to-value spacing check ==========
print("\n" + "=" * 80)
print("STEP 5: LABEL-VALUE SPACING / PADDING CHECK")
print("=" * 80)

# Identify key labels and their expected values
label_checks = [
    ("NUMBER:", 445, "PO number value"),
    ("DATE OF ORDER:", 490, "Date value"),
    ("VENDOR:", None, "Vendor company"),
    ("SHIP TO:", None, "Ship to name"),
    ("PROJECT:", 295, "Project value"),
    ("DATE:", 280, "Delivery date"),
    ("REQUESTOR:", None, "Requestor ID"),
    ("INVOICE TO:", None, "Invoice address"),
]

for lbl_text, expected_x, desc in label_checks:
    # Find label in template
    label_word = None
    for w in words:
        if w['text'].strip() == lbl_text:
            label_word = w
            break
    if label_word:
        pdf_y = tpage.height - label_word['bottom']
        lbl_right = label_word['x1']
        gap = (expected_x - lbl_right) if expected_x else "N/A"
        print(f"  {lbl_text:18s} ends x={lbl_right:.0f}, pdfY={pdf_y:.0f}, value starts x={expected_x or '(below)'}, gap={gap}{'px' if isinstance(gap, float) else ''}")
