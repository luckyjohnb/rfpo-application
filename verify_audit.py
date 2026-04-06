#!/usr/bin/env python3
"""Quick verification of PDF field positioning after fixes"""
import sys, os
sys.path.insert(0, '/app')
os.chdir('/app')

from custom_admin import create_app
app = create_app()

with app.app_context():
    from models import db, RFPO, Consortium, Project, Vendor, VendorSite
    from pdf_generator import RFPOPDFGenerator
    import pdfplumber, io

    rfpo = RFPO.query.get(28)
    gen = RFPOPDFGenerator()
    consortium = Consortium.query.filter_by(consort_id=rfpo.consortium_id).first()
    project = Project.query.filter_by(project_id=rfpo.project_id).first()
    vendor = Vendor.query.get(rfpo.vendor_id) if rfpo.vendor_id else None
    vendor_site = VendorSite.query.get(rfpo.vendor_site_id) if rfpo.vendor_site_id else None

    pdf_bytes = gen.generate_po_pdf(rfpo, consortium, project, vendor, vendor_site)

    # Extract template-only text positions
    tpl_words = set()
    with pdfplumber.open('/app/static/po_files/po.pdf') as tpl:
        ph = float(tpl.pages[0].height)
        for w in tpl.pages[0].extract_words(x_tolerance=2, y_tolerance=2):
            tpl_words.add(w['text'])

    # Extract all text from generated proof
    with pdfplumber.open(io.BytesIO(pdf_bytes.read())) as pdf:
        page = pdf.pages[0]
        ph = float(page.height)
        words = page.extract_words(x_tolerance=2, y_tolerance=2)

        print("=" * 70)
        print("FIELD POSITION VERIFICATION (post-fix)")
        print("=" * 70)

        # Collect labels and values
        labels = {}
        values = {}
        for w in sorted(words, key=lambda x: (x['top'], x['x0'])):
            pdfY = round(ph - w['top'], 1)
            x0 = round(w['x0'], 1)
            x1 = round(w['x1'], 1)
            t = w['text']

            # Key template labels
            if t in ['NUMBER:', 'ORDER:', 'PROJECT:', 'DATE:', 'Number:']:
                labels[t] = {'x1': x1, 'pdfY': pdfY, 'x0': x0}
            # Composite labels
            if 'DATE OF ORDER:' in t or t == 'OF':
                pass  # handled below

        # Print ALL text with positions on page 1
        print("\nALL TEXT (sorted by Y desc, then X):")
        for w in sorted(words, key=lambda x: (x['top'], x['x0'])):
            pdfY = round(ph - w['top'], 1)
            x0 = round(w['x0'], 1)
            x1 = round(w['x1'], 1)
            t = w['text']
            # Only show fields in the areas we changed
            if pdfY > 700 or (640 < pdfY < 670) or (508 < pdfY < 515):
                marker = " [TPL]" if t in tpl_words else ""
                print(f"  x={x0:>6.1f}-{x1:<6.1f}  pdfY={pdfY:<7.1f}  '{t}'{marker}")

        print("\n" + "=" * 70)
        print("GAP ANALYSIS")
        print("=" * 70)

        # Find specific label-value pairs by proximity
        all_items = []
        for w in words:
            pdfY = round(ph - w['top'], 1)
            all_items.append({
                'text': w['text'],
                'x0': round(w['x0'], 1),
                'x1': round(w['x1'], 1),
                'pdfY': pdfY,
            })

        # Manual gap checks based on known label positions from template
        # Template labels from our audit:
        checks = [
            ("NUMBER:", 432, "RFPO-2026"),
            ("DATE OF ORDER:", 463, "04/03/2026"),
            ("PROJECT:", 293, "[2026"),
            ("DATE:", 277, "01/31/2027"),
            ("Agreement Number:", 348, "NONE"),
        ]

        for label_name, label_end_x, value_prefix in checks:
            # Find the value text
            for item in all_items:
                if item['text'].startswith(value_prefix):
                    gap = item['x0'] - label_end_x
                    print(f"  {label_name:25s} label_end={label_end_x}, value_x={item['x0']}, gap={gap:.1f}px  value='{item['text']}'")
                    break
            else:
                print(f"  {label_name:25s} VALUE NOT FOUND (prefix '{value_prefix}')")

        print("\nDone.")
