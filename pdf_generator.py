#!/usr/bin/env python3
"""
PDF Generator for RFPO Purchase Orders
Combines template PDFs with dynamic RFPO data
"""

import os
import io
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from flask import current_app

logger = logging.getLogger(__name__)


class RFPOPDFGenerator:
    def __init__(self, positioning_config=None):
        self.static_path = os.path.join(current_app.root_path, "static", "po_files")
        self.logo_path = os.path.join(current_app.root_path, "uploads", "logos")
        self.positioning_config = positioning_config

        # Debug positioning config
        if positioning_config:
            logger.debug(
                "PDF Generator initialized WITH positioning config: %s", type(positioning_config)
            )
            try:
                pos_data = positioning_config.get_positioning_data()
                logger.debug("Positioning data keys: %s", list(pos_data.keys()))
                visible_fields = [
                    k for k, v in pos_data.items() if v.get("visible", True)
                ]
                hidden_fields = [
                    k for k, v in pos_data.items() if not v.get("visible", True)
                ]
                logger.debug("Visible fields (%d): %s", len(visible_fields), visible_fields)
                logger.debug("Hidden fields (%d): %s", len(hidden_fields), hidden_fields)

                # Show first few fields with details
                for i, (field_name, field_data) in enumerate(
                    list(pos_data.items())[:3]
                ):
                    logger.debug(
                        "Field %d %s: x=%s, y=%s, visible=%s",
                        i+1, field_name, field_data.get('x'), field_data.get('y'), field_data.get('visible')
                    )
            except Exception as e:
                logger.error("Error accessing positioning data: %s", e)
        else:
            logger.debug(
                "PDF Generator initialized WITHOUT positioning config - will use defaults"
            )

    def generate_rfpo_pdf(self, rfpo, consortium, project, vendor=None, vendor_site=None, requestor=None):
        """Generate RFPO (Request for Purchase Order) PDF — NOT a PO.

        This creates a standalone PDF matching the RFPO HTML preview layout
        with the "REQUEST FOR PURCHASE ORDER" header and disclaimer.
        Used for snapshots at submission time.
        """
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        self._draw_rfpo_page(c, rfpo, consortium, project, vendor, vendor_site, requestor, width, height)
        c.showPage()
        c.save()
        buffer.seek(0)

        # Append consortium terms pages (same as PO flow)
        if consortium:
            terms_file = self._get_consortium_terms_file(consortium.abbrev, consortium)
            if terms_file:
                if terms_file.startswith(".."):
                    terms_path = os.path.normpath(os.path.join(self.static_path, terms_file))
                else:
                    terms_path = os.path.join(self.static_path, terms_file)
                if os.path.exists(terms_path):
                    try:
                        output = PdfWriter()
                        main_reader = PdfReader(buffer)
                        for page in main_reader.pages:
                            output.add_page(page)
                        terms_reader = PdfReader(terms_path, strict=False)
                        for page in terms_reader.pages:
                            output.add_page(page)
                        combined = io.BytesIO()
                        output.write(combined)
                        combined.seek(0)
                        return combined
                    except Exception as e:
                        logger.warning("Could not append terms to RFPO PDF: %s", e)
                        buffer.seek(0)

        return buffer

    def _draw_rfpo_page(self, c, rfpo, consortium, project, vendor, vendor_site, requestor, width, height):
        """Draw the RFPO page layout matching the HTML preview template."""
        margin_left = 50
        margin_right = width - 50
        usable_width = margin_right - margin_left

        # --- HEADER ---
        # Consortium logo (right-aligned, matching HTML 300px img)
        logo_drawn = False
        if consortium and hasattr(consortium, "logo") and consortium.logo:
            logo_file = os.path.join("uploads", "logos", consortium.logo)
            if os.path.exists(logo_file):
                try:
                    c.drawImage(logo_file, margin_right - 200, height - 78,
                                width=190, height=50, preserveAspectRatio=True)
                    logo_drawn = True
                except Exception:
                    pass
        if not logo_drawn:
            fallback = os.path.join("static", "po_files", "uscar_logo.jpg")
            if os.path.exists(fallback):
                try:
                    c.drawImage(fallback, margin_right - 200, height - 78,
                                width=190, height=50, preserveAspectRatio=True)
                except Exception:
                    pass

        # Title — matching HTML: header1 = 13px bold, header2 = 22px bold
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin_left, height - 42, "REQUEST FOR PURCHASE ORDER")
        c.setFont("Helvetica-Bold", 20)
        c.drawString(margin_left, height - 66, rfpo.rfpo_id)
        c.setFont("Helvetica", 7.5)
        c.drawString(margin_left, height - 78, "THIS IS NOT A PO NUMBER - you cannot use this with any vendor.")

        # Horizontal rule (1pt solid, matching HTML .bar)
        y = height - 88
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(1)
        c.line(margin_left, y, margin_right, y)
        y -= 18

        # --- INFO TABLE ---
        # Column layout:  label (left) | value | right-label | right-value
        label_x = margin_left + 2
        value_x = margin_left + 155          # left-column values
        right_label_x = margin_right - 172   # right-column labels (left-aligned)
        right_value_x = margin_right - 100   # right-column values
        row_height = 14
        line_spacing = 11
        font_size = 9

        def draw_row(label, value, label2=None, value2=None):
            nonlocal y
            c.setFont("Helvetica-Bold", font_size)
            c.drawString(label_x, y, label)
            c.setFont("Helvetica", font_size)

            # Right column (always drawn at top of row)
            if label2:
                c.setFont("Helvetica-Bold", font_size)
                c.drawString(right_label_x, y, label2)
                c.setFont("Helvetica", font_size)
                if value2:
                    c.drawString(right_value_x, y, str(value2))

            # Left column value (handles multi-line)
            if value:
                lines = str(value).split("\n")
                for i, line in enumerate(lines):
                    c.drawString(value_x, y - (i * line_spacing), line.strip())
                line_count = max(1, len(lines))
                y -= row_height + (line_spacing * (line_count - 1))
            else:
                y -= row_height

        def draw_separator():
            """Draw a subtle row separator matching HTML table cell padding."""
            c.setStrokeColorRGB(0.85, 0.85, 0.85)
            c.setLineWidth(0.25)
            c.line(label_x, y + row_height - 3, margin_right - 2, y + row_height - 3)
            c.setStrokeColorRGB(0, 0, 0)

        # Government Agreement Number
        draw_row("Government Agreement Number:",
                 rfpo.government_agreement_number or "\u2014")
        draw_separator()

        # Project
        project_text = f"{project.name} ({project.ref})" if project else ""
        draw_row("Project:", project_text)
        draw_separator()

        # Requestor + Raised date
        requestor_name = ""
        requestor_email = ""
        if requestor:
            requestor_name = requestor.get_display_name()
            requestor_email = getattr(requestor, "email", "") or ""
        elif rfpo.requestor_id:
            try:
                from models import User
                req_user = User.query.filter_by(record_id=rfpo.requestor_id).first()
                if req_user:
                    requestor_name = req_user.get_display_name()
                    requestor_email = req_user.email or ""
            except Exception:
                requestor_name = rfpo.requestor_id
        raised_date = rfpo.created_at.strftime("%B %d, %Y") if rfpo.created_at else ""
        # Draw requestor name + email (multi-line left value)
        req_display = requestor_name
        if requestor_email:
            req_display += f"\nEmail: {requestor_email}"
        draw_row("Requestor:", req_display, "Raised:", raised_date)
        draw_separator()

        # Invoice to
        invoice_addr = rfpo.invoice_address or ""
        if not invoice_addr and consortium and hasattr(consortium, "invoicing_address") and consortium.invoicing_address:
            invoice_addr = consortium.invoicing_address
        draw_row("Invoice to:", invoice_addr)
        draw_separator()

        # Ship to name + PO Expiration Date
        expiry_date = rfpo.delivery_date.strftime("%B %d, %Y") if rfpo.delivery_date else ""
        draw_row("Ship to name:", rfpo.shipto_name or "\u2014",
                 "PO Expiration Date:", expiry_date or "\u2014")
        draw_separator()

        # Ship to address
        draw_row("Ship to address:", rfpo.shipto_address or "\u2014")
        draw_separator()

        # Vendor block
        vendor_name = ""
        vendor_addr = ""
        vendor_contact = ""
        vendor_tel = ""
        if vendor:
            vendor_name = vendor.company_name or ""
            site = vendor_site or vendor
            vendor_addr = getattr(site, "contact_address", "") or ""
            vendor_contact = getattr(site, "contact_name", "") or ""
            vendor_tel = getattr(site, "contact_tel", "") or ""
        draw_row("Vendor:", vendor_name, "Contact:", vendor_contact)
        if vendor_addr:
            # Vendor address continuation + Contact Tel on same row
            c.setFont("Helvetica", font_size)
            addr_lines_list = vendor_addr.split("\n")
            for i, line in enumerate(addr_lines_list):
                c.drawString(value_x, y - (i * line_spacing), line.strip())
            addr_line_count = len(addr_lines_list)
            if vendor_tel:
                c.setFont("Helvetica-Bold", font_size)
                c.drawString(right_label_x, y, "Contact Tel:")
                c.setFont("Helvetica", font_size)
                c.drawString(right_value_x, y, vendor_tel)
            y -= row_height + (line_spacing * (addr_line_count - 1))
        elif vendor_tel:
            draw_row("", "", "Contact Tel:", vendor_tel)

        y -= 16  # spacing before line items (matching HTML &#160;<br>&#160;)

        # --- LINE ITEMS TABLE ---
        col_num_x = margin_left
        col_qty_x = margin_left + 30
        col_desc_x = margin_left + 70
        col_unit_x = margin_right - 110
        col_total_x = margin_right

        c.setStrokeColorRGB(0, 0, 0)

        # Header row — 2px solid border (matching HTML th { border: 2px solid #000 })
        c.setLineWidth(2)
        c.setFont("Helvetica-Bold", 8.5)
        hdr_h = 18  # header cell height
        hdr_top = y + 10
        hdr_bottom = hdr_top - hdr_h
        text_y = hdr_bottom + 5  # text baseline inside header
        c.rect(margin_left, hdr_bottom, usable_width, hdr_h)
        # Vertical dividers inside header
        col_dividers = [col_qty_x - 2, col_desc_x - 2, col_unit_x - 2, col_total_x - 62]
        for vx in col_dividers:
            c.line(vx, hdr_top, vx, hdr_bottom)
        c.drawString(col_num_x + 4, text_y, "#")
        c.drawString(col_qty_x + 2, text_y, "Qty")
        c.drawString(col_desc_x + 2, text_y, "Description of supplies or services")
        c.drawRightString(col_total_x - 64, text_y, "Unit Price")
        c.drawRightString(col_total_x - 4, text_y, "Total Price")

        # Data rows — start BELOW the header with clear gap
        y = hdr_bottom  # cursor is now the top of the data area
        c.setFont("Helvetica", 8.5)
        items = sorted(rfpo.line_items, key=lambda x: x.line_number) if rfpo.line_items else []
        for idx, item in enumerate(items):
            if y < 130:  # leave room for totals
                break
            desc = item.description or ""
            if item.is_capital_equipment:
                desc += " [Capital Equipment]"
            desc_lines = self._wrap_text(desc, 48)
            row_lines = max(1, len(desc_lines))
            cell_h = 11 * row_lines + 7  # padding top(4) + bottom(3) + text

            row_top = y
            row_bottom = y - cell_h
            text_baseline = row_top - 12  # text offset from top of cell

            # Cell borders — 1px solid #ccc (matching HTML td { border: 1px solid #ccc })
            c.setStrokeColorRGB(0.8, 0.8, 0.8)
            c.setLineWidth(0.5)
            c.rect(margin_left, row_bottom, usable_width, cell_h)
            for vx in col_dividers:
                c.line(vx, row_top, vx, row_bottom)
            c.setStrokeColorRGB(0, 0, 0)

            # Cell text
            c.drawString(col_num_x + 4, text_baseline, str(item.line_number))
            c.drawString(col_qty_x + 2, text_baseline, str(item.quantity))
            for i, dl in enumerate(desc_lines):
                c.drawString(col_desc_x + 2, text_baseline - (i * 11), dl)
            c.drawRightString(col_total_x - 64, text_baseline, f"${item.unit_price:,.2f}")
            c.drawRightString(col_total_x - 4, text_baseline, f"${item.total_price:,.2f}")

            y = row_bottom  # next row starts at bottom of this row

        # --- TOTALS ---
        y -= 8

        # Gross purchase order
        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(col_total_x - 64, y, "Gross purchase order:")
        c.setFont("Helvetica", 9)
        subtotal = rfpo.subtotal if rfpo.subtotal else 0
        c.drawRightString(col_total_x - 4, y, f"${subtotal:,.2f}")
        y -= 16

        # Cost share
        cost_share = 0
        try:
            cost_share = rfpo.get_calculated_cost_share_amount()
        except Exception:
            cost_share = rfpo.cost_share_amount or 0
        c.setFont("Helvetica-Bold", 9)
        label = "Less supplier cost share:"
        if rfpo.cost_share_description:
            label += f"  ({rfpo.cost_share_description})"
        c.drawRightString(col_total_x - 64, y, label)
        c.setFont("Helvetica", 9)
        c.drawRightString(col_total_x - 4, y, f"(${cost_share:,.2f})")
        y -= 16

        # Net total — bold with 2px border box (matching HTML td.bold)
        c.setFont("Helvetica-Bold", 10)
        c.drawRightString(col_total_x - 64, y, "Net purchase not to exceed:")
        total = 0
        try:
            total = rfpo.get_calculated_total_amount()
        except Exception:
            total = rfpo.total_amount or 0
        total_text = f"${total:,.2f}"
        # Draw bordered box around net total value (matching HTML td.bold { border: 2px solid #000 })
        tw = c.stringWidth(total_text, "Helvetica-Bold", 10)
        box_x = col_total_x - 4 - tw - 4
        box_y = y - 4
        box_w = tw + 8
        box_h = 16
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(2)
        c.rect(box_x, box_y, box_w, box_h)
        c.drawRightString(col_total_x - 4, y, total_text)

    def generate_po_pdf(self, rfpo, consortium, project, vendor=None, vendor_site=None):
        """Generate complete PO PDF with dynamic data"""
        try:
            # Create a temporary PDF with our data overlay
            data_pdf = self._create_data_overlay(
                rfpo, consortium, project, vendor, vendor_site
            )

            # Combine with template PDFs
            final_pdf = self._combine_with_templates(
                data_pdf, consortium.abbrev, consortium
            )

            return final_pdf

        except Exception as e:
            logger.error("Error generating PDF: %s", e)
            raise

    def _create_data_overlay(
        self, rfpo, consortium, project, vendor=None, vendor_site=None
    ):
        """Create PDF overlay with RFPO data"""
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Store RFPO ID on canvas for continuation pages
        c._rfpo_id = rfpo.rfpo_id

        # Page 1: Main PO Information including line items (like legacy template)
        line_items_overflow = self._draw_page1_data(
            c, rfpo, consortium, project, vendor, vendor_site, width, height
        )
        c.showPage()

        # Page 2+: Additional line items if they don't fit on page 1
        if line_items_overflow:
            self._draw_additional_line_items_pages(
                c, line_items_overflow, width, height
            )

        c.save()
        buffer.seek(0)
        return buffer

    def _get_field_position(self, field_name, default_x=0, default_y=0):
        """Get positioning data for a field, with fallback to defaults"""
        if not self.positioning_config:
            return default_x, default_y, 9, "normal"  # default font_size and weight

        positioning_data = self.positioning_config.get_positioning_data()
        field_data = positioning_data.get(field_name, {})

        # Special handling for dynamic fields - always use defaults if not configured
        dynamic_field_prefixes = [
            "line_item_",
            "vendor_small_business",
            "vendor_university",
            "vendor_nonprofit",
        ]
        is_dynamic_field = any(
            field_name.startswith(prefix) or field_name == prefix
            for prefix in dynamic_field_prefixes
        )

        if is_dynamic_field and not field_data:
            logger.debug(
                "Dynamic field %s using defaults (not in positioning config)", field_name
            )
            return (
                default_x,
                default_y,
                8,
                "normal",
            )  # Use default coordinates for dynamic fields

        # For other fields, if not in positioning data, don't draw it (field was cleared/removed)
        if not field_data:
            logger.debug("Field %s not in positioning data - skipping (cleared)", field_name)
            return None, None, None, None

        # If field is explicitly hidden, don't draw it
        if not field_data.get("visible", True):
            logger.debug("Field %s is hidden - skipping", field_name)
            return None, None, None, None

        x = field_data.get("x", default_x)
        y = field_data.get("y", default_y)
        font_size = field_data.get("font_size", 9)
        font_weight = field_data.get("font_weight", "normal")

        # FIXED: Frontend already converts screen coordinates to PDF coordinates
        # The stored coordinates are already in PDF coordinate space (origin at bottom-left)
        # Apply preview offset adjustment to align with designer positioning
        if self.positioning_config:
            pdf_width = 612
            pdf_height = 792

            logger.debug("Canvas is fixed at PDF dimensions: %dx%d", pdf_width, pdf_height)

            # Coordinates are already in PDF space - apply preview offset for alignment
            preview_offset = (
                -15
            )  # Offset to align preview with designer positioning (was 25, now -15 for 40px decrease)
            pdf_x = x
            pdf_y = y + preview_offset  # Adjust Y coordinate for preview alignment

            logger.debug("Using stored PDF coordinates for %s:", field_name)
            logger.debug(
                "   Stored PDF coords: (%s, %s) -> Preview adjusted: (%.1f, %.1f)", x, y, pdf_x, pdf_y
            )
            logger.debug("   Applied preview offset: +%dpx Y", preview_offset)

            # Ensure coordinates are within PDF bounds
            pdf_x = max(0, min(pdf_width, pdf_x))
            pdf_y = max(0, min(pdf_height, pdf_y))

            if pdf_x != x or pdf_y != (y + preview_offset):
                logger.debug(
                    "Clamped %s coordinates to bounds: (%.1f, %.1f)", field_name, pdf_x, pdf_y
                )

            return pdf_x, pdf_y, font_size, font_weight

        return x, y, font_size, font_weight

    def _draw_text_with_positioning(
        self, canvas, field_name, text, default_x, default_y, right_align=False, font_size_override=None
    ):
        """Draw text using positioning configuration - supports multi-line text"""
        x, y, font_size, font_weight = self._get_field_position(
            field_name, default_x, default_y
        )

        if x is None:  # Field is hidden
            logger.debug("Field %s is hidden, skipping", field_name)
            return

        # Allow caller to override font size (e.g. for auto-shrink logic)
        if font_size_override is not None:
            font_size = font_size_override

        logger.debug(
            "Drawing %s: '%s' at (%s, %s) with font %spt %s", field_name, text, x, y, font_size, font_weight
        )

        # Validate coordinates are within PDF bounds
        if x < 0 or x > 612 or y < 0 or y > 792:
            logger.warning(
                "%s coordinates (%s, %s) are outside PDF bounds (612x792)", field_name, x, y
            )

        # Set font based on weight
        if font_weight == "bold":
            canvas.setFont("Helvetica-Bold", font_size)
        else:
            canvas.setFont("Helvetica", font_size)

        try:
            # Handle multi-line text by splitting on newlines
            text_lines = str(text).split("\n")
            line_height = font_size + 2  # Add small spacing between lines

            for i, line in enumerate(text_lines):
                line_y = y - (i * line_height)  # Move down for each line
                if right_align:
                    canvas.drawRightString(x, line_y, line.strip())
                else:
                    canvas.drawString(x, line_y, line.strip())

            logger.debug("Successfully drew %s (%d lines)", field_name, len(text_lines))
        except Exception as e:
            logger.error("Error drawing %s: %s", field_name, e)

    def _draw_logo_with_positioning(
        self, canvas, field_name, logo_filename, default_x, default_y
    ):
        """Draw logo image using positioning configuration"""
        x, y, _, _ = self._get_field_position(field_name, default_x, default_y)

        if x is None:  # Field is hidden
            logger.debug("Logo field %s is hidden, skipping", field_name)
            return

        logger.debug("Drawing logo %s: '%s' at (%s, %s)", field_name, logo_filename, x, y)

        try:
            import os
            from reportlab.lib.utils import ImageReader
            from PIL import Image

            # Get logo file path
            logo_path = os.path.join("uploads", "logos", logo_filename)

            # Check if logo file exists
            if not os.path.exists(logo_path):
                logger.warning("Logo file not found: %s", logo_path)
                # Draw placeholder text instead
                canvas.setFont("Helvetica", 8)
                canvas.drawString(x, y, f"[LOGO: {logo_filename}]")
                return

            # Get logo dimensions from positioning config or use defaults
            positioning_data = (
                self.positioning_config.get_positioning_data()
                if self.positioning_config
                else {}
            )
            field_config = positioning_data.get(field_name, {})
            logo_width = field_config.get("width", 80)
            logo_height = field_config.get("height", 40)

            # Apply logo-specific offset to align with designer positioning
            # Logo needs to move UP significantly in preview to match designer top positioning
            logo_preview_offset = (
                -60
            )  # Move logo up in preview by 60px (was -80, corrected by +20)
            pdf_y = y + logo_preview_offset

            # Validate coordinates are within PDF bounds
            if x < 0 or x > 612 or pdf_y < 0 or pdf_y > 792:
                logger.warning(
                    "%s coordinates (%s, %s) are outside PDF bounds (612x792)", field_name, x, pdf_y
                )

            # Draw the logo image
            canvas.drawImage(
                logo_path,
                x,
                pdf_y,
                width=logo_width,
                height=logo_height,
                preserveAspectRatio=True,
            )
            logger.debug("Successfully drew logo %s", field_name)

        except Exception as e:
            logger.error("Error drawing logo %s: %s", field_name, e)
            # Draw placeholder text as fallback
            try:
                canvas.setFont("Helvetica", 8)
                canvas.drawString(x, y, f"[LOGO ERROR: {logo_filename}]")
            except Exception:
                pass

    def _draw_fallback_logo(self, canvas, default_x, default_y):
        """Draw the default USCAR logo from static files when no consortium logo is uploaded"""
        import os

        logo_path = os.path.join("static", "po_files", "uscar_logo.jpg")
        if not os.path.exists(logo_path):
            logger.warning("Default logo not found: %s", logo_path)
            return

        try:
            x, y, _, _ = self._get_field_position("consortium_logo", default_x, default_y)
            if x is None:
                return

            # Only apply preview offset when positioning config exists (designer coordinates)
            # For defaults, place logo directly above the title strip (y=712 top of strip)
            if self.positioning_config:
                logo_preview_offset = -60
                pdf_y = y + logo_preview_offset
            else:
                pdf_y = 716  # Just above PURCHASE ORDER title strip (top at y=712)

            canvas.drawImage(
                logo_path,
                x,
                pdf_y,
                width=80,
                height=40,
                preserveAspectRatio=True,
            )
            logger.debug("Drew fallback USCAR logo at (%s, %s)", x, pdf_y)
        except Exception as e:
            logger.error("Error drawing fallback logo: %s", e)

    def _draw_page1_data(
        self, canvas, rfpo, consortium, project, vendor, vendor_site, width, height
    ):
        """Draw data on page 1 (main PO info) - using positioning configuration or legacy defaults

        Default coordinates are mapped to the po.pdf template layout:
        - Template is 612x792 pts (US Letter)
        - Coordinates use PDF convention (origin at bottom-left)
        - Data is placed BELOW each template label to fill the form fields
        """

        # === CONSORTIUM LOGO ===
        if consortium and hasattr(consortium, "logo") and consortium.logo:
            self._draw_logo_with_positioning(
                canvas, "consortium_logo", consortium.logo, 50, 750
            )
        else:
            # Fallback: draw default USCAR logo from static files
            self._draw_fallback_logo(canvas, 50, 750)

        # === TOP SECTION ===
        # PO NUMBER — template "NUMBER:" label at x=394, baseline y=764; value to right
        po_display = rfpo.po_number if rfpo.po_number else rfpo.rfpo_id
        # Auto-shrink font for long PO numbers to fit within box (x=445 to x=588)
        max_po_width = 143  # 588 - 445
        po_font_size = 9
        from reportlab.pdfbase.pdfmetrics import stringWidth
        while po_font_size > 5 and stringWidth(po_display, "Helvetica", po_font_size) > max_po_width:
            po_font_size -= 0.5
        self._draw_text_with_positioning(canvas, "po_number", po_display, 445, 764, font_size_override=po_font_size)

        # DATE OF ORDER — template label at x=394, baseline y=728; value to right of label
        # Label ends at x≈463; start value at x=476 for ~13px gap (matches NUMBER field)
        self._draw_text_with_positioning(
            canvas, "po_date", datetime.now(ZoneInfo("America/New_York")).strftime("%m/%d/%Y"), 476, 728
        )

        # === VENDOR SECTION (Box: 46,535 to 244,679 — label "VENDOR:" at y=669) ===
        if vendor:
            contact_name = None
            contact_address = None
            contact_city = None
            contact_state = None
            contact_zip = None
            contact_tel = None

            if vendor_site:
                contact_name = vendor_site.contact_name
                contact_address = vendor_site.contact_address
                contact_city = vendor_site.contact_city
                contact_state = vendor_site.contact_state
                contact_zip = vendor_site.contact_zip
                contact_tel = vendor_site.contact_tel
            else:
                contact_name = vendor.contact_name
                contact_address = vendor.contact_address
                contact_city = vendor.contact_city
                contact_state = vendor.contact_state
                contact_zip = vendor.contact_zip
                contact_tel = vendor.contact_tel

            # Vendor company name — below "VENDOR:" label
            self._draw_text_with_positioning(
                canvas, "vendor_company", vendor.company_name, 52, 656
            )

            if contact_name:
                self._draw_text_with_positioning(
                    canvas, "vendor_contact", contact_name, 52, 643
                )

            # Address
            vendor_addr_y = 630
            if contact_address:
                self._draw_text_with_positioning(
                    canvas, "vendor_address", contact_address, 52, vendor_addr_y
                )
            else:
                address_parts = []
                city_state_zip = []
                if contact_city:
                    city_state_zip.append(contact_city)
                if contact_state:
                    city_state_zip.append(contact_state)
                if contact_zip:
                    city_state_zip.append(contact_zip)

                if city_state_zip:
                    address_parts.append(", ".join(city_state_zip))

                if address_parts:
                    self._draw_text_with_positioning(
                        canvas, "vendor_address", "\n".join(address_parts), 52, vendor_addr_y
                    )

            if contact_tel:
                # Position phone below address dynamically
                addr_text = contact_address or ", ".join(filter(None, [contact_city, contact_state, contact_zip]))
                addr_lines = len(addr_text.split("\n")) if addr_text else 0
                phone_y = vendor_addr_y - (addr_lines * 13) - 13
                self._draw_text_with_positioning(
                    canvas, "vendor_phone", f"Tel: {contact_tel}", 52, phone_y
                )
        else:
            self._draw_text_with_positioning(
                canvas, "vendor_company", "[No Vendor Selected]", 52, 656
            )

        # === SHIP TO SECTION (Box: 420,113 to 590,257 — label "SHIP TO:" at x=424, y=667) ===
        if rfpo.shipto_name:
            self._draw_text_with_positioning(
                canvas, "ship_to_name", rfpo.shipto_name, 424, 654
            )

        if rfpo.shipto_address:
            self._draw_text_with_positioning(
                canvas, "ship_to_address", rfpo.shipto_address, 424, 641
            )

        # === MIDDLE FORM FIELDS ===
        # PROJECT — label "PROJECT:" at x=253, y=667; box (250,647)-(415,679) — 2 rows, 32pt tall
        # Value placed right after label; wraps to second line if needed
        from reportlab.pdfbase.pdfmetrics import stringWidth
        project_text = f"[{project.ref}] {project.name}"
        project_value_x = 305  # 12px gap after "PROJECT:" label ends (~x=293)
        project_box_right = 413  # box right edge with small margin
        project_avail = project_box_right - project_value_x  # ~108pt available
        project_font_size = 8

        text_width = stringWidth(project_text, "Helvetica", project_font_size)
        if text_width <= project_avail:
            # Fits on one line next to label
            self._draw_text_with_positioning(
                canvas, "project_info", project_text, project_value_x, 667, font_size_override=project_font_size
            )
        else:
            # Wrap to 2 lines: line 1 next to label, line 2 below at full box width
            line2_x = 253  # start at box left edge for second line
            line2_avail = project_box_right - line2_x  # full width ~160pt
            # Split text to fit line 1 width
            words = project_text.split()
            line1 = ""
            line2_words = []
            for word in words:
                test = (line1 + " " + word).strip() if line1 else word
                if stringWidth(test, "Helvetica", project_font_size) <= project_avail:
                    line1 = test
                else:
                    line2_words.append(word)
            line2 = " ".join(line2_words)
            # Truncate line2 if still too long
            while line2 and stringWidth(line2, "Helvetica", project_font_size) > line2_avail:
                line2 = line2[:-4] + "..."
            self._draw_text_with_positioning(
                canvas, "project_info", line1, project_value_x, 667, font_size_override=project_font_size
            )
            if line2:
                self._draw_text_with_positioning(
                    canvas, "project_info_line2", line2, line2_x, 656, font_size_override=project_font_size
                )

        # DATE — template label "DATE:" at x=253, y=639; box (250,629)-(415,647)
        # Label ends at x≈277; start value at x=290 for ~13px gap
        if rfpo.delivery_date:
            self._draw_text_with_positioning(
                canvas,
                "delivery_date",
                rfpo.delivery_date.strftime("%m/%d/%Y"),
                290,
                639,
            )

        # PAYMENT, DELIVERY DETAIL fields hidden from create flow (Issues #5, #6)
        # These fields are no longer collected from users and omitted from PDF output

        # === GOVERNMENT AGREEMENT (template label "under Agreement Number:" ends ~x=348, y=511) ===
        # Start value at x=355 for ~7px gap; keeps within middle column (right edge 415)
        if rfpo.government_agreement_number:
            self._draw_text_with_positioning(
                canvas,
                "government_agreement",
                rfpo.government_agreement_number,
                355,
                511,
            )

        # === LINE ITEMS SECTION ===
        # Template table header row is at y=497-506 (already in template)
        # Line items area: box (46,176)-(590,491)
        overflow_items = []
        if rfpo.line_items:
            # Start just below the template's header row
            line_height = 12
            current_y = 480

            canvas.setFont("Helvetica", 8)

            for i, item in enumerate(rfpo.line_items):
                desc_lines = self._wrap_text(item.description, 45)
                lines_needed = 1 if len(desc_lines) <= 1 else 2
                space_needed = line_height * lines_needed

                # Leave room for totals section (y=176 is box bottom)
                if current_y - space_needed < 220:
                    overflow_items = rfpo.line_items[i:]
                    break

                # Quantity — column (46,176)-(85,491)
                self._draw_text_with_positioning(
                    canvas, f"line_item_{i}_quantity", str(item.quantity), 55, current_y
                )

                # Description — column (91,176)-(424,491)
                desc_text = desc_lines[0] if desc_lines else ""
                if item.is_capital_equipment:
                    desc_text += " [CAPITAL EQUIP.]"

                self._draw_text_with_positioning(
                    canvas, f"line_item_{i}_description", desc_text, 95, current_y
                )

                # Unit price — column (431,176)-(510,491), right-aligned
                self._draw_text_with_positioning(
                    canvas,
                    f"line_item_{i}_unit_price",
                    f"${item.unit_price:,.2f}",
                    505,
                    current_y,
                    right_align=True,
                )

                # Total price — column (516,176)-(590,491), right-aligned
                self._draw_text_with_positioning(
                    canvas,
                    f"line_item_{i}_total_price",
                    f"${item.total_price:,.2f}",
                    585,
                    current_y,
                    right_align=True,
                )

                current_y -= line_height

                # If description is too long, continue on next line
                if len(desc_lines) > 1:
                    self._draw_text_with_positioning(
                        canvas,
                        f"line_item_{i}_description_cont",
                        (
                            desc_lines[1][:45] + "..."
                            if len(desc_lines[1]) > 45
                            else desc_lines[1]
                        ),
                        95,
                        current_y,
                    )
                    current_y -= line_height

            # === TOTALS SECTION ===
            # Always anchored at the bottom of the line items box (y=176)
            # This keeps totals in a consistent position regardless of item count
            # UNIT PRICE col right edge = 505, TOTAL PRICE col right edge = 585
            # Price column boxes bottom at y=176; place totals just above that
            totals_y = 192  # baseline for TOTAL row, ~16pt above box bottom
            subtotals_y = totals_y + 13  # SUBTOTAL row above TOTAL

            # If there's a cost share, shift everything up to make room
            if rfpo.cost_share_amount and rfpo.cost_share_amount > 0:
                totals_y = 185
                cost_share_y = totals_y + 13
                subtotals_y = cost_share_y + 13

            # Horizontal rule above subtotal
            canvas.line(431, subtotals_y + 10, 585, subtotals_y + 10)

            # Subtotal — label right-aligned in unit price col, value in total price col
            canvas.setFont("Helvetica", 8)
            self._draw_text_with_positioning(
                canvas, "subtotal_label", "SUBTOTAL:", 505, subtotals_y, right_align=True
            )
            self._draw_text_with_positioning(
                canvas, "subtotal", f"${rfpo.subtotal:,.2f}", 585, subtotals_y, right_align=True
            )

            if rfpo.cost_share_amount and rfpo.cost_share_amount > 0:
                self._draw_text_with_positioning(
                    canvas,
                    "vendor_cost_share_label",
                    "VENDOR COST SHARE:",
                    505,
                    cost_share_y,
                    right_align=True,
                )
                self._draw_text_with_positioning(
                    canvas,
                    "vendor_cost_share_amount",
                    f"-${rfpo.cost_share_amount:,.2f}",
                    585,
                    cost_share_y,
                    right_align=True,
                )

            # Horizontal rule above total
            canvas.line(431, totals_y + 10, 585, totals_y + 10)

            # Total — bold, same column alignment
            canvas.setFont("Helvetica-Bold", 9)
            self._draw_text_with_positioning(
                canvas, "total_label", "TOTAL:", 505, totals_y, right_align=True
            )
            self._draw_text_with_positioning(
                canvas, "total", f"${rfpo.total_amount:,.2f}", 585, totals_y, right_align=True
            )

        # === REQUESTOR SECTION (Box: 46,42 to 244,168 — label "REQUESTOR:" at y=156) ===
        # Look up requestor's name from User model by record_id
        requestor_name = rfpo.requestor_id or "ADMIN001"
        try:
            from models import User
            requestor_user = User.query.filter_by(record_id=rfpo.requestor_id).first()
            if requestor_user:
                requestor_name = requestor_user.get_display_name()
        except Exception as e:
            logger.warning("Could not look up requestor name: %s", e)
        self._draw_text_with_positioning(
            canvas,
            "requestor_info",
            requestor_name,
            52,
            145,
        )

        # === INVOICE TO SECTION (Box: 249,42 to 447,168 — label "INVOICE TO:" at y=156) ===
        if rfpo.invoice_address:
            self._draw_text_with_positioning(
                canvas, "invoice_address", rfpo.invoice_address, 255, 145
            )

        # === APPROVED SECTION (Box: 452,42 to 589,168 — label "APPROVED:" at y=156) ===
        # Find the most recent approval action for this RFPO
        try:
            from models import RFPOApprovalInstance, RFPOApprovalAction
            instance = RFPOApprovalInstance.query.filter_by(rfpo_id=rfpo.id).first()
            if instance:
                approval_action = (
                    RFPOApprovalAction.query
                    .filter_by(instance_id=instance.id, status='approved')
                    .order_by(RFPOApprovalAction.created_at.desc())
                    .first()
                )
                if approval_action and approval_action.approver_name:
                    self._draw_text_with_positioning(
                        canvas, "approved_by", approval_action.approver_name, 455, 145
                    )
        except Exception as e:
            logger.warning("Could not look up approver name: %s", e)

        # Return any line items that didn't fit on page 1
        return overflow_items

    def _draw_additional_line_items_pages(self, canvas, overflow_items, width, height):
        """Draw additional line items on page 2+ using po_page2.pdf template"""
        items_per_page = 25  # Approximate number of items that fit on page 2
        line_height = 12
        page_start_y = 720  # Start near top of page for continuation

        items_remaining = list(overflow_items)

        while items_remaining:
            # Items for this page
            current_page_items = items_remaining[:items_per_page]
            items_remaining = items_remaining[items_per_page:]

            # Draw items on current page
            current_y = page_start_y
            canvas.setFont("Helvetica", 8)

            # Add continuation header
            canvas.setFont("Helvetica-Bold", 10)
            canvas.drawString(
                60,
                current_y,
                f"Purchase Order {getattr(canvas, '_rfpo_id', '')} - Continuation",
            )
            current_y -= 30

            # Table headers
            canvas.setFont("Helvetica-Bold", 8)
            canvas.drawString(60, current_y, "QTY")
            canvas.drawString(120, current_y, "DESCRIPTION OF SUPPLIES OR SERVICES")
            canvas.drawString(450, current_y, "UNIT PRICE")
            canvas.drawString(500, current_y, "TOTAL PRICE")

            # Draw line under headers
            canvas.line(60, current_y - 3, 530, current_y - 3)
            current_y -= 20

            canvas.setFont("Helvetica", 8)

            for item in current_page_items:
                if current_y < 50:  # Stop if getting too close to bottom
                    break

                # Quantity
                canvas.drawString(60, current_y, str(item.quantity))

                # Description (wrapped to fit column width)
                desc_lines = self._wrap_text(item.description, 45)
                desc_text = desc_lines[0] if desc_lines else ""

                # Add capital equipment indicator if applicable
                if item.is_capital_equipment:
                    desc_text += " [CAPITAL EQUIP.]"

                canvas.drawString(120, current_y, desc_text)

                # Unit price (right-aligned)
                canvas.drawRightString(490, current_y, f"${item.unit_price:,.2f}")

                # Total price (right-aligned)
                canvas.drawRightString(530, current_y, f"${item.total_price:,.2f}")

                current_y -= line_height

                # If description is too long, continue on next line
                if len(desc_lines) > 1 and current_y > 60:
                    continuation_text = (
                        desc_lines[1][:45] + "..."
                        if len(desc_lines[1]) > 45
                        else desc_lines[1]
                    )
                    canvas.drawString(120, current_y, continuation_text)
                    current_y -= line_height

            # Start new page if there are more items
            if items_remaining:
                canvas.showPage()

    def _combine_with_templates(self, data_pdf, consortium_abbrev, consortium=None):
        """Combine data overlay with template PDFs following legacy pattern"""
        output = PdfWriter()

        # Load data PDF
        data_reader = PdfReader(data_pdf)

        # Page 1: Combine with po.pdf template (main PO content)
        template_path = os.path.join(self.static_path, "po.pdf")
        if os.path.exists(template_path):
            template_reader = PdfReader(template_path)
            if len(template_reader.pages) > 0 and len(data_reader.pages) > 0:
                # FIXED: Create a copy of the template page before merging
                template_page = template_reader.pages[0]
                data_page = data_reader.pages[0]

                # Merge data overlay on top of template
                template_page.merge_page(data_page)
                output.add_page(template_page)

                logger.debug("Merged page 1: template + data overlay")
            elif len(data_reader.pages) > 0:
                # Fallback: just use data page if no template
                output.add_page(data_reader.pages[0])
                logger.debug("Using data page only (no template)")
            else:
                logger.warning("No data pages to merge")

        # Pages 2+: Combine additional data pages with po_page2.pdf template (for overflow line items)
        page2_template_path = os.path.join(self.static_path, "po_page2.pdf")
        if len(data_reader.pages) > 1 and os.path.exists(page2_template_path):
            page2_template_reader = PdfReader(page2_template_path)

            for i in range(1, len(data_reader.pages)):
                if len(page2_template_reader.pages) > 0:
                    # Use po_page2.pdf template for continuation pages
                    page = page2_template_reader.pages[0]
                    page.merge_page(data_reader.pages[i])
                    output.add_page(page)
                else:
                    # Fallback: just add the data page without template
                    output.add_page(data_reader.pages[i])

        # Add consortium-specific terms at the end using byte-level concatenation
        terms_file = self._get_consortium_terms_file(consortium_abbrev, consortium)
        if terms_file:
            # Handle both static and uploaded terms files
            if terms_file.startswith(".."):
                # This is a relative path to uploads/terms/
                terms_path = os.path.normpath(
                    os.path.join(self.static_path, terms_file)
                )
            else:
                # This is a static file in po_files/
                terms_path = os.path.join(self.static_path, terms_file)
            if os.path.exists(terms_path):
                try:
                    # NEW APPROACH: Use byte-level PDF concatenation to avoid merge conflicts
                    # This preserves the original PDF structure completely

                    # First, save our current output (main pages)
                    main_buffer = io.BytesIO()
                    output.write(main_buffer)
                    main_buffer.seek(0)

                    # Create a new output writer for the final combined PDF
                    final_output = PdfWriter()

                    # Add all main pages first
                    main_reader = PdfReader(main_buffer)
                    logger.debug(
                        "Adding %d main pages to final output", len(main_reader.pages)
                    )
                    for i, page in enumerate(main_reader.pages):
                        final_output.add_page(page)
                        logger.debug("Added main page %d", i+1)

                    # Now add terms pages using fresh reader (no prior merge conflicts)
                    terms_reader = PdfReader(terms_path, strict=False)
                    logger.debug(
                        "Adding %d terms pages from %s", len(terms_reader.pages), terms_file
                    )

                    for i, page in enumerate(terms_reader.pages):
                        try:
                            # Since this is a fresh reader with no prior merges, it should work
                            final_output.add_page(page)
                            logger.debug("Added terms page %d (fresh reader)", i+1)
                        except Exception as add_error:
                            logger.error("Failed to add terms page %d: %s", i+1, add_error)

                            # Fallback: Create a text placeholder
                            try:
                                fallback_buffer = io.BytesIO()
                                c = canvas.Canvas(fallback_buffer, pagesize=letter)
                                c.setFont("Helvetica", 12)
                                c.drawString(
                                    50, 750, f"Terms and Conditions - Page {i+1}"
                                )
                                c.drawString(
                                    50,
                                    720,
                                    f"[Original page from {terms_file} could not be displayed]",
                                )
                                c.drawString(
                                    50,
                                    700,
                                    f"Please refer to the original document for complete terms.",
                                )
                                c.save()
                                fallback_buffer.seek(0)

                                fallback_reader = PdfReader(fallback_buffer)
                                final_output.add_page(fallback_reader.pages[0])
                                logger.debug("Added fallback for terms page %d", i+1)

                            except Exception as fallback_error:
                                logger.error(
                                    "Fallback failed for terms page %d: %s", i+1, fallback_error
                                )

                    # Replace the original output with the final combined version
                    output = final_output
                    logger.debug(
                        "Successfully combined main pages + terms using fresh readers"
                    )

                except Exception as e:
                    logger.error("Error reading terms PDF %s: %s", terms_file, e)
                    # Create a simple text page as fallback
                    from reportlab.pdfgen import canvas
                    from reportlab.lib.pagesizes import letter

                    fallback_buffer = io.BytesIO()
                    c = canvas.Canvas(fallback_buffer, pagesize=letter)
                    c.setFont("Helvetica", 12)
                    c.drawString(50, 750, f"Terms and Conditions - {consortium_abbrev}")
                    c.drawString(
                        50, 720, f"[Terms PDF could not be loaded: {terms_file}]"
                    )
                    c.save()
                    fallback_buffer.seek(0)

                    fallback_reader = PdfReader(fallback_buffer)
                    output.add_page(fallback_reader.pages[0])
                    logger.debug("Added fallback terms page")
            else:
                logger.warning("Terms file not found: %s", terms_path)
        else:
            logger.debug("No terms mapping for consortium: %s", consortium_abbrev)

        # Write to bytes
        output_buffer = io.BytesIO()
        output.write(output_buffer)
        output_buffer.seek(0)

        # Final validation - check the complete PDF
        try:
            output_buffer.seek(0)
            final_reader = PdfReader(output_buffer)
            total_pages = len(final_reader.pages)
            logger.debug("Final PDF validation: %d total pages", total_pages)

            # Quick check of each page type
            for i, page in enumerate(final_reader.pages):
                page_type = "data" if i == 0 else "terms"
                try:
                    mediabox = page.mediabox
                    resources = page.get("/Resources", {})
                    has_content = "/XObject" in resources or "/Font" in resources
                    logger.debug(
                        "   Page %d (%s): %sx%s, content=%s", i+1, page_type, mediabox.width, mediabox.height, has_content
                    )
                except Exception:
                    pass

            output_buffer.seek(0)  # Reset for return
        except Exception as validation_error:
            logger.warning("PDF validation failed: %s", validation_error)

        return output_buffer

    def _get_consortium_terms_file(self, consortium_abbrev, consortium_obj=None):
        """Get the appropriate terms file based on consortium"""
        # Only use terms if consortium object has a custom terms PDF uploaded
        if (
            consortium_obj
            and hasattr(consortium_obj, "terms_pdf")
            and consortium_obj.terms_pdf
        ):
            # Sanitize filename to prevent path traversal
            terms_filename = os.path.basename(consortium_obj.terms_pdf)
            if not terms_filename or terms_filename.startswith('.'):
                return None
            # Return path relative to uploads/terms/
            terms_path = os.path.join(
                "..", "..", "uploads", "terms", terms_filename
            )
            # Verify resolved path stays within uploads/terms/
            resolved = os.path.realpath(os.path.join(self.static_path, terms_path))
            uploads_dir = os.path.realpath(os.path.join(self.static_path, "..", "..", "uploads", "terms"))
            if not resolved.startswith(uploads_dir):
                return None
            return terms_path

        # No fallback - if no terms configured, don't add any terms
        return None

    def _wrap_text(self, text, max_chars):
        """Wrap text to specified character width"""
        if not text:
            return []

        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            if len(current_line + " " + word) <= max_chars:
                current_line = current_line + " " + word if current_line else word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines
