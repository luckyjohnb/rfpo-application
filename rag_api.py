"""
RAG API endpoints for enhanced file upload and processing
Provides endpoints for file management, RFPO association, and RAG search
"""
import os
import uuid
import mimetypes
from datetime import datetime
from typing import List, Dict, Optional
import logging
from threading import Thread

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError

from models import db, RFPO, UploadedFile, DocumentChunk, Team
from document_processor import document_processor
from user_management import UserManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Blueprint
rag_bp = Blueprint('rag', __name__, url_prefix='/api/v1/rag')

# Initialize user manager
user_manager = UserManager()

def require_auth(f):
    """Decorator to require authentication"""
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authentication required'}), 401
        
        try:
            # Use the same JWT validation as the main app
            import jwt
            from app import JWT_SECRET_KEY
            
            token = auth_header[7:]  # Remove 'Bearer ' prefix
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
            user = user_manager.get_user_by_id(payload['user_id'])
            
            if not user or user.get('status') != 'active':
                return jsonify({'error': 'Invalid or inactive user'}), 401
            
            request.current_user = user
            return f(*args, **kwargs)
            
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        except Exception as e:
            return jsonify({'error': f'Authentication error: {str(e)}'}), 401
    
    decorated.__name__ = f.__name__
    return decorated

def get_allowed_extensions():
    """Get allowed file extensions from configuration"""
    return {
        'txt', 'md', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv', 
        'ppt', 'pptx', 'json', 'xml', 'rtf'
    }

def is_allowed_file(filename):
    """Check if file extension is allowed"""
    if '.' not in filename:
        return False
    
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in get_allowed_extensions()

def get_file_info(file_path: str, original_filename: str) -> Dict:
    """Get comprehensive file information"""
    stat = os.stat(file_path)
    mime_type, _ = mimetypes.guess_type(original_filename)
    
    return {
        'size': stat.st_size,
        'mime_type': mime_type or 'application/octet-stream',
        'extension': original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else '',
        'created_at': datetime.fromtimestamp(stat.st_ctime),
        'modified_at': datetime.fromtimestamp(stat.st_mtime)
    }

def process_file_async(file_id: str, app_instance):
    """Process file asynchronously in background thread"""
    try:
        with app_instance.app_context():
            file_record = UploadedFile.query.filter_by(file_id=file_id).first()
            if file_record:
                document_processor.process_uploaded_file(file_record)
                logger.info(f"Successfully processed file {file_id} in background")
    except Exception as e:
        logger.error(f"Async processing failed for file {file_id}: {str(e)}")

@rag_bp.route('/rfpos', methods=['GET'])
@require_auth
def list_rfpos():
    """List all RFPOs for the current user"""
    try:
        user = request.current_user
        
        # Get user's teams (simplified - you may need to adjust based on your auth system)
        rfpos = RFPO.query.all()  # For now, return all RFPOs
        
        return jsonify({
            'success': True,
            'rfpos': [rfpo.to_dict() for rfpo in rfpos]
        })
        
    except Exception as e:
        logger.error(f"Error listing RFPOs: {str(e)}")
        return jsonify({'error': str(e)}), 500

@rag_bp.route('/rfpos', methods=['POST'])
@require_auth
def create_rfpo():
    """Create a new RFPO"""
    try:
        user = request.current_user
        data = request.get_json()
        
        if not data.get('title'):
            return jsonify({'error': 'Title is required'}), 400
        
        if not data.get('team_id'):
            return jsonify({'error': 'Team ID is required'}), 400
        
        # Generate RFPO ID
        rfpo_count = RFPO.query.count()
        rfpo_id = f"RFPO-{rfpo_count + 1:03d}"
        
        # Create RFPO
        rfpo = RFPO(
            rfpo_id=rfpo_id,
            title=data['title'],
            description=data.get('description', ''),
            vendor=data.get('vendor', ''),
            due_date=datetime.fromisoformat(data['due_date']) if data.get('due_date') else None,
            status=data.get('status', 'Draft'),
            team_id=data['team_id'],
            created_by=user['username']
        )
        
        db.session.add(rfpo)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'rfpo': rfpo.to_dict()
        }), 201
        
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'RFPO ID already exists'}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating RFPO: {str(e)}")
        return jsonify({'error': str(e)}), 500

@rag_bp.route('/rfpos/<int:rfpo_id>', methods=['GET'])
@require_auth
def get_rfpo(rfpo_id):
    """Get RFPO details with associated files"""
    try:
        rfpo = RFPO.query.get_or_404(rfpo_id)
        
        rfpo_data = rfpo.to_dict()
        rfpo_data['files'] = [file.to_dict() for file in rfpo.files]
        
        return jsonify({
            'success': True,
            'rfpo': rfpo_data
        })
        
    except Exception as e:
        logger.error(f"Error getting RFPO {rfpo_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@rag_bp.route('/rfpos/<int:rfpo_id>/files', methods=['POST'])
@require_auth
def upload_file_to_rfpo(rfpo_id):
    """Upload file(s) to an RFPO with RAG processing"""
    try:
        user = request.current_user
        
        # Verify RFPO exists
        rfpo = RFPO.query.get_or_404(rfpo_id)
        
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No files selected'}), 400
        
        uploaded_files = []
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        
        for file in files:
            if file.filename == '':
                continue
                
            if not is_allowed_file(file.filename):
                return jsonify({
                    'error': f'File type not allowed: {file.filename}. '
                            f'Allowed types: {", ".join(get_allowed_extensions())}'
                }), 400
            
            # Secure filename and generate unique storage name
            original_filename = secure_filename(file.filename)
            file_id = str(uuid.uuid4())
            stored_filename = f"{file_id}_{original_filename}"
            file_path = os.path.join(upload_folder, stored_filename)
            
            # Save file
            file.save(file_path)
            
            # Get file info
            file_info = get_file_info(file_path, original_filename)
            
            # Create database record
            uploaded_file = UploadedFile(
                file_id=file_id,
                original_filename=original_filename,
                stored_filename=stored_filename,
                file_path=file_path,
                file_size=file_info['size'],
                mime_type=file_info['mime_type'],
                file_extension=file_info['extension'],
                rfpo_id=rfpo_id,
                uploaded_by=user['username'],
                processing_status='pending'
            )
            
            db.session.add(uploaded_file)
            uploaded_files.append(uploaded_file)
        
        db.session.commit()
        
        # Start async processing for each file
        from flask import current_app as flask_app
        app_instance = flask_app._get_current_object()
        for uploaded_file in uploaded_files:
            thread = Thread(target=process_file_async, args=(uploaded_file.file_id, app_instance))
            thread.daemon = True
            thread.start()
        
        return jsonify({
            'success': True,
            'message': f'Successfully uploaded {len(uploaded_files)} files. Processing started.',
            'files': [file.to_dict() for file in uploaded_files]
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error uploading files to RFPO {rfpo_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@rag_bp.route('/files/<file_id>/status', methods=['GET'])
@require_auth
def get_file_processing_status(file_id):
    """Get processing status of a file"""
    try:
        file_record = UploadedFile.query.filter_by(file_id=file_id).first_or_404()
        
        return jsonify({
            'success': True,
            'status': {
                'processing_status': file_record.processing_status,
                'text_extracted': file_record.text_extracted,
                'embeddings_created': file_record.embeddings_created,
                'chunk_count': file_record.chunk_count,
                'processing_error': file_record.processing_error,
                'processed_at': file_record.processed_at.isoformat() if file_record.processed_at else None
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting file status {file_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@rag_bp.route('/files/<file_id>/reprocess', methods=['POST'])
@require_auth
def reprocess_file(file_id):
    """Reprocess a file (useful if processing failed)"""
    try:
        file_record = UploadedFile.query.filter_by(file_id=file_id).first_or_404()
        
        # Reset processing status
        file_record.processing_status = 'pending'
        file_record.processing_error = None
        file_record.text_extracted = False
        file_record.embeddings_created = False
        file_record.processed_at = None
        
        # Delete existing chunks
        DocumentChunk.query.filter_by(file_id=file_record.id).delete()
        
        db.session.commit()
        
        # Start async processing
        thread = Thread(target=process_file_async, args=(file_id,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'File reprocessing started'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error reprocessing file {file_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@rag_bp.route('/rfpos/<int:rfpo_id>/search', methods=['POST'])
@require_auth
def search_rfpo_documents(rfpo_id):
    """Search documents within an RFPO using RAG"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        # Verify RFPO exists
        rfpo = RFPO.query.get_or_404(rfpo_id)
        
        # Search similar chunks
        top_k = data.get('top_k', 5)
        similar_chunks = document_processor.search_similar_chunks(query, rfpo_id, top_k)
        
        return jsonify({
            'success': True,
            'query': query,
            'rfpo_id': rfpo_id,
            'results': similar_chunks,
            'result_count': len(similar_chunks)
        })
        
    except Exception as e:
        logger.error(f"Error searching RFPO {rfpo_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@rag_bp.route('/rfpos/<int:rfpo_id>/chat', methods=['POST'])
@require_auth
def chat_with_rfpo_documents(rfpo_id):
    """Chat with RFPO documents using RAG context"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Verify RFPO exists
        rfpo = RFPO.query.get_or_404(rfpo_id)
        
        # Get relevant context from documents
        context_chunks = document_processor.search_similar_chunks(message, rfpo_id, top_k=3)
        
        # Build context for the AI
        context_text = ""
        if context_chunks:
            context_text = "Relevant document context:\n\n"
            for i, chunk in enumerate(context_chunks, 1):
                context_text += f"Context {i} (from {chunk['file_name']}):\n{chunk['text_content']}\n\n"
        
        # Prepare the enhanced message with context
        enhanced_message = f"""Based on the documents uploaded to RFPO {rfpo.rfpo_id} ({rfpo.title}), please answer this question:

{message}

{context_text}

Please provide a helpful response based on the document context provided above."""
        
        return jsonify({
            'success': True,
            'enhanced_message': enhanced_message,
            'context_chunks': context_chunks,
            'rfpo_info': {
                'rfpo_id': rfpo.rfpo_id,
                'title': rfpo.title
            }
        })
        
    except Exception as e:
        logger.error(f"Error in RAG chat for RFPO {rfpo_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@rag_bp.route('/files/<file_id>', methods=['DELETE'])
@require_auth
def delete_file(file_id):
    """Delete an uploaded file and its processed data"""
    try:
        file_record = UploadedFile.query.filter_by(file_id=file_id).first_or_404()
        
        # Delete physical file
        if os.path.exists(file_record.file_path):
            os.remove(file_record.file_path)
        
        # Delete chunks (cascade should handle this, but explicit is better)
        DocumentChunk.query.filter_by(file_id=file_record.id).delete()
        
        # Delete file record
        db.session.delete(file_record)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'File deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting file {file_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@rag_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'RAG API',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0'
    })
