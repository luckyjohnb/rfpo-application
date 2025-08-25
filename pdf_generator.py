#!/usr/bin/env python3
"""
PDF Generator for RFPO Purchase Orders
Combines template PDFs with dynamic RFPO data
"""

import os
import io
from datetime import datetime
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from flask import current_app

class RFPOPDFGenerator:
    def __init__(self, positioning_config=None):
        self.static_path = os.path.join(current_app.root_path, 'static', 'po_files')
        self.logo_path = os.path.join(current_app.root_path, 'uploads', 'logos')
        self.positioning_config = positioning_config
        
        # Debug positioning config
        if positioning_config:
            print(f"🎯 PDF Generator initialized WITH positioning config: {type(positioning_config)}")
            try:
                pos_data = positioning_config.get_positioning_data()
                print(f"🎯 Positioning data keys: {list(pos_data.keys())}")
                visible_fields = [k for k, v in pos_data.items() if v.get('visible', True)]
                hidden_fields = [k for k, v in pos_data.items() if not v.get('visible', True)]
                print(f"🎯 Visible fields ({len(visible_fields)}): {visible_fields}")
                print(f"🎯 Hidden fields ({len(hidden_fields)}): {hidden_fields}")
                
                # Show first few fields with details
                for i, (field_name, field_data) in enumerate(list(pos_data.items())[:3]):
                    print(f"🎯 Field {i+1} {field_name}: x={field_data.get('x')}, y={field_data.get('y')}, visible={field_data.get('visible')}")
            except Exception as e:
                print(f"❌ Error accessing positioning data: {e}")
        else:
            print("⚠️  PDF Generator initialized WITHOUT positioning config - will use defaults")
        
    def generate_po_pdf(self, rfpo, consortium, project, vendor=None, vendor_site=None):
        """Generate complete PO PDF with dynamic data"""
        try:
            # Create a temporary PDF with our data overlay
            data_pdf = self._create_data_overlay(rfpo, consortium, project, vendor, vendor_site)
            
            # Combine with template PDFs
            final_pdf = self._combine_with_templates(data_pdf, consortium.abbrev)
            
            return final_pdf
            
        except Exception as e:
            print(f"Error generating PDF: {e}")
            raise
        
    def _create_data_overlay(self, rfpo, consortium, project, vendor=None, vendor_site=None):
        """Create PDF overlay with RFPO data"""
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        
        # Page 1: Main PO Information including line items (like legacy template)
        self._draw_page1_data(c, rfpo, consortium, project, vendor, vendor_site, width, height)
        c.showPage()
        
        c.save()
        buffer.seek(0)
        return buffer
    
    def _get_field_position(self, field_name, default_x=0, default_y=0):
        """Get positioning data for a field, with fallback to defaults"""
        if not self.positioning_config:
            return default_x, default_y, 9, 'normal'  # default font_size and weight
        
        positioning_data = self.positioning_config.get_positioning_data()
        field_data = positioning_data.get(field_name, {})
        
        # If field is not in positioning data, don't draw it (field was cleared/removed)
        if not field_data:
            print(f"🚫 Field {field_name} not in positioning data - skipping (cleared)")
            return None, None, None, None
        
        # If field is explicitly hidden, don't draw it
        if not field_data.get('visible', True):
            print(f"🚫 Field {field_name} is hidden - skipping")
            return None, None, None, None
        
        x = field_data.get('x', default_x)
        y = field_data.get('y', default_y)
        font_size = field_data.get('font_size', 9)
        font_weight = field_data.get('font_weight', 'normal')
        
        # FIXED: Frontend already converts screen coordinates to PDF coordinates
        # The stored coordinates are already in PDF coordinate space (origin at bottom-left)
        # Apply preview offset adjustment to align with designer positioning
        if self.positioning_config:
            pdf_width = 612
            pdf_height = 792
            
            print(f"📐 Canvas is fixed at PDF dimensions: {pdf_width}x{pdf_height}")
            
            # Coordinates are already in PDF space - apply preview offset for alignment
            preview_offset = -15  # Offset to align preview with designer positioning (was 25, now -15 for 40px decrease)
            pdf_x = x
            pdf_y = y + preview_offset  # Adjust Y coordinate for preview alignment
            
            print(f"🔄 Using stored PDF coordinates for {field_name}:")
            print(f"   Stored PDF coords: ({x}, {y}) -> Preview adjusted: ({pdf_x:.1f}, {pdf_y:.1f})")
            print(f"   Applied preview offset: +{preview_offset}px Y")
            
            # Ensure coordinates are within PDF bounds
            pdf_x = max(0, min(pdf_width, pdf_x))
            pdf_y = max(0, min(pdf_height, pdf_y))
            
            if pdf_x != x or pdf_y != (y + preview_offset):
                print(f"⚠️  Clamped {field_name} coordinates to bounds: ({pdf_x:.1f}, {pdf_y:.1f})")
            
            return pdf_x, pdf_y, font_size, font_weight
        
        return x, y, font_size, font_weight
    
    def _draw_text_with_positioning(self, canvas, field_name, text, default_x, default_y, right_align=False):
        """Draw text using positioning configuration - supports multi-line text"""
        x, y, font_size, font_weight = self._get_field_position(field_name, default_x, default_y)
        
        if x is None:  # Field is hidden
            print(f"🚫 Field {field_name} is hidden, skipping")
            return
        
        print(f"📝 Drawing {field_name}: '{text}' at ({x}, {y}) with font {font_size}pt {font_weight}")
        
        # Validate coordinates are within PDF bounds
        if x < 0 or x > 612 or y < 0 or y > 792:
            print(f"⚠️  WARNING: {field_name} coordinates ({x}, {y}) are outside PDF bounds (612x792)")
        
        # Set font based on weight
        if font_weight == 'bold':
            canvas.setFont("Helvetica-Bold", font_size)
        else:
            canvas.setFont("Helvetica", font_size)
        
        try:
            # Handle multi-line text by splitting on newlines
            text_lines = str(text).split('\n')
            line_height = font_size + 2  # Add small spacing between lines
            
            for i, line in enumerate(text_lines):
                line_y = y - (i * line_height)  # Move down for each line
                if right_align:
                    canvas.drawRightString(x, line_y, line.strip())
                else:
                    canvas.drawString(x, line_y, line.strip())
            
            print(f"✅ Successfully drew {field_name} ({len(text_lines)} lines)")
        except Exception as e:
            print(f"❌ Error drawing {field_name}: {e}")
    
    def _draw_logo_with_positioning(self, canvas, field_name, logo_filename, default_x, default_y):
        """Draw logo image using positioning configuration"""
        x, y, _, _ = self._get_field_position(field_name, default_x, default_y)
        
        if x is None:  # Field is hidden
            print(f"🚫 Logo field {field_name} is hidden, skipping")
            return
        
        print(f"🖼️ Drawing logo {field_name}: '{logo_filename}' at ({x}, {y})")
        
        try:
            import os
            from reportlab.lib.utils import ImageReader
            from PIL import Image
            
            # Get logo file path
            logo_path = os.path.join('uploads', 'logos', logo_filename)
            
            # Check if logo file exists
            if not os.path.exists(logo_path):
                print(f"⚠️ Logo file not found: {logo_path}")
                # Draw placeholder text instead
                canvas.setFont("Helvetica", 8)
                canvas.drawString(x, y, f"[LOGO: {logo_filename}]")
                return
            
            # Get logo dimensions from positioning config or use defaults
            positioning_data = self.positioning_config.get_positioning_data() if self.positioning_config else {}
            field_config = positioning_data.get(field_name, {})
            logo_width = field_config.get('width', 80)
            logo_height = field_config.get('height', 40)
            
            # Apply logo-specific offset to align with designer positioning
            # Logo needs to move UP significantly in preview to match designer top positioning
            logo_preview_offset = -60  # Move logo up in preview by 60px (was -80, corrected by +20)
            pdf_y = y + logo_preview_offset
            
            # Validate coordinates are within PDF bounds
            if x < 0 or x > 612 or pdf_y < 0 or pdf_y > 792:
                print(f"⚠️ WARNING: {field_name} coordinates ({x}, {pdf_y}) are outside PDF bounds (612x792)")
            
            # Draw the logo image
            canvas.drawImage(logo_path, x, pdf_y, width=logo_width, height=logo_height, preserveAspectRatio=True)
            print(f"✅ Successfully drew logo {field_name}")
            
        except Exception as e:
            print(f"❌ Error drawing logo {field_name}: {e}")
            # Draw placeholder text as fallback
            try:
                canvas.setFont("Helvetica", 8)
                canvas.drawString(x, y, f"[LOGO ERROR: {logo_filename}]")
            except:
                pass
    
    def _draw_page1_data(self, canvas, rfpo, consortium, project, vendor, vendor_site, width, height):
        """Draw data on page 1 (main PO info) - using positioning configuration or legacy defaults"""
        
        # === CONSORTIUM LOGO ===
        if consortium and hasattr(consortium, 'logo') and consortium.logo:
            self._draw_logo_with_positioning(canvas, 'consortium_logo', consortium.logo, 50, 750)
        
        # === TOP SECTION ===
        # PO NUMBER
        self._draw_text_with_positioning(canvas, 'po_number', rfpo.rfpo_id, 470, 710)
        
        # DATE OF ORDER
        self._draw_text_with_positioning(canvas, 'po_date', datetime.now().strftime('%m/%d/%Y'), 470, 695)
        
        # === VENDOR SECTION ===
        if vendor:
            # Determine which contact info to use - vendor_site takes priority, then vendor default
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
                # Fall back to vendor's default contact info
                contact_name = vendor.contact_name
                contact_address = vendor.contact_address
                contact_city = vendor.contact_city
                contact_state = vendor.contact_state
                contact_zip = vendor.contact_zip
                contact_tel = vendor.contact_tel
            
            # Vendor company name
            self._draw_text_with_positioning(canvas, 'vendor_company', vendor.company_name, 60, 600)
            
            # Contact person
            if contact_name:
                self._draw_text_with_positioning(canvas, 'vendor_contact', contact_name, 60, 585)
            
            # Use pre-formatted address if available, otherwise build from components
            if contact_address:
                # Use the pre-formatted address (likely already contains full address with line breaks)
                self._draw_text_with_positioning(canvas, 'vendor_address', contact_address, 60, 570)
            else:
                # Build address from individual components if no pre-formatted address
                address_parts = []
                city_state_zip = []
                if contact_city:
                    city_state_zip.append(contact_city)
                if contact_state:
                    city_state_zip.append(contact_state)
                if contact_zip:
                    city_state_zip.append(contact_zip)
                
                if city_state_zip:
                    address_parts.append(', '.join(city_state_zip))
                
                if address_parts:
                    self._draw_text_with_positioning(canvas, 'vendor_address', '\n'.join(address_parts), 60, 570)
                
            # Phone number if available
            if contact_tel:
                self._draw_text_with_positioning(canvas, 'vendor_phone', f"Phone: {contact_tel}", 60, 555)
        else:
            # Show placeholder if no vendor selected
            self._draw_text_with_positioning(canvas, 'vendor_company', "[No Vendor Selected]", 60, 600)
        
        # === SHIP TO SECTION ===
        if rfpo.shipto_name:
            self._draw_text_with_positioning(canvas, 'ship_to_name', rfpo.shipto_name, 240, 600)
        
        if rfpo.shipto_address:
            # Keep original line breaks for proper multi-line formatting
            self._draw_text_with_positioning(canvas, 'ship_to_address', rfpo.shipto_address, 240, 585)
        
        # === DELIVERY SECTION ===
        # Type & Place
        if rfpo.delivery_type:
            self._draw_text_with_positioning(canvas, 'delivery_type', rfpo.delivery_type, 410, 570)
        
        # Payment for Transportation
        if rfpo.delivery_payment:
            self._draw_text_with_positioning(canvas, 'delivery_payment', rfpo.delivery_payment, 410, 545)
        
        # Routing
        if rfpo.delivery_routing:
            self._draw_text_with_positioning(canvas, 'delivery_routing', rfpo.delivery_routing, 410, 520)
        
        # === MIDDLE SECTION ===
        # PAYMENT section
        if rfpo.payment_terms:
            self._draw_text_with_positioning(canvas, 'payment_terms', rfpo.payment_terms, 60, 470)
        
        # PROJECT section
        self._draw_text_with_positioning(canvas, 'project_info', f"[{project.ref}] {project.name}", 240, 470)
        
        # DELIVERY DATE
        if rfpo.delivery_date:
            self._draw_text_with_positioning(canvas, 'delivery_date', rfpo.delivery_date.strftime('%m/%d/%Y'), 410, 470)
        
        # Government Agreement Number
        if rfpo.government_agreement_number:
            self._draw_text_with_positioning(canvas, 'government_agreement', 
                f"U.S. Government Funding under Agreement Number: {rfpo.government_agreement_number}", 240, 455)
        
        # === LINE ITEMS SECTION (Middle area, starts around y=400) ===
        if rfpo.line_items:
            # Line items table - positioned to match legacy template  
            table_start_y = 410
            line_height = 12
            current_y = table_start_y
            
            # Table headers - use positioning for header
            self._draw_text_with_positioning(canvas, 'line_items_header', 
                "QTY  DESCRIPTION OF SUPPLIES OR SERVICES  UNIT PRICE  TOTAL PRICE", 60, current_y)
            
            # Draw line under headers
            canvas.line(60, current_y - 3, 530, current_y - 3)
            
            current_y -= 20
            canvas.setFont("Helvetica", 8)
            
            for i, item in enumerate(rfpo.line_items):
                if current_y < 150:  # Stop if getting too close to bottom
                    break
                
                # Quantity (left-aligned in qty column)
                self._draw_text_with_positioning(canvas, f'line_item_{i}_quantity', str(item.quantity), 60, current_y)
                
                # Description (wrapped to fit column width)
                desc_lines = self._wrap_text(item.description, 45)
                desc_text = desc_lines[0] if desc_lines else ""
                
                # Add capital equipment indicator to description if applicable
                if item.is_capital_equipment:
                    desc_text += " [CAPITAL EQUIP.]"
                
                self._draw_text_with_positioning(canvas, f'line_item_{i}_description', desc_text, 120, current_y)
                
                # Unit price (right-aligned in unit price column)  
                self._draw_text_with_positioning(canvas, f'line_item_{i}_unit_price', f"${item.unit_price:,.2f}", 450, current_y, right_align=True)
                
                # Total price (right-aligned in total price column)
                self._draw_text_with_positioning(canvas, f'line_item_{i}_total_price', f"${item.total_price:,.2f}", 530, current_y, right_align=True)
                
                # If description is too long, continue on next line
                if len(desc_lines) > 1 and current_y > 160:
                    current_y -= line_height
                    self._draw_text_with_positioning(canvas, f'line_item_{i}_description_cont', desc_lines[1][:45] + "..." if len(desc_lines[1]) > 45 else desc_lines[1], 120, current_y)
                
                current_y -= line_height
            
            # Add totals section at bottom right
            current_y -= 10
            canvas.line(400, current_y, 530, current_y)  # Line above totals
            current_y -= 15
            
            # Subtotal
            self._draw_text_with_positioning(canvas, 'subtotal', f"SUBTOTAL: ${rfpo.subtotal:,.2f}", 400, current_y)
            
            if rfpo.cost_share_amount and rfpo.cost_share_amount > 0:
                current_y -= 15
                canvas.setFont("Helvetica", 9)
                self._draw_text_with_positioning(canvas, 'vendor_cost_share_label', "VENDOR COST SHARE:", 350, current_y)
                self._draw_text_with_positioning(canvas, 'vendor_cost_share_amount', f"-${rfpo.cost_share_amount:,.2f}", 530, current_y, right_align=True)
            
            current_y -= 15
            canvas.line(400, current_y + 10, 530, current_y + 10)  # Line above total
            
            # Total
            self._draw_text_with_positioning(canvas, 'total', f"TOTAL: ${rfpo.total_amount:,.2f}", 400, current_y)
            
            # Set the bottom position for requestor/invoice sections
            bottom_sections_y = current_y - 30
        else:
            bottom_sections_y = 350
        
        # === VENDOR IS SECTION (Bottom left area) ===
        vendor_is_y = bottom_sections_y - 50
        canvas.setFont("Helvetica", 8)
        self._draw_text_with_positioning(canvas, 'vendor_type_label', "VENDOR IS:", 60, vendor_is_y)
        
        # Checkboxes (using simple text representation)
        checkbox_y = vendor_is_y - 15
        self._draw_text_with_positioning(canvas, 'vendor_small_business', "☐ SMALL BUSINESS", 60, checkbox_y)
        self._draw_text_with_positioning(canvas, 'vendor_university', "☐ UNIVERSITY", 160, checkbox_y)
        self._draw_text_with_positioning(canvas, 'vendor_nonprofit', "☐ NON-PROFIT", 240, checkbox_y)
        
        # === REQUESTOR SECTION ===
        requestor_info_parts = []
        requestor_info_parts.append(rfpo.requestor_id or "ADMIN001")
        if rfpo.requestor_tel:
            requestor_info_parts.append(f"Tel: {rfpo.requestor_tel}")
        if rfpo.requestor_location:
            requestor_info_parts.append(rfpo.requestor_location)
        
        if requestor_info_parts:
            self._draw_text_with_positioning(canvas, 'requestor_info', '\n'.join(requestor_info_parts), 60, bottom_sections_y)
        
        # === INVOICE TO SECTION ===
        if rfpo.invoice_address:
            # Keep original line breaks for proper multi-line formatting
            self._draw_text_with_positioning(canvas, 'invoice_address', rfpo.invoice_address, 410, bottom_sections_y)
    

    
    def _combine_with_templates(self, data_pdf, consortium_abbrev):
        """Combine data overlay with template PDFs"""
        output = PdfWriter()
        
        # Load data PDF
        data_reader = PdfReader(data_pdf)
        
        # Page 1: Combine with po.pdf template (all main content on one page like legacy)
        template_path = os.path.join(self.static_path, 'po.pdf')
        if os.path.exists(template_path):
            template_reader = PdfReader(template_path)
            if len(template_reader.pages) > 0:
                page = template_reader.pages[0]
                if len(data_reader.pages) > 0:
                    page.merge_page(data_reader.pages[0])
                output.add_page(page)
        
        # Add consortium-specific terms
        terms_file = self._get_consortium_terms_file(consortium_abbrev)
        if terms_file:
            terms_path = os.path.join(self.static_path, terms_file)
            if os.path.exists(terms_path):
                terms_reader = PdfReader(terms_path)
                for page in terms_reader.pages:
                    output.add_page(page)
        
        # Write to bytes
        output_buffer = io.BytesIO()
        output.write(output_buffer)
        output_buffer.seek(0)
        
        return output_buffer
    
    def _get_consortium_terms_file(self, consortium_abbrev):
        """Get the appropriate terms file based on consortium"""
        terms_mapping = {
            'USCAR': 'uscar_terms.pdf',
            'USABC': 'usabc_terms.pdf', 
            'USAMP': 'usamp_terms.pdf'
        }
        return terms_mapping.get(consortium_abbrev.upper())
    
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
