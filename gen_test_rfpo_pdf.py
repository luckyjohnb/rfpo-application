#!/usr/bin/env python3
"""Generate a test RFPO PDF locally using mock data matching RFPO-Proj3024-0146-2026-04-09-N01.

Usage: python gen_test_rfpo_pdf.py
Output: test_rfpo_snapshot.pdf
"""
import os
import sys
from datetime import datetime
from types import SimpleNamespace

# Need Flask app context for pdf_generator (uses current_app.root_path)
from flask import Flask
app = Flask(__name__)

with app.app_context():
    from pdf_generator import RFPOPDFGenerator

    # Mock data matching the screenshot
    rfpo = SimpleNamespace(
        rfpo_id="RFPO-Proj3024-0146-2026-04-09-N01",
        government_agreement_number="",
        requestor_id="ADMIN001",
        created_at=datetime(2026, 4, 9),
        invoice_address="27682 Oriole Court\nFlat Rock, MI 48134\nUnited States",
        shipto_name="",
        shipto_address="",
        delivery_date=None,
        vendor_id=1,
        vendor_site_id=None,
        consortium_id="USCAR",
        project_id="Proj3024-0146",
        subtotal=100.00,
        cost_share_amount=0,
        cost_share_description="",
        cost_share_type=None,
        total_amount=100.00,
        po_number=None,
        line_items=[
            SimpleNamespace(
                line_number=1,
                quantity=1,
                description="Line Item 1",
                unit_price=100.00,
                total_price=100.00,
                is_capital_equipment=False,
            )
        ],
    )

    # Add calculated methods
    rfpo.get_calculated_cost_share_amount = lambda: 0.0
    rfpo.get_calculated_total_amount = lambda: 100.0

    consortium = SimpleNamespace(
        consort_id="USCAR",
        abbrev="USCAR",
        name="United States Council for Automotive Research LLC",
        logo=None,  # Will use fallback USCAR logo
        terms_pdf=None,
        invoicing_address="United States Council for Automotive Research LLC\nAttn: Accounts Payable\n3000 Town Center Building, Suite 35\nSouthfield, MI 48075",
    )

    project = SimpleNamespace(
        project_id="Proj3024-0146",
        ref="Proj3024-0146",
        name="mytestproj",
    )

    vendor = SimpleNamespace(
        company_name="Splendor Analytics",
        contact_name="John Bouchard",
        contact_address="27682 Oriole Court",
        contact_city="Flat Rock",
        contact_state="MI",
        contact_zip="48134",
        contact_tel="734-775-6560",
    )

    requestor = SimpleNamespace(
        first_name="John",
        last_name="Bouchard",
        email="john@example.com",
    )
    requestor.get_display_name = lambda: "John Bouchard"

    gen = RFPOPDFGenerator(positioning_config=None)
    pdf_buffer = gen.generate_rfpo_pdf(rfpo, consortium, project, vendor, requestor=requestor)

    output_path = os.path.join(os.path.dirname(__file__), "test_rfpo_snapshot.pdf")
    with open(output_path, "wb") as f:
        f.write(pdf_buffer.getvalue())

    print(f"PDF generated: {output_path}")
    print(f"Size: {os.path.getsize(output_path)} bytes")
