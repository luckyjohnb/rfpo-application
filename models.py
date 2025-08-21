from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class Consortium(db.Model):
    """Consortium model for managing different consortiums"""
    __tablename__ = 'consortiums'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False, unique=True)
    abbrev = db.Column(db.String(32), nullable=False, unique=True)
    
    # Configuration flags
    require_approved_vendor_list = db.Column(db.Boolean, default=False)
    non_government_project_id = db.Column(db.Integer)  # Reference to non-gov project if selected
    
    # User permissions (stored as comma-separated user IDs)
    viewer_user_ids = db.Column(db.Text)  # Users who can view all RFPOs for this consortium
    limited_admin_user_ids = db.Column(db.Text)  # Users with limited admin abilities
    
    # Contact and document delivery information
    invoicing_address = db.Column(db.Text)
    
    # Fax information
    fax_recipient_name = db.Column(db.String(256))
    fax_number = db.Column(db.String(32))
    
    # Email information
    email_recipient_name = db.Column(db.String(256))
    email_address = db.Column(db.String(256))
    
    # Postal information
    postal_recipient_name = db.Column(db.String(256))
    postal_address = db.Column(db.Text)
    
    # Completed PO email
    completed_po_email = db.Column(db.String(256))
    
    # Status and audit fields
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(64))
    updated_by = db.Column(db.String(64))
    
    # Relationships
    teams = db.relationship('Team', backref='consortium', lazy=True)
    
    def get_viewer_users(self):
        """Get list of viewer user IDs"""
        if self.viewer_user_ids:
            return [uid.strip() for uid in self.viewer_user_ids.split(',') if uid.strip()]
        return []
    
    def set_viewer_users(self, user_ids):
        """Set viewer user IDs from a list"""
        if user_ids:
            self.viewer_user_ids = ','.join(str(uid) for uid in user_ids)
        else:
            self.viewer_user_ids = None
    
    def get_limited_admin_users(self):
        """Get list of limited admin user IDs"""
        if self.limited_admin_user_ids:
            return [uid.strip() for uid in self.limited_admin_user_ids.split(',') if uid.strip()]
        return []
    
    def set_limited_admin_users(self, user_ids):
        """Set limited admin user IDs from a list"""
        if user_ids:
            self.limited_admin_user_ids = ','.join(str(uid) for uid in user_ids)
        else:
            self.limited_admin_user_ids = None
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'abbrev': self.abbrev,
            'require_approved_vendor_list': self.require_approved_vendor_list,
            'non_government_project_id': self.non_government_project_id,
            'viewer_user_ids': self.get_viewer_users(),
            'limited_admin_user_ids': self.get_limited_admin_users(),
            'invoicing_address': self.invoicing_address,
            'fax_recipient_name': self.fax_recipient_name,
            'fax_number': self.fax_number,
            'email_recipient_name': self.email_recipient_name,
            'email_address': self.email_address,
            'postal_recipient_name': self.postal_recipient_name,
            'postal_address': self.postal_address,
            'completed_po_email': self.completed_po_email,
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'updated_by': self.updated_by,
            'team_count': len(self.teams) if self.teams else 0
        }
    
    def __repr__(self):
        return f'<Consortium {self.abbrev}: {self.title}>'

class RFPO(db.Model):
    """Request for Purchase Order model"""
    __tablename__ = 'rfpos'
    
    id = db.Column(db.Integer, primary_key=True)
    rfpo_id = db.Column(db.String(64), unique=True, nullable=False)  # e.g., RFPO-001
    title = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text)
    vendor = db.Column(db.String(128))
    due_date = db.Column(db.Date)
    status = db.Column(db.String(32), default='Draft')  # Draft, In Progress, Completed, etc.
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    created_by = db.Column(db.String(64), nullable=False)
    updated_by = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    team = db.relationship('Team', backref=db.backref('rfpos', lazy=True))
    files = db.relationship('UploadedFile', backref='rfpo', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'rfpo_id': self.rfpo_id,
            'title': self.title,
            'description': self.description,
            'vendor': self.vendor,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'status': self.status,
            'team_id': self.team_id,
            'created_by': self.created_by,
            'updated_by': self.updated_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'file_count': len(self.files) if self.files else 0
        }

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
    name = db.Column(db.String(128), nullable=False)  # Team Name
    description = db.Column(db.Text)  # Description
    abbrev = db.Column(db.String(32), nullable=False, unique=True)  # Abbrev
    
    # Part of Consortium (optional - can be "none")
    consortium_id = db.Column(db.Integer, db.ForeignKey('consortiums.id'), nullable=True)
    
    # Team-level user permissions
    viewer_user_ids = db.Column(db.Text)  # Users who can view all RFPOs for this team
    limited_admin_user_ids = db.Column(db.Text)  # Users with limited admin abilities on team
    
    # Status and audit fields
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(64))
    updated_by = db.Column(db.String(64))
    
    def get_viewer_users(self):
        """Get list of viewer user IDs for this team"""
        if self.viewer_user_ids:
            return [uid.strip() for uid in self.viewer_user_ids.split(',') if uid.strip()]
        return []
    
    def set_viewer_users(self, user_ids):
        """Set viewer user IDs from a list"""
        if user_ids:
            self.viewer_user_ids = ','.join(str(uid) for uid in user_ids)
        else:
            self.viewer_user_ids = None
    
    def get_limited_admin_users(self):
        """Get list of limited admin user IDs for this team"""
        if self.limited_admin_user_ids:
            return [uid.strip() for uid in self.limited_admin_user_ids.split(',') if uid.strip()]
        return []
    
    def set_limited_admin_users(self, user_ids):
        """Set limited admin user IDs from a list"""
        if user_ids:
            self.limited_admin_user_ids = ','.join(str(uid) for uid in user_ids)
        else:
            self.limited_admin_user_ids = None

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'abbrev': self.abbrev,
            'consortium_id': self.consortium_id,
            'consortium_name': self.consortium.title if self.consortium else None,
            'consortium_abbrev': self.consortium.abbrev if self.consortium else None,
            'viewer_user_ids': self.get_viewer_users(),
            'limited_admin_user_ids': self.get_limited_admin_users(),
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'updated_by': self.updated_by,
            'rfpo_count': len(self.rfpos) if self.rfpos else 0
        }
    
    def __repr__(self):
        consortium_info = f" (Consortium: {self.consortium.abbrev})" if self.consortium else " (No Consortium)"
        return f'<Team {self.abbrev}: {self.name}{consortium_info}>'
