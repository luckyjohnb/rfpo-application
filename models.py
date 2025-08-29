from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import json

db = SQLAlchemy()

class Consortium(db.Model):
    """Consortium model for managing different consortiums"""
    __tablename__ = 'consortiums'
    
    id = db.Column(db.Integer, primary_key=True)
    consort_id = db.Column(db.String(32), unique=True, nullable=False)  # External consortium ID (e.g., "00000008")
    
    # Basic Information (matching form field names)
    name = db.Column(db.String(255), nullable=False, unique=True)  # consort_name
    abbrev = db.Column(db.String(20), nullable=False, unique=True)  # consort_abbrev
    logo = db.Column(db.String(255))  # consort_logo_1 (logo filename for web)
    terms_pdf = db.Column(db.String(255))  # terms_pdf (terms and conditions PDF filename)
    
    # Configuration flags
    require_approved_vendors = db.Column(db.Boolean, default=True)  # consort_rfpo_approvedvendors (1=Yes, 0=No)
    non_government_project_id = db.Column(db.String(32))  # consort_non_projects (project ID from dropdown)
    
    # User permissions (stored as JSON arrays for multi-select fields)
    rfpo_viewer_user_ids = db.Column(db.Text)  # consort_rfpo_viewers[] - JSON array of user IDs
    rfpo_admin_user_ids = db.Column(db.Text)   # consort_rfpo_admin[] - JSON array of user IDs
    
    # Contact and document delivery information
    invoicing_address = db.Column(db.Text)  # consort_invoicing_1 (textarea)
    
    # Fax information for required documents
    doc_fax_name = db.Column(db.String(255))  # consort_doc_faxname
    doc_fax_number = db.Column(db.String(255))  # consort_doc_faxno
    
    # Email information for required documents
    doc_email_name = db.Column(db.String(255))  # consort_doc_emailname
    doc_email_address = db.Column(db.String(255))  # consort_doc_emailaddress
    
    # Postal information for required documents
    doc_post_name = db.Column(db.String(255))  # consort_doc_postname
    doc_post_address = db.Column(db.Text)  # consort_doc_postaddress (textarea)
    
    # Completed PO email
    po_email = db.Column(db.String(255))  # consort_po_email
    
    # Status and audit fields
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(64))
    updated_by = db.Column(db.String(64))
    
    # Note: Teams reference this consortium via consortium_consort_id field
    
    def get_rfpo_viewer_users(self):
        """Get list of RFPO viewer user IDs"""
        if self.rfpo_viewer_user_ids:
            return json.loads(self.rfpo_viewer_user_ids)
        return []
    
    def set_rfpo_viewer_users(self, user_ids):
        """Set RFPO viewer user IDs from a list"""
        if user_ids:
            # Filter out empty strings and 'none' values
            filtered_ids = [uid for uid in user_ids if uid and uid != '']
            self.rfpo_viewer_user_ids = json.dumps(filtered_ids)
        else:
            self.rfpo_viewer_user_ids = None
    
    def get_rfpo_admin_users(self):
        """Get list of RFPO admin user IDs"""
        if self.rfpo_admin_user_ids:
            return json.loads(self.rfpo_admin_user_ids)
        return []
    
    def set_rfpo_admin_users(self, user_ids):
        """Set RFPO admin user IDs from a list"""
        if user_ids:
            # Filter out empty strings and 'none' values
            filtered_ids = [uid for uid in user_ids if uid and uid != '']
            self.rfpo_admin_user_ids = json.dumps(filtered_ids)
        else:
            self.rfpo_admin_user_ids = None
    
    def to_dict(self):
        return {
            'id': self.id,
            'consort_id': self.consort_id,
            'name': self.name,
            'abbrev': self.abbrev,
            'logo': self.logo,
            'terms_pdf': self.terms_pdf,
            'require_approved_vendors': self.require_approved_vendors,
            'non_government_project_id': self.non_government_project_id,
            'rfpo_viewer_user_ids': self.get_rfpo_viewer_users(),
            'rfpo_admin_user_ids': self.get_rfpo_admin_users(),
            'invoicing_address': self.invoicing_address,
            'doc_fax_name': self.doc_fax_name,
            'doc_fax_number': self.doc_fax_number,
            'doc_email_name': self.doc_email_name,
            'doc_email_address': self.doc_email_address,
            'doc_post_name': self.doc_post_name,
            'doc_post_address': self.doc_post_address,
            'po_email': self.po_email,
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'updated_by': self.updated_by
        }
    
    def __repr__(self):
        return f'<Consortium {self.consort_id} ({self.abbrev}): {self.name}>'

class RFPO(db.Model):
    """Request for Purchase Order model"""
    __tablename__ = 'rfpos'
    
    id = db.Column(db.Integer, primary_key=True)
    rfpo_id = db.Column(db.String(64), unique=True, nullable=False)  # e.g., RFPO-TestProj3-2025-08-24-N01
    title = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text)
    
    # Project and Team associations
    project_id = db.Column(db.String(32), nullable=False)  # Project ID this RFPO belongs to
    consortium_id = db.Column(db.String(32), nullable=False)  # Consortium ID
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    
    # Government Agreement
    government_agreement_number = db.Column(db.String(255))
    
    # Requestor Information
    requestor_id = db.Column(db.String(32), nullable=False)  # User ID of requestor
    requestor_tel = db.Column(db.String(50))
    requestor_location = db.Column(db.Text)
    
    # Shipping Information
    shipto_name = db.Column(db.String(255))
    shipto_tel = db.Column(db.String(50))
    shipto_address = db.Column(db.Text)
    
    # Invoice Information
    invoice_address = db.Column(db.Text)
    
    # Delivery Information
    delivery_date = db.Column(db.Date)
    delivery_type = db.Column(db.String(100))  # FOB Seller's Plant, FOB Destination
    delivery_payment = db.Column(db.String(100))  # Collect, Prepaid
    delivery_routing = db.Column(db.String(100))  # Buyer's traffic, Seller's traffic
    payment_terms = db.Column(db.String(100), default='Net 30')
    
    # Vendor Information
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'))
    vendor_site_id = db.Column(db.Integer, db.ForeignKey('vendor_sites.id'))
    
    # Financial Information
    subtotal = db.Column(db.Numeric(12, 2), default=0.00)
    cost_share_description = db.Column(db.String(255))
    cost_share_type = db.Column(db.String(20), default='total')  # 'total' or 'percent'
    cost_share_amount = db.Column(db.Numeric(12, 2), default=0.00)
    total_amount = db.Column(db.Numeric(12, 2), default=0.00)
    
    # Optional Comments (not included in RFPO)
    comments = db.Column(db.Text)
    
    # Status and tracking
    status = db.Column(db.String(32), default='Draft')  # Draft, Submitted, Approved, etc.
    due_date = db.Column(db.Date)
    created_by = db.Column(db.String(64), nullable=False)
    updated_by = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    team = db.relationship('Team', backref=db.backref('rfpos', lazy=True))
    vendor = db.relationship('Vendor', backref=db.backref('rfpos', lazy=True))
    vendor_site = db.relationship('VendorSite', backref=db.backref('rfpos', lazy=True))
    files = db.relationship('UploadedFile', backref='rfpo', lazy=True, cascade='all, delete-orphan')
    line_items = db.relationship('RFPOLineItem', backref='rfpo', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'rfpo_id': self.rfpo_id,
            'title': self.title,
            'description': self.description,
            'project_id': self.project_id,
            'consortium_id': self.consortium_id,
            'team_id': self.team_id,
            'government_agreement_number': self.government_agreement_number,
            'requestor_id': self.requestor_id,
            'requestor_tel': self.requestor_tel,
            'requestor_location': self.requestor_location,
            'shipto_name': self.shipto_name,
            'shipto_tel': self.shipto_tel,
            'shipto_address': self.shipto_address,
            'invoice_address': self.invoice_address,
            'delivery_date': self.delivery_date.isoformat() if self.delivery_date else None,
            'delivery_type': self.delivery_type,
            'delivery_payment': self.delivery_payment,
            'delivery_routing': self.delivery_routing,
            'payment_terms': self.payment_terms,
            'vendor_id': self.vendor_id,
            'vendor_site_id': self.vendor_site_id,
            'vendor_name': self.vendor.company_name if self.vendor else None,
            'subtotal': float(self.subtotal) if self.subtotal else 0.00,
            'cost_share_description': self.cost_share_description,
            'cost_share_type': self.cost_share_type,
            'cost_share_amount': float(self.cost_share_amount) if self.cost_share_amount else 0.00,
            'total_amount': float(self.total_amount) if self.total_amount else 0.00,
            'comments': self.comments,
            'status': self.status,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'created_by': self.created_by,
            'updated_by': self.updated_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'file_count': len(self.files) if self.files else 0,
            'line_item_count': len(self.line_items) if self.line_items else 0
        }

class RFPOLineItem(db.Model):
    """Line items for RFPO purchase orders"""
    __tablename__ = 'rfpo_line_items'
    
    id = db.Column(db.Integer, primary_key=True)
    rfpo_id = db.Column(db.Integer, db.ForeignKey('rfpos.id'), nullable=False)
    line_number = db.Column(db.Integer, nullable=False)  # Order in the RFPO (1, 2, 3...)
    
    # Line item details
    quantity = db.Column(db.Integer, default=0)
    description = db.Column(db.Text, nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), default=0.00)
    total_price = db.Column(db.Numeric(12, 2), default=0.00)
    
    # Capital Equipment Information (optional)
    is_capital_equipment = db.Column(db.Boolean, default=False)
    capital_description = db.Column(db.String(255))
    capital_serial_id = db.Column(db.String(100))
    capital_location = db.Column(db.String(255))
    capital_acquisition_date = db.Column(db.Date)
    capital_condition = db.Column(db.String(255))
    capital_acquisition_cost = db.Column(db.Numeric(12, 2))
    
    # Audit fields
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def calculate_total(self):
        """Calculate total price from quantity and unit price"""
        if self.quantity and self.unit_price:
            self.total_price = self.quantity * self.unit_price
        else:
            self.total_price = 0.00
    
    def to_dict(self):
        return {
            'id': self.id,
            'rfpo_id': self.rfpo_id,
            'line_number': self.line_number,
            'quantity': self.quantity,
            'description': self.description,
            'unit_price': float(self.unit_price) if self.unit_price else 0.00,
            'total_price': float(self.total_price) if self.total_price else 0.00,
            'is_capital_equipment': self.is_capital_equipment,
            'capital_description': self.capital_description,
            'capital_serial_id': self.capital_serial_id,
            'capital_location': self.capital_location,
            'capital_acquisition_date': self.capital_acquisition_date.isoformat() if self.capital_acquisition_date else None,
            'capital_condition': self.capital_condition,
            'capital_acquisition_cost': float(self.capital_acquisition_cost) if self.capital_acquisition_cost else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<RFPOLineItem {self.line_number}: {self.description[:50]}... ({self.quantity} @ ${self.unit_price})>'

class UploadedFile(db.Model):
    """Uploaded files associated with RFPOs"""
    __tablename__ = 'uploaded_files'
    
    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.String(36), unique=True, nullable=False)  # UUID
    original_filename = db.Column(db.String(256), nullable=False)
    stored_filename = db.Column(db.String(256), nullable=False)  # UUID_originalname
    file_path = db.Column(db.String(512), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)  # Size in bytes
    mime_type = db.Column(db.String(128))
    file_extension = db.Column(db.String(10))
    document_type = db.Column(db.String(255))  # Document type from doc_types list
    description = db.Column(db.Text)  # Optional description
    
    # RAG processing status
    processing_status = db.Column(db.String(32), default='pending')  # pending, processing, completed, failed
    text_extracted = db.Column(db.Boolean, default=False)
    embeddings_created = db.Column(db.Boolean, default=False)
    chunk_count = db.Column(db.Integer, default=0)
    processing_error = db.Column(db.Text)
    
    # Associations
    rfpo_id = db.Column(db.Integer, db.ForeignKey('rfpos.id'), nullable=False)
    uploaded_by = db.Column(db.String(64), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    
    # Relationships
    chunks = db.relationship('DocumentChunk', backref='file', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'file_id': self.file_id,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'file_extension': self.file_extension,
            'document_type': self.document_type,
            'description': self.description,
            'processing_status': self.processing_status,
            'text_extracted': self.text_extracted,
            'embeddings_created': self.embeddings_created,
            'chunk_count': self.chunk_count,
            'processing_error': self.processing_error,
            'rfpo_id': self.rfpo_id,
            'uploaded_by': self.uploaded_by,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None
        }

class DocumentChunk(db.Model):
    """Text chunks from documents for RAG"""
    __tablename__ = 'document_chunks'
    
    id = db.Column(db.Integer, primary_key=True)
    chunk_id = db.Column(db.String(36), unique=True, nullable=False)  # UUID
    text_content = db.Column(db.Text, nullable=False)
    chunk_index = db.Column(db.Integer, nullable=False)  # Order in document
    chunk_size = db.Column(db.Integer, nullable=False)  # Character count
    
    # Metadata
    page_number = db.Column(db.Integer)  # For PDFs
    section_title = db.Column(db.String(256))  # If extractable
    metadata_json = db.Column(db.Text)  # Additional metadata as JSON
    
    # Vector embeddings (stored as JSON for SQLite compatibility)
    embedding_vector = db.Column(db.Text)  # JSON serialized embedding
    embedding_model = db.Column(db.String(128))  # Model used for embedding
    
    # Associations
    file_id = db.Column(db.Integer, db.ForeignKey('uploaded_files.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_embedding(self, vector):
        """Store embedding vector as JSON"""
        if vector is not None:
            self.embedding_vector = json.dumps(vector.tolist() if hasattr(vector, 'tolist') else vector)
    
    def get_embedding(self):
        """Retrieve embedding vector from JSON"""
        if self.embedding_vector:
            return json.loads(self.embedding_vector)
        return None
    
    def set_metadata(self, metadata_dict):
        """Store metadata as JSON"""
        if metadata_dict:
            self.metadata_json = json.dumps(metadata_dict)
    
    def get_metadata(self):
        """Retrieve metadata from JSON"""
        if self.metadata_json:
            return json.loads(self.metadata_json)
        return {}
    
    def to_dict(self):
        return {
            'id': self.id,
            'chunk_id': self.chunk_id,
            'text_content': self.text_content,
            'chunk_index': self.chunk_index,
            'chunk_size': self.chunk_size,
            'page_number': self.page_number,
            'section_title': self.section_title,
            'metadata': self.get_metadata(),
            'embedding_model': self.embedding_model,
            'file_id': self.file_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Team(db.Model):
    """Team model for managing teams within consortiums"""
    __tablename__ = 'teams'
    
    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.String(32), unique=True, nullable=False)  # External team ID (e.g., "00000098")
    name = db.Column(db.String(255), nullable=False)  # team_name (increased to match form maxlength)
    description = db.Column(db.Text)  # team_desc (textarea)
    abbrev = db.Column(db.String(32), nullable=False, unique=True)  # team_abbrev
    
    # Part of Consortium (optional - references consort_id from dropdown)
    consortium_consort_id = db.Column(db.String(32), nullable=True)  # team_consort (consortium's consort_id)
    
    # Team-level user permissions (stored as JSON arrays)
    rfpo_viewer_user_ids = db.Column(db.Text)  # team_rfpo_viewers[] - JSON array of user IDs
    rfpo_admin_user_ids = db.Column(db.Text)   # team_rfpo_admin[] - JSON array of user IDs
    
    # Status and audit fields
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(64))
    updated_by = db.Column(db.String(64))
    
    def get_rfpo_viewer_users(self):
        """Get list of RFPO viewer user IDs for this team"""
        if self.rfpo_viewer_user_ids:
            return json.loads(self.rfpo_viewer_user_ids)
        return []
    
    def set_rfpo_viewer_users(self, user_ids):
        """Set RFPO viewer user IDs from a list"""
        if user_ids:
            # Filter out empty strings and 'none' values
            filtered_ids = [uid for uid in user_ids if uid and uid != '']
            self.rfpo_viewer_user_ids = json.dumps(filtered_ids)
        else:
            self.rfpo_viewer_user_ids = None
    
    def get_rfpo_admin_users(self):
        """Get list of RFPO admin user IDs for this team"""
        if self.rfpo_admin_user_ids:
            return json.loads(self.rfpo_admin_user_ids)
        return []
    
    def set_rfpo_admin_users(self, user_ids):
        """Set RFPO admin user IDs from a list"""
        if user_ids:
            # Filter out empty strings and 'none' values
            filtered_ids = [uid for uid in user_ids if uid and uid != '']
            self.rfpo_admin_user_ids = json.dumps(filtered_ids)
        else:
            self.rfpo_admin_user_ids = None

    def to_dict(self):
        return {
            'id': self.id,
            'record_id': self.record_id,
            'name': self.name,
            'description': self.description,
            'abbrev': self.abbrev,
            'consortium_consort_id': self.consortium_consort_id,
            'rfpo_viewer_user_ids': self.get_rfpo_viewer_users(),
            'rfpo_admin_user_ids': self.get_rfpo_admin_users(),
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'updated_by': self.updated_by,
            'rfpo_count': len(self.rfpos) if self.rfpos else 0
        }
    
    def __repr__(self):
        consortium_info = f" (Consortium: {self.consortium_consort_id})" if self.consortium_consort_id else " (No Consortium)"
        return f'<Team {self.record_id} ({self.abbrev}): {self.name}{consortium_info}>'

class User(UserMixin, db.Model):
    """User model for managing system users"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.String(32), unique=True, nullable=False)  # External user ID (e.g., "00004326")
    
    # Basic Information (from create form)
    fullname = db.Column(db.String(100), nullable=False)  # Name
    email = db.Column(db.String(255), nullable=False, unique=True)  # Email (used as login username)
    password_hash = db.Column(db.String(255), nullable=False)  # Encrypted password
    sex = db.Column(db.String(1))  # 'm' or 'f'
    
    # Company Information
    company_code = db.Column(db.String(10))  # BP, CHEV, DOE, EM, FCA, FRD, GM, Lab, P66, SHL, xxx, USC
    company = db.Column(db.String(100))  # Company name
    position = db.Column(db.String(100))  # Job position/title
    department = db.Column(db.String(100))  # Dept
    
    # Address Information
    building_address = db.Column(db.String(100))  # Building/Int Mail address
    address1 = db.Column(db.String(100))  # Address1
    address2 = db.Column(db.String(100))  # Address2
    city = db.Column(db.String(100))  # City
    state = db.Column(db.String(2))  # State (2-letter code)
    zip_code = db.Column(db.String(20))  # Zip
    country = db.Column(db.String(100))  # Country
    
    # Contact Information
    phone = db.Column(db.String(50))  # Tel
    phone_ext = db.Column(db.String(8))  # Phone extension
    mobile = db.Column(db.String(50))  # Mobile
    fax = db.Column(db.String(50))  # Fax
    
    # System Permissions (stored as JSON for flexibility)
    permissions = db.Column(db.Text)  # JSON: CAL_MEET_USER, GOD, RFPO_ADMIN, RFPO_USER, VROOM_ADMIN, VROOM_USER
    
    # Legacy fields (marked as deprecated in forms)
    global_admin = db.Column(db.Boolean, default=False)  # Deprecated: "won't be used in future"
    use_rfpo = db.Column(db.Boolean, default=False)  # Deprecated: "won't be used in future"
    
    # Web/System Settings
    agreed_to_terms = db.Column(db.Boolean, default=False)  # Agreed to Ts&Cs
    max_upload_size = db.Column(db.Integer, default=8388608)  # Max upload allowed (in bytes)
    
    # Session/Login Information
    last_visit = db.Column(db.DateTime)
    last_ip = db.Column(db.String(45))  # IPv4 or IPv6
    last_browser = db.Column(db.Text)  # User agent string
    
    # Status and Audit
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(64))
    updated_by = db.Column(db.String(64))
    
    def get_permissions(self):
        """Get list of user permissions"""
        if self.permissions:
            return json.loads(self.permissions)
        return []
    
    def set_permissions(self, permission_list):
        """Set user permissions from a list"""
        if permission_list:
            self.permissions = json.dumps(permission_list)
        else:
            self.permissions = None
    
    def has_permission(self, permission):
        """Check if user has a specific permission"""
        user_permissions = self.get_permissions()
        return permission in user_permissions
    
    def is_super_admin(self):
        """Check if user is a super admin (GOD permission)"""
        return self.has_permission('GOD')
    
    def is_rfpo_admin(self):
        """Check if user has RFPO admin permissions"""
        return self.has_permission('RFPO_ADMIN') or self.is_super_admin()
    
    def is_rfpo_user(self):
        """Check if user has RFPO user permissions"""
        return self.has_permission('RFPO_USER') or self.is_rfpo_admin()
    
    def get_display_name(self):
        """Get formatted display name"""
        return self.fullname if self.fullname else self.email
    
    def get_full_address(self):
        """Get formatted full address"""
        address_parts = []
        if self.building_address:
            address_parts.append(self.building_address)
        if self.address1:
            address_parts.append(self.address1)
        if self.address2:
            address_parts.append(self.address2)
        if self.city:
            city_state_zip = self.city
            if self.state:
                city_state_zip += f", {self.state}"
            if self.zip_code:
                city_state_zip += f" {self.zip_code}"
            address_parts.append(city_state_zip)
        if self.country:
            address_parts.append(self.country)
        return "\n".join(address_parts)
    
    def get_teams(self):
        """Get list of teams this user belongs to"""
        return [ut.team for ut in self.user_teams if ut.team]
    
    def get_team_names(self):
        """Get list of team names this user belongs to"""
        return [team.name for team in self.get_teams()]
    
    def is_member_of_team(self, team_id):
        """Check if user is a member of a specific team"""
        return any(ut.team_id == team_id for ut in self.user_teams)
    
    def add_to_team(self, team_id, role='member', created_by=None):
        """Add user to a team with specified role"""
        if not self.is_member_of_team(team_id):
            user_team = UserTeam(
                user_id=self.id,
                team_id=team_id,
                role=role,
                created_by=created_by
            )
            db.session.add(user_team)
            return user_team
        return None
    
    def remove_from_team(self, team_id):
        """Remove user from a team"""
        user_team = next((ut for ut in self.user_teams if ut.team_id == team_id), None)
        if user_team:
            db.session.delete(user_team)
            return True
        return False
    
    def to_dict(self):
        return {
            'id': self.id,
            'record_id': self.record_id,
            'fullname': self.fullname,
            'email': self.email,
            'sex': self.sex,
            'company_code': self.company_code,
            'company': self.company,
            'position': self.position,
            'department': self.department,
            'building_address': self.building_address,
            'address1': self.address1,
            'address2': self.address2,
            'city': self.city,
            'state': self.state,
            'zip_code': self.zip_code,
            'country': self.country,
            'phone': self.phone,
            'phone_ext': self.phone_ext,
            'mobile': self.mobile,
            'fax': self.fax,
            'permissions': self.get_permissions(),
            'global_admin': self.global_admin,
            'use_rfpo': self.use_rfpo,
            'agreed_to_terms': self.agreed_to_terms,
            'max_upload_size': self.max_upload_size,
            'last_visit': self.last_visit.isoformat() if self.last_visit else None,
            'last_ip': self.last_ip,
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'updated_by': self.updated_by,
            'display_name': self.get_display_name(),
            'full_address': self.get_full_address(),
            'teams': self.get_team_names(),
            'team_count': len(self.user_teams),
            'is_super_admin': self.is_super_admin(),
            'is_rfpo_admin': self.is_rfpo_admin(),
            'is_rfpo_user': self.is_rfpo_user()
        }
    
    def __repr__(self):
        return f'<User {self.record_id}: {self.get_display_name()}>'

class UserTeam(db.Model):
    """Association table for User-Team relationships (many-to-many)"""
    __tablename__ = 'user_teams'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    
    # Role/Permission within the team (optional)
    role = db.Column(db.String(64))  # e.g., 'member', 'admin', 'viewer'
    
    # Audit fields
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(64))
    
    # Unique constraint to prevent duplicate associations
    __table_args__ = (
        db.UniqueConstraint('user_id', 'team_id', name='uq_user_team'),
    )
    
    # Relationships
    user = db.relationship('User', backref=db.backref('user_teams', lazy=True, cascade='all, delete-orphan'))
    team = db.relationship('Team', backref=db.backref('team_users', lazy=True, cascade='all, delete-orphan'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'team_id': self.team_id,
            'role': self.role,
            'user_name': self.user.fullname if self.user else None,
            'user_email': self.user.email if self.user else None,
            'team_name': self.team.name if self.team else None,
            'team_abbrev': self.team.abbrev if self.team else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by': self.created_by
        }
    
    def __repr__(self):
        return f'<UserTeam: {self.user.get_display_name() if self.user else "Unknown"} -> {self.team.name if self.team else "Unknown"}>'

class Project(db.Model):
    """Project model for managing non-government and research projects"""
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(32), unique=True, nullable=False)  # External project ID (e.g., "00000317")
    
    # Basic Information (matching form field names)
    ref = db.Column(db.String(20), nullable=False, unique=True)  # project_ref
    name = db.Column(db.String(255), nullable=False)  # project_name (Project Title)
    description = db.Column(db.Text)  # project_description (textarea)
    
    # Multi-consortium membership (projects can be financed through multiple consortiums)
    consortium_ids = db.Column(db.Text)  # project_consort[] - JSON array of consortium consort_ids
    
    # Optional team association
    team_record_id = db.Column(db.String(32), nullable=True)  # project_team (team's record_id)
    
    # Project member permissions
    rfpo_viewer_user_ids = db.Column(db.Text)  # project_rfpo_viewers[] - JSON array of user IDs
    
    # Project classification flags
    gov_funded = db.Column(db.Boolean, default=True)  # project_gov (Gov Funded checkbox)
    uni_project = db.Column(db.Boolean, default=False)  # project_uni (Uni Project checkbox)
    
    # Status and audit fields
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(64))
    updated_by = db.Column(db.String(64))
    
    def get_consortium_ids(self):
        """Get list of consortium IDs this project belongs to"""
        if self.consortium_ids:
            return json.loads(self.consortium_ids)
        return []
    
    def set_consortium_ids(self, consortium_id_list):
        """Set consortium IDs from a list"""
        if consortium_id_list:
            # Filter out empty strings
            filtered_ids = [cid for cid in consortium_id_list if cid and cid != '']
            self.consortium_ids = json.dumps(filtered_ids)
        else:
            self.consortium_ids = None
    
    def get_rfpo_viewer_users(self):
        """Get list of RFPO viewer user IDs for this project"""
        if self.rfpo_viewer_user_ids:
            return json.loads(self.rfpo_viewer_user_ids)
        return []
    
    def set_rfpo_viewer_users(self, user_ids):
        """Set RFPO viewer user IDs from a list"""
        if user_ids:
            # Filter out empty strings and 'none' values
            filtered_ids = [uid for uid in user_ids if uid and uid != '']
            self.rfpo_viewer_user_ids = json.dumps(filtered_ids)
        else:
            self.rfpo_viewer_user_ids = None
    
    def is_multi_consortium(self):
        """Check if project belongs to multiple consortiums"""
        return len(self.get_consortium_ids()) > 1
    
    def get_project_type(self):
        """Get human-readable project type"""
        types = []
        if self.gov_funded:
            types.append("Government Funded")
        if self.uni_project:
            types.append("University Project")
        if not types:
            types.append("Private/Other")
        return ", ".join(types)
    
    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'ref': self.ref,
            'name': self.name,
            'description': self.description,
            'consortium_ids': self.get_consortium_ids(),
            'team_record_id': self.team_record_id,
            'rfpo_viewer_user_ids': self.get_rfpo_viewer_users(),
            'gov_funded': self.gov_funded,
            'uni_project': self.uni_project,
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'updated_by': self.updated_by,
            'is_multi_consortium': self.is_multi_consortium(),
            'project_type': self.get_project_type(),
            'consortium_count': len(self.get_consortium_ids()),
            'viewer_count': len(self.get_rfpo_viewer_users())
        }
    
    def __repr__(self):
        consortium_info = f" ({len(self.get_consortium_ids())} consortiums)" if self.get_consortium_ids() else " (No consortium)"
        return f'<Project {self.project_id} ({self.ref}): {self.name}{consortium_info}>'

class Vendor(db.Model):
    """Vendor model for managing approved vendors"""
    __tablename__ = 'vendors'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.String(32), unique=True, nullable=False)  # External vendor ID (e.g., "00000865")
    
    # Basic Information (matching form field names)
    company_name = db.Column(db.String(255), nullable=False)  # vendor_company_name
    
    # Vendor Status
    status = db.Column(db.String(20), default='live')  # vendor_status (live/withheld)
    
    # Vendor Classification
    certs_reps = db.Column(db.Boolean, default=False)  # vendor_certs (Certs & Reps checkbox)
    cert_date = db.Column(db.Date)  # vendor_cert_date (certification creation date)
    cert_expire_date = db.Column(db.Date)  # vendor_cert_expire_date (certification expiration)
    is_university = db.Column(db.Boolean, default=False)  # vendor_uni (Uni checkbox - disabled in form)
    vendor_type = db.Column(db.Integer, default=0)  # vendor_type2 (0=None, 1=University, 2=Small Business, 3=Non Profit)
    
    # Consortium Approvals (stored as JSON for the checkbox fields)
    approved_consortiums = db.Column(db.Text)  # consort_0 through consort_9 checkboxes as JSON array
    
    # One-time vendor project association
    onetime_project_id = db.Column(db.String(32), nullable=True)  # vendor_onetime (project_id)
    
    # Default Contact Information
    contact_name = db.Column(db.String(255))  # vendor_contact_name
    contact_dept = db.Column(db.String(255))  # vendor_contact_dept
    contact_tel = db.Column(db.String(255))  # vendor_contact_tel
    contact_fax = db.Column(db.String(50))   # vendor_contact_fax
    contact_address = db.Column(db.Text)     # vendor_address (textarea)
    contact_city = db.Column(db.String(255)) # vendor_city
    contact_state = db.Column(db.String(2))  # vendor_state (state dropdown)
    contact_zip = db.Column(db.String(50))   # vendor_postal
    contact_country = db.Column(db.String(50)) # vendor_country
    
    # Status and audit fields
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(64))
    updated_by = db.Column(db.String(64))
    
    def get_approved_consortiums(self):
        """Get list of consortium abbreviations this vendor is approved for"""
        if self.approved_consortiums:
            return json.loads(self.approved_consortiums)
        return []
    
    def set_approved_consortiums(self, consortium_list):
        """Set approved consortiums from a list of abbreviations"""
        if consortium_list:
            # Filter out empty strings
            filtered_consortiums = [c for c in consortium_list if c and c != '']
            self.approved_consortiums = json.dumps(filtered_consortiums)
        else:
            self.approved_consortiums = None
    
    def is_approved_for_consortium(self, consortium_abbrev):
        """Check if vendor is approved for a specific consortium"""
        return consortium_abbrev in self.get_approved_consortiums()
    
    def get_vendor_type_display(self):
        """Get human-readable vendor type"""
        type_map = {
            0: "None",
            1: "University", 
            2: "Small Business",
            3: "Non Profit"
        }
        return type_map.get(self.vendor_type, "Unknown")
    
    def is_onetime_vendor(self):
        """Check if this is a one-time vendor"""
        return self.onetime_project_id is not None
    
    def get_full_contact_address(self):
        """Get formatted full contact address"""
        address_parts = []
        if self.contact_address:
            address_parts.append(self.contact_address)
        if self.contact_city:
            city_state_zip = self.contact_city
            if self.contact_state:
                city_state_zip += f", {self.contact_state}"
            if self.contact_zip:
                city_state_zip += f" {self.contact_zip}"
            address_parts.append(city_state_zip)
        if self.contact_country:
            address_parts.append(self.contact_country)
        return "\n".join(address_parts)
    
    def to_dict(self):
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'company_name': self.company_name,
            'status': self.status,
            'certs_reps': self.certs_reps,
            'cert_date': self.cert_date.isoformat() if self.cert_date else None,
            'cert_expire_date': self.cert_expire_date.isoformat() if self.cert_expire_date else None,
            'is_university': self.is_university,
            'vendor_type': self.vendor_type,
            'vendor_type_display': self.get_vendor_type_display(),
            'approved_consortiums': self.get_approved_consortiums(),
            'onetime_project_id': self.onetime_project_id,
            'contact_name': self.contact_name,
            'contact_dept': self.contact_dept,
            'contact_tel': self.contact_tel,
            'contact_fax': self.contact_fax,
            'contact_address': self.contact_address,
            'contact_city': self.contact_city,
            'contact_state': self.contact_state,
            'contact_zip': self.contact_zip,
            'contact_country': self.contact_country,
            'full_contact_address': self.get_full_contact_address(),
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'updated_by': self.updated_by,
            'is_onetime_vendor': self.is_onetime_vendor(),
            'consortium_count': len(self.get_approved_consortiums()),
            'site_count': len(self.sites) if self.sites else 0
        }
    
    def __repr__(self):
        status_info = f" ({self.status})" if self.status != 'live' else ""
        onetime_info = " [One-time]" if self.is_onetime_vendor() else ""
        return f'<Vendor {self.vendor_id}: {self.company_name}{status_info}{onetime_info}>'

class VendorSite(db.Model):
    """Vendor site/contact model for managing multiple vendor contacts"""
    __tablename__ = 'vendor_sites'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_site_id = db.Column(db.String(32), unique=True, nullable=False)  # External site ID (e.g., "00000905")
    
    # Vendor association
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False)
    
    # Contact Information (matching form field names)
    contact_name = db.Column(db.String(255))  # vendor_site_contact_name
    contact_dept = db.Column(db.String(255))  # vendor_site_contact_dept
    contact_tel = db.Column(db.String(255))   # vendor_site_contact_tel
    contact_fax = db.Column(db.String(50))    # vendor_site_contact_fax
    contact_address = db.Column(db.Text)      # vendor_site_address (textarea)
    contact_city = db.Column(db.String(255))  # vendor_site_city
    contact_state = db.Column(db.String(2))   # vendor_site_state (state dropdown)
    contact_zip = db.Column(db.String(50))    # vendor_site_postal
    contact_country = db.Column(db.String(50)) # vendor_site_country
    
    # Status and audit fields
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(64))
    updated_by = db.Column(db.String(64))
    
    # Relationships
    vendor = db.relationship('Vendor', backref=db.backref('sites', lazy=True, cascade='all, delete-orphan'))
    
    def get_full_contact_address(self):
        """Get formatted full contact address"""
        address_parts = []
        if self.contact_address:
            address_parts.append(self.contact_address)
        if self.contact_city:
            city_state_zip = self.contact_city
            if self.contact_state:
                city_state_zip += f", {self.contact_state}"
            if self.contact_zip:
                city_state_zip += f" {self.contact_zip}"
            address_parts.append(city_state_zip)
        if self.contact_country:
            address_parts.append(self.contact_country)
        return "\n".join(address_parts)
    
    def to_dict(self):
        return {
            'id': self.id,
            'vendor_site_id': self.vendor_site_id,
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.company_name if self.vendor else None,
            'contact_name': self.contact_name,
            'contact_dept': self.contact_dept,
            'contact_tel': self.contact_tel,
            'contact_fax': self.contact_fax,
            'contact_address': self.contact_address,
            'contact_city': self.contact_city,
            'contact_state': self.contact_state,
            'contact_zip': self.contact_zip,
            'contact_country': self.contact_country,
            'full_contact_address': self.get_full_contact_address(),
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'updated_by': self.updated_by
        }
    
    def __repr__(self):
        vendor_name = self.vendor.company_name if self.vendor else "Unknown Vendor"
        return f'<VendorSite {self.vendor_site_id}: {self.contact_name} @ {vendor_name}>'

class PDFPositioning(db.Model):
    """PDF Positioning configuration for consortium-specific templates"""
    __tablename__ = 'pdf_positioning'
    
    id = db.Column(db.Integer, primary_key=True)
    consortium_id = db.Column(db.String(32), nullable=False)  # e.g., "00000014" for USCAR
    template_name = db.Column(db.String(100), nullable=False)  # e.g., "po_template"
    
    # Field positioning data stored as JSON
    # Each field has: {"x": 123, "y": 456, "font_size": 9, "font_weight": "normal", "visible": true}
    positioning_data = db.Column(db.Text)  # JSON string with all field positions
    
    # Template metadata
    template_width = db.Column(db.Integer, default=612)  # PDF width in points
    template_height = db.Column(db.Integer, default=792)  # PDF height in points
    
    # Status and audit fields
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(64))
    updated_by = db.Column(db.String(64))
    
    def get_positioning_data(self):
        """Get positioning data as Python dict"""
        if self.positioning_data:
            try:
                return json.loads(self.positioning_data)
            except:
                return {}
        return {}
    
    def set_positioning_data(self, data_dict):
        """Set positioning data from Python dict"""
        if data_dict:
            self.positioning_data = json.dumps(data_dict)
        else:
            self.positioning_data = None
    
    def get_field_position(self, field_name):
        """Get position for a specific field"""
        data = self.get_positioning_data()
        return data.get(field_name, {})
    
    def set_field_position(self, field_name, x, y, font_size=9, font_weight="normal", visible=True):
        """Set position for a specific field"""
        data = self.get_positioning_data()
        data[field_name] = {
            "x": x,
            "y": y, 
            "font_size": font_size,
            "font_weight": font_weight,
            "visible": visible
        }
        self.set_positioning_data(data)
    
    def to_dict(self):
        return {
            'id': self.id,
            'consortium_id': self.consortium_id,
            'template_name': self.template_name,
            'positioning_data': self.get_positioning_data(),
            'template_width': self.template_width,
            'template_height': self.template_height,
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'updated_by': self.updated_by
        }
    
    def __repr__(self):
        return f'<PDFPositioning {self.consortium_id}:{self.template_name}>'

class List(db.Model):
    """List model for key-value configuration and lookup data"""
    __tablename__ = 'lists'
    
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.String(32), unique=True, nullable=False)  # External list ID (e.g., "0000000021")
    
    # Configuration fields (matching form field names)
    type = db.Column(db.String(255), nullable=False)  # lists_type (e.g., "adminlevel")
    key = db.Column(db.String(255), nullable=False)   # lists_key (e.g., "GOD")
    value = db.Column(db.String(255), nullable=False) # lists_value (e.g., "Super Admin")
    
    # Status and audit fields
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(64))
    updated_by = db.Column(db.String(64))
    
    # Unique constraint to prevent duplicate type-key combinations
    __table_args__ = (
        db.UniqueConstraint('type', 'key', name='uq_list_type_key'),
    )
    
    @classmethod
    def get_by_type(cls, list_type):
        """Get all list items of a specific type"""
        return cls.query.filter_by(type=list_type, active=True).all()
    
    @classmethod
    def get_value_by_key(cls, list_type, key):
        """Get the value for a specific type-key combination"""
        list_item = cls.query.filter_by(type=list_type, key=key, active=True).first()
        return list_item.value if list_item else None
    
    @classmethod
    def get_key_value_pairs(cls, list_type):
        """Get all key-value pairs for a specific type as a dictionary"""
        items = cls.get_by_type(list_type)
        return {item.key: item.value for item in items}
    
    def to_dict(self):
        return {
            'id': self.id,
            'list_id': self.list_id,
            'type': self.type,
            'key': self.key,
            'value': self.value,
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'updated_by': self.updated_by
        }
    
    def __repr__(self):
        return f'<List {self.list_id} ({self.type}): {self.key} = {self.value}>'

class RFPOApprovalWorkflow(db.Model):
    """RFPO Approval Workflow Templates for Consortiums, Teams, and Projects"""
    __tablename__ = 'rfpo_approval_workflows'
    
    id = db.Column(db.Integer, primary_key=True)
    workflow_id = db.Column(db.String(32), unique=True, nullable=False)  # External workflow ID
    
    # Workflow Information
    name = db.Column(db.String(255), nullable=False)  # Workflow name (e.g., "USCAR Standard Approval")
    description = db.Column(db.Text)  # Workflow description
    version = db.Column(db.String(20), default='1.0')  # Workflow version
    
    # Workflow Type and Associations
    workflow_type = db.Column(db.String(20), nullable=False, default='consortium')  # 'consortium', 'team', 'project'
    consortium_id = db.Column(db.String(32), nullable=True)  # Consortium consort_id (nullable for team/project workflows)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)  # Team ID for team workflows
    project_id = db.Column(db.String(32), nullable=True)  # Project ID for project workflows
    
    # Status and Control
    is_active = db.Column(db.Boolean, default=False)  # Only one workflow can be active per entity
    is_template = db.Column(db.Boolean, default=True)  # True for templates, False for instances
    
    # Audit fields
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(64))
    updated_by = db.Column(db.String(64))
    
    # Relationships
    stages = db.relationship('RFPOApprovalStage', backref='workflow', lazy=True, cascade='all, delete-orphan', order_by='RFPOApprovalStage.stage_order')
    instances = db.relationship('RFPOApprovalInstance', backref='template_workflow', lazy=True)
    team = db.relationship('Team', backref=db.backref('approval_workflows', lazy=True))
    
    # Indexes for efficient querying
    __table_args__ = (
        db.Index('idx_consortium_type_active', 'consortium_id', 'workflow_type', 'is_active'),
        db.Index('idx_team_type_active', 'team_id', 'workflow_type', 'is_active'),
        db.Index('idx_project_type_active', 'project_id', 'workflow_type', 'is_active'),
    )
    
    def activate(self):
        """Activate this workflow and deactivate others for the same entity"""
        if self.workflow_type == 'consortium':
            # Deactivate all other consortium workflows
            db.session.query(RFPOApprovalWorkflow).filter_by(
                consortium_id=self.consortium_id,
                workflow_type='consortium',
                is_template=True
            ).update({'is_active': False})
        elif self.workflow_type == 'team':
            # Deactivate all other team workflows
            db.session.query(RFPOApprovalWorkflow).filter_by(
                team_id=self.team_id,
                workflow_type='team',
                is_template=True
            ).update({'is_active': False})
        elif self.workflow_type == 'project':
            # Deactivate all other project workflows
            db.session.query(RFPOApprovalWorkflow).filter_by(
                project_id=self.project_id,
                workflow_type='project',
                is_template=True
            ).update({'is_active': False})
        
        # Activate this workflow
        self.is_active = True
        self.updated_at = datetime.utcnow()
    
    def get_total_stages(self):
        """Get total number of stages in this workflow"""
        return len(self.stages)
    
    def get_total_steps(self):
        """Get total number of approval steps across all stages"""
        return sum(len(stage.steps) for stage in self.stages)
    
    def get_bracket_coverage(self):
        """Get list of budget brackets covered by this workflow"""
        return [stage.budget_bracket_key for stage in self.stages if stage.budget_bracket_key]
    
    def get_entity_name(self):
        """Get the name of the entity this workflow belongs to"""
        if self.workflow_type == 'consortium':
            consortium = Consortium.query.filter_by(consort_id=self.consortium_id).first()
            return consortium.name if consortium else self.consortium_id
        elif self.workflow_type == 'team':
            return self.team.name if self.team else f"Team {self.team_id}"
        elif self.workflow_type == 'project':
            project = Project.query.filter_by(project_id=self.project_id).first()
            return project.name if project else self.project_id
        return "Unknown"
    
    def get_entity_identifier(self):
        """Get the identifier of the entity this workflow belongs to"""
        if self.workflow_type == 'consortium':
            return self.consortium_id
        elif self.workflow_type == 'team':
            return str(self.team_id)
        elif self.workflow_type == 'project':
            return self.project_id
        return "Unknown"
    
    def to_dict(self):
        return {
            'id': self.id,
            'workflow_id': self.workflow_id,
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'workflow_type': self.workflow_type,
            'consortium_id': self.consortium_id,
            'team_id': self.team_id,
            'project_id': self.project_id,
            'entity_name': self.get_entity_name(),
            'entity_identifier': self.get_entity_identifier(),
            'is_active': self.is_active,
            'is_template': self.is_template,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'updated_by': self.updated_by,
            'total_stages': self.get_total_stages(),
            'total_steps': self.get_total_steps(),
            'bracket_coverage': self.get_bracket_coverage()
        }
    
    def __repr__(self):
        status = "ACTIVE" if self.is_active else "INACTIVE"
        return f'<RFPOApprovalWorkflow {self.workflow_id} ({self.workflow_type.upper()}): {self.name} [{status}]>'

class RFPOApprovalStage(db.Model):
    """Budget Bracket Stages within RFPO Approval Workflows"""
    __tablename__ = 'rfpo_approval_stages'
    
    id = db.Column(db.Integer, primary_key=True)
    stage_id = db.Column(db.String(32), unique=True, nullable=False)  # External stage ID
    
    # Stage Information
    stage_name = db.Column(db.String(255), nullable=False)  # Stage name (e.g., "Under $5,000")
    stage_order = db.Column(db.Integer, nullable=False)  # Order of this stage in workflow (1, 2, 3...)
    description = db.Column(db.Text)  # Stage description
    
    # Budget Bracket Association
    budget_bracket_key = db.Column(db.String(255), nullable=False)  # References RFPO_BRACK key from Lists
    budget_bracket_amount = db.Column(db.Numeric(12, 2), nullable=False)  # Cached amount for performance
    
    # Workflow Association
    workflow_id = db.Column(db.Integer, db.ForeignKey('rfpo_approval_workflows.id'), nullable=False)
    
    # Stage Configuration
    requires_all_steps = db.Column(db.Boolean, default=True)  # True: all steps must approve, False: any step can approve
    is_parallel = db.Column(db.Boolean, default=False)  # True: steps can approve in parallel, False: sequential
    
    # Required Document Types (stored as JSON array of doc_types keys)
    required_document_types = db.Column(db.Text)  # JSON array of document type keys from doc_types list
    
    # Audit fields
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    steps = db.relationship('RFPOApprovalStep', backref='stage', lazy=True, cascade='all, delete-orphan', order_by='RFPOApprovalStep.step_order')
    
    # Unique constraint: one stage per bracket per workflow
    __table_args__ = (
        db.UniqueConstraint('workflow_id', 'budget_bracket_key', name='uq_workflow_bracket'),
        db.UniqueConstraint('workflow_id', 'stage_order', name='uq_workflow_stage_order'),
    )
    
    def get_total_steps(self):
        """Get total number of approval steps in this stage"""
        return len(self.steps)
    
    def get_required_approvers(self):
        """Get list of primary approvers for this stage"""
        return [step.primary_approver_id for step in self.steps if step.primary_approver_id]
    
    def get_backup_approvers(self):
        """Get list of backup approvers for this stage"""
        return [step.backup_approver_id for step in self.steps if step.backup_approver_id]
    
    def get_required_document_types(self):
        """Get list of required document type keys"""
        if self.required_document_types:
            try:
                return json.loads(self.required_document_types)
            except:
                return []
        return []
    
    def set_required_document_types(self, doc_type_keys):
        """Set required document types from a list of keys"""
        if doc_type_keys:
            # Filter out empty strings
            filtered_keys = [key for key in doc_type_keys if key and key.strip()]
            self.required_document_types = json.dumps(filtered_keys)
        else:
            self.required_document_types = None
    
    def get_required_document_names(self):
        """Get list of required document type names (for display)"""
        from models import List  # Import here to avoid circular imports
        doc_keys = self.get_required_document_types()
        if not doc_keys:
            return []
        
        doc_names = []
        for key in doc_keys:
            doc_item = List.query.filter_by(type='doc_types', key=key, active=True).first()
            if doc_item and doc_item.value.strip():  # Only include non-empty values
                doc_names.append(doc_item.value)
        return doc_names
    
    def to_dict(self):
        return {
            'id': self.id,
            'stage_id': self.stage_id,
            'stage_name': self.stage_name,
            'stage_order': self.stage_order,
            'description': self.description,
            'budget_bracket_key': self.budget_bracket_key,
            'budget_bracket_amount': float(self.budget_bracket_amount) if self.budget_bracket_amount else 0.00,
            'workflow_id': self.workflow_id,
            'requires_all_steps': self.requires_all_steps,
            'is_parallel': self.is_parallel,
            'required_document_types': self.get_required_document_types(),
            'required_document_names': self.get_required_document_names(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'total_steps': self.get_total_steps(),
            'required_approvers': self.get_required_approvers(),
            'backup_approvers': self.get_backup_approvers()
        }
    
    def __repr__(self):
        return f'<RFPOApprovalStage {self.stage_id}: {self.stage_name} (${self.budget_bracket_amount})>'

class RFPOApprovalStep(db.Model):
    """Individual Approval Steps within Budget Bracket Stages"""
    __tablename__ = 'rfpo_approval_steps'
    
    id = db.Column(db.Integer, primary_key=True)
    step_id = db.Column(db.String(32), unique=True, nullable=False)  # External step ID
    
    # Step Information
    step_name = db.Column(db.String(255), nullable=False)  # Step name (e.g., "Technical Review")
    step_order = db.Column(db.Integer, nullable=False)  # Order of this step in stage (1, 2, 3...)
    description = db.Column(db.Text)  # Step description
    
    # RFPO_APPRO Association
    approval_type_key = db.Column(db.String(255), nullable=False)  # References RFPO_APPRO key from Lists
    approval_type_name = db.Column(db.String(255), nullable=False)  # Cached name for performance
    
    # Stage Association
    stage_id = db.Column(db.Integer, db.ForeignKey('rfpo_approval_stages.id'), nullable=False)
    
    # Approver Configuration
    primary_approver_id = db.Column(db.String(32), nullable=False)  # User record_id of primary approver
    backup_approver_id = db.Column(db.String(32), nullable=True)  # User record_id of backup approver (optional)
    
    # Step Configuration
    is_required = db.Column(db.Boolean, default=True)  # True: step must be completed, False: optional
    timeout_days = db.Column(db.Integer, default=5)  # Days before step times out
    auto_escalate = db.Column(db.Boolean, default=False)  # Auto-escalate to backup after timeout
    
    # Audit fields
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint: one step per order per stage (but allow multiple of same approval type)
    __table_args__ = (
        db.UniqueConstraint('stage_id', 'step_order', name='uq_stage_step_order'),
    )
    
    def get_primary_approver(self):
        """Get primary approver user object"""
        return User.query.filter_by(record_id=self.primary_approver_id, active=True).first()
    
    def get_backup_approver(self):
        """Get backup approver user object"""
        if self.backup_approver_id:
            return User.query.filter_by(record_id=self.backup_approver_id, active=True).first()
        return None
    
    def to_dict(self):
        primary_approver = self.get_primary_approver()
        backup_approver = self.get_backup_approver()
        
        return {
            'id': self.id,
            'step_id': self.step_id,
            'step_name': self.step_name,
            'step_order': self.step_order,
            'description': self.description,
            'approval_type_key': self.approval_type_key,
            'approval_type_name': self.approval_type_name,
            'stage_id': self.stage_id,
            'primary_approver_id': self.primary_approver_id,
            'primary_approver_name': primary_approver.get_display_name() if primary_approver else None,
            'backup_approver_id': self.backup_approver_id,
            'backup_approver_name': backup_approver.get_display_name() if backup_approver else None,
            'is_required': self.is_required,
            'timeout_days': self.timeout_days,
            'auto_escalate': self.auto_escalate,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<RFPOApprovalStep {self.step_id}: {self.step_name} ({self.approval_type_name})>'

class RFPOApprovalInstance(db.Model):
    """Workflow Instance created when RFPO is submitted for approval"""
    __tablename__ = 'rfpo_approval_instances'
    
    id = db.Column(db.Integer, primary_key=True)
    instance_id = db.Column(db.String(32), unique=True, nullable=False)  # External instance ID
    
    # RFPO Association
    rfpo_id = db.Column(db.Integer, db.ForeignKey('rfpos.id'), nullable=False)
    
    # Workflow Template Association (snapshot at time of creation)
    template_workflow_id = db.Column(db.Integer, db.ForeignKey('rfpo_approval_workflows.id'), nullable=False)
    
    # Instance Information
    workflow_name = db.Column(db.String(255), nullable=False)  # Snapshot of workflow name
    workflow_version = db.Column(db.String(20), nullable=False)  # Snapshot of workflow version
    consortium_id = db.Column(db.String(32), nullable=False)  # Snapshot of consortium ID
    
    # Instance Status
    current_stage_order = db.Column(db.Integer, default=1)  # Current stage being processed
    current_step_order = db.Column(db.Integer, default=1)  # Current step being processed
    overall_status = db.Column(db.String(32), default='draft')  # Uses RFPO_STATU values
    
    # Instance Configuration (snapshot from template)
    instance_data = db.Column(db.Text)  # JSON snapshot of workflow configuration at creation time
    
    # Timing
    submitted_at = db.Column(db.DateTime)  # When RFPO was submitted for approval
    completed_at = db.Column(db.DateTime)  # When approval process completed
    
    # Audit fields
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(64))
    
    # Relationships
    rfpo = db.relationship('RFPO', backref=db.backref('approval_instance', uselist=False))
    actions = db.relationship('RFPOApprovalAction', backref='instance', lazy=True, cascade='all, delete-orphan', order_by='RFPOApprovalAction.created_at')
    
    def get_instance_data(self):
        """Get workflow configuration snapshot as Python dict"""
        if self.instance_data:
            try:
                return json.loads(self.instance_data)
            except:
                return {}
        return {}
    
    def set_instance_data(self, data_dict):
        """Set workflow configuration snapshot from Python dict"""
        if data_dict:
            self.instance_data = json.dumps(data_dict)
        else:
            self.instance_data = None
    
    def get_current_stage(self):
        """Get current stage information from snapshot"""
        data = self.get_instance_data()
        stages = data.get('stages', [])
        for stage in stages:
            if stage.get('stage_order') == self.current_stage_order:
                return stage
        return None
    
    def get_current_step(self):
        """Get current step information from snapshot"""
        current_stage = self.get_current_stage()
        if current_stage:
            steps = current_stage.get('steps', [])
            for step in steps:
                if step.get('step_order') == self.current_step_order:
                    return step
        return None
    
    def get_pending_actions(self):
        """Get list of pending approval actions"""
        return [action for action in self.actions if action.status == 'pending']
    
    def get_completed_actions(self):
        """Get list of completed approval actions"""
        return [action for action in self.actions if action.status in ['approved', 'conditional', 'refused']]
    
    def is_complete(self):
        """Check if approval workflow is complete"""
        return self.overall_status in ['approved', 'refused']
    
    def advance_to_next_step(self):
        """Advance workflow to next step or stage"""
        current_stage = self.get_current_stage()
        if current_stage:
            steps = current_stage.get('steps', [])
            if self.current_step_order < len(steps):
                # Move to next step in current stage
                self.current_step_order += 1
            else:
                # Move to next stage
                data = self.get_instance_data()
                stages = data.get('stages', [])
                if self.current_stage_order < len(stages):
                    self.current_stage_order += 1
                    self.current_step_order = 1
                else:
                    # Workflow complete
                    self.overall_status = 'approved'
                    self.completed_at = datetime.utcnow()
    
    def to_dict(self):
        return {
            'id': self.id,
            'instance_id': self.instance_id,
            'rfpo_id': self.rfpo_id,
            'template_workflow_id': self.template_workflow_id,
            'workflow_name': self.workflow_name,
            'workflow_version': self.workflow_version,
            'consortium_id': self.consortium_id,
            'current_stage_order': self.current_stage_order,
            'current_step_order': self.current_step_order,
            'overall_status': self.overall_status,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'pending_actions_count': len(self.get_pending_actions()),
            'completed_actions_count': len(self.get_completed_actions()),
            'is_complete': self.is_complete(),
            'current_stage': self.get_current_stage(),
            'current_step': self.get_current_step()
        }
    
    def __repr__(self):
        return f'<RFPOApprovalInstance {self.instance_id}: RFPO-{self.rfpo_id} [{self.overall_status}]>'

class RFPOApprovalAction(db.Model):
    """Individual Approval Actions taken by approvers"""
    __tablename__ = 'rfpo_approval_actions'
    
    id = db.Column(db.Integer, primary_key=True)
    action_id = db.Column(db.String(32), unique=True, nullable=False)  # External action ID
    
    # Instance Association
    instance_id = db.Column(db.Integer, db.ForeignKey('rfpo_approval_instances.id'), nullable=False)
    
    # Action Context (snapshot from instance at time of action)
    stage_order = db.Column(db.Integer, nullable=False)  # Which stage this action is for
    step_order = db.Column(db.Integer, nullable=False)  # Which step this action is for
    stage_name = db.Column(db.String(255), nullable=False)  # Snapshot of stage name
    step_name = db.Column(db.String(255), nullable=False)  # Snapshot of step name
    approval_type_key = db.Column(db.String(255), nullable=False)  # Snapshot of approval type
    
    # Approver Information
    approver_id = db.Column(db.String(32), nullable=False)  # User record_id who took this action
    approver_name = db.Column(db.String(255), nullable=False)  # Snapshot of approver name
    is_backup_approver = db.Column(db.Boolean, default=False)  # True if backup approver took action
    
    # Action Details
    status = db.Column(db.String(32), nullable=False)  # Uses RFPO_STATU values: approved, conditional, refused, pending
    comments = db.Column(db.Text)  # Approver comments
    conditions = db.Column(db.Text)  # Conditional approval conditions (if status = conditional)
    
    # Timing
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)  # When action was assigned
    due_date = db.Column(db.DateTime)  # When action is due
    completed_at = db.Column(db.DateTime)  # When action was completed
    
    # Escalation
    is_escalated = db.Column(db.Boolean, default=False)  # True if action was escalated
    escalated_at = db.Column(db.DateTime)  # When action was escalated
    escalation_reason = db.Column(db.String(255))  # Reason for escalation
    
    # Audit fields
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_approver(self):
        """Get approver user object"""
        return User.query.filter_by(record_id=self.approver_id, active=True).first()
    
    def is_pending(self):
        """Check if action is pending"""
        return self.status == 'pending'
    
    def is_approved(self):
        """Check if action is approved"""
        return self.status == 'approved'
    
    def is_conditional(self):
        """Check if action is conditionally approved"""
        return self.status == 'conditional'
    
    def is_refused(self):
        """Check if action is refused"""
        return self.status == 'refused'
    
    def is_overdue(self):
        """Check if action is overdue"""
        if self.due_date and self.status == 'pending':
            return datetime.utcnow() > self.due_date
        return False
    
    def complete_action(self, status, comments=None, conditions=None, approver_id=None):
        """Complete this approval action"""
        self.status = status
        self.comments = comments
        self.conditions = conditions
        self.completed_at = datetime.utcnow()
        
        if approver_id:
            # Update approver info if different (backup approver scenario)
            approver = User.query.filter_by(record_id=approver_id, active=True).first()
            if approver:
                self.approver_id = approver_id
                self.approver_name = approver.get_display_name()
                self.is_backup_approver = (approver_id != self.approver_id)
    
    def escalate_action(self, reason=None):
        """Escalate this action to backup approver"""
        self.is_escalated = True
        self.escalated_at = datetime.utcnow()
        self.escalation_reason = reason or 'Automatic escalation due to timeout'
    
    def to_dict(self):
        return {
            'id': self.id,
            'action_id': self.action_id,
            'instance_id': self.instance_id,
            'stage_order': self.stage_order,
            'step_order': self.step_order,
            'stage_name': self.stage_name,
            'step_name': self.step_name,
            'approval_type_key': self.approval_type_key,
            'approver_id': self.approver_id,
            'approver_name': self.approver_name,
            'is_backup_approver': self.is_backup_approver,
            'status': self.status,
            'comments': self.comments,
            'conditions': self.conditions,
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'is_escalated': self.is_escalated,
            'escalated_at': self.escalated_at.isoformat() if self.escalated_at else None,
            'escalation_reason': self.escalation_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_pending': self.is_pending(),
            'is_approved': self.is_approved(),
            'is_conditional': self.is_conditional(),
            'is_refused': self.is_refused(),
            'is_overdue': self.is_overdue()
        }
    
    def __repr__(self):
        return f'<RFPOApprovalAction {self.action_id}: {self.step_name} by {self.approver_name} [{self.status}]>'
