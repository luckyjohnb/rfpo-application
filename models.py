from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

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
    __tablename__ = 'teams'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    abbrev = db.Column(db.String(32), nullable=False, unique=True)
    consortium_id = db.Column(db.Integer, nullable=False)
    viewer_user_ids = db.Column(db.Text)  # Comma-separated user IDs
    limited_admin_user_ids = db.Column(db.Text)  # Comma-separated user IDs
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(64))
    updated_by = db.Column(db.String(64))

    __table_args__ = (
        db.UniqueConstraint('name', 'consortium_id', name='uq_team_name_consortium'),
        db.UniqueConstraint('abbrev', 'consortium_id', name='uq_team_abbrev_consortium'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'abbrev': self.abbrev,
            'consortium_id': self.consortium_id,
            'viewer_user_ids': self.viewer_user_ids.split(',') if self.viewer_user_ids else [],
            'limited_admin_user_ids': self.limited_admin_user_ids.split(',') if self.limited_admin_user_ids else [],
            'active': self.active,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'created_by': self.created_by,
            'updated_by': self.updated_by,
        }
