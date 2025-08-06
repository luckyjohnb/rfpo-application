from flask import Flask, render_template, request, jsonify, send_file
import os
import uuid
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from functools import wraps
import jwt

# Conditional imports for optional features
try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
    print("✅ Pandas available - Full file processing enabled")
except ImportError:
    print("⚠️ Warning: pandas not available. File processing features will be limited.")
    PANDAS_AVAILABLE = False

try:
    from reportlab.lib import colors
    from reportlab.lib.colors import Color
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
    print("✅ ReportLab available - PDF export enabled")
except ImportError:
    print("⚠️ Warning: ReportLab not available. PDF export disabled.")
    REPORTLAB_AVAILABLE = False

# Import user management
from user_management import UserManager

# Load environment variables
def load_config():
    """Load configuration from environment or .env file"""
    config = {}
    
    # Try to load from .env file
    try:
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key] = value
    except FileNotFoundError:
        print("⚠️ Warning: .env file not found. Using default configuration.")
    
    # Set defaults if not found in .env
    config.setdefault('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production-' + str(uuid.uuid4()))
    config.setdefault('JWT_SECRET_KEY', 'dev-jwt-secret-change-in-production-' + str(uuid.uuid4()))
    config.setdefault('FLASK_DEBUG', 'False')
    config.setdefault('UPLOAD_FOLDER', 'uploads')
    config.setdefault('MAX_CONTENT_LENGTH', '16777216')  # 16MB
    
    return config

# Load configuration
config = load_config()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = config['FLASK_SECRET_KEY']
app.config['UPLOAD_FOLDER'] = config['UPLOAD_FOLDER']
app.config['MAX_CONTENT_LENGTH'] = int(config['MAX_CONTENT_LENGTH'])

# JWT Configuration
JWT_SECRET_KEY = config['JWT_SECRET_KEY']

# Create necessary directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('config', exist_ok=True)
os.makedirs('logs', exist_ok=True)

# Initialize User Manager
user_manager = UserManager()

# Global storage for uploaded data (in production, use database)
uploaded_data = {}

# Tab configuration
TAB_CONFIG = {
    'total_tabs': 4,
    'tab_names': ['File Upload', 'Data Review', 'Processing', 'Results']
}

# Authentication decorators
def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'success': False, 'message': 'No token provided'}), 401
        
        try:
            # Remove 'Bearer ' prefix if present
            if token.startswith('Bearer '):
                token = token[7:]
            
            # Verify token
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
            user = user_manager.get_user_by_id(payload['user_id'])
            
            if not user:
                return jsonify({'success': False, 'message': 'User not found'}), 401
            
            if user.get('status') != 'active':
                return jsonify({'success': False, 'message': 'Account not active'}), 401
                
            request.current_user = user
            
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'message': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'success': False, 'message': 'Invalid token'}), 401
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 401
            
        return f(*args, **kwargs)
    return decorated_function

def require_admin(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(request, 'current_user') or not request.current_user:
            return jsonify({'success': False, 'message': 'Authentication required'}), 401
        
        if 'Administrator' not in request.current_user.get('roles', []):
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
            
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def landing():
    """Landing page"""
    try:
        return render_template('landing.html')
    except Exception as e:
        # Fallback if template fails
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Flask App - Template Error</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .error {{ color: #dc3545; background: #f8d7da; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .success {{ color: #155724; background: #d4edda; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                a {{ color: #007bff; text-decoration: none; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 Flask Application Status</h1>
                <div class="success">
                    <strong>✅ Flask Server is Running!</strong><br>
                    Your application is working, but there's a template issue.
                </div>
                <div class="error">
                    <strong>Template Error:</strong> {str(e)}
                </div>
                <h3>Available Routes:</h3>
                <ul>
                    <li><a href="/hello">Hello World Test</a></li>
                    <li><a href="/test">API Test</a></li>
                    <li><a href="/app">Main Application</a></li>
                </ul>
                <h3>Troubleshooting:</h3>
                <ol>
                    <li>Check if templates directory exists</li>
                    <li>Verify landing.html and index.html files</li>
                    <li>Check Flask template configuration</li>
                </ol>
            </div>
        </body>
        </html>
        """

@app.route('/hello')
def hello():
    """Simple hello world to test if Flask is working"""
    return '<h1>🎉 Flask is Working!</h1><p>Your Flask application is running successfully.</p><a href="/app">Go to Main App</a>'

@app.route('/app')
def index():
    """Main application"""
    try:
        return render_template('index.html')
    except Exception as e:
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Flask App - Main Application</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .error {{ color: #dc3545; background: #f8d7da; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .success {{ color: #155724; background: #d4edda; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎯 Main Application</h1>
                <div class="success">Flask server is running successfully!</div>
                <div class="error">Template Error: {str(e)}</div>
                <p><a href="/hello">← Back to Hello World</a> | <a href="/test">Test API →</a></p>
            </div>
        </body>
        </html>
        """

@app.route('/test')
def test():
    """Simple test endpoint to verify app is working"""
    return jsonify({
        'status': 'success',
        'message': 'Flask application is working correctly!',
        'timestamp': datetime.utcnow().isoformat(),
        'features': {
            'pandas': PANDAS_AVAILABLE,
            'reportlab': REPORTLAB_AVAILABLE,
            'user_management': True
        }
    })

# Authentication Routes
@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        remember_me = data.get('remember_me', False)
        
        if not username or not password:
            return jsonify({'success': False, 'message': 'Username and password required'})
        
        # Authenticate user
        user = user_manager.authenticate_user(username, password)
        if not user:
            return jsonify({'success': False, 'message': 'Invalid credentials'})
        
        # Check if user is active
        if user.get('status') != 'active':
            return jsonify({'success': False, 'message': 'Account is not active'})
        
        # Generate JWT token
        expiry = datetime.utcnow() + (timedelta(days=30) if remember_me else timedelta(hours=24))
        payload = {
            'user_id': user['id'],
            'username': user['username'],
            'exp': expiry
        }
        
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')
        
        # Update last login
        user_manager.update_last_login(user['id'])
        
        return jsonify({
            'success': True,
            'token': token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'display_name': user.get('display_name', ''),
                'email': user['email'],
                'roles': user['roles']
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/auth/register', methods=['POST'])
def register():
    """User registration"""
    try:
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        display_name = data.get('display_name')
        password = data.get('password')
        
        if not all([username, email, password]):
            return jsonify({'success': False, 'message': 'Missing required fields'})
        
        # Create user (pending approval)
        result = user_manager.create_user(
            username=username,
            email=email,
            password=password,
            display_name=display_name,
            roles=['User'],
            status='pending'
        )
        
        if result['success']:
            return jsonify({'success': True, 'message': 'Registration successful. Awaiting approval.'})
        else:
            return jsonify({'success': False, 'message': result['message']})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/auth/validate', methods=['POST'])
def validate_token():
    """Validate JWT token"""
    try:
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'success': False, 'message': 'No token provided'})
        
        if token.startswith('Bearer '):
            token = token[7:]
        
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
        user = user_manager.get_user_by_id(payload['user_id'])
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'display_name': user.get('display_name', ''),
                'email': user['email'],
                'roles': user['roles']
            }
        })
        
    except jwt.ExpiredSignatureError:
        return jsonify({'success': False, 'message': 'Token expired'})
    except jwt.InvalidTokenError:
        return jsonify({'success': False, 'message': 'Invalid token'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# User Management Routes
@app.route('/api/users', methods=['GET'])
@require_auth
@require_admin
def get_users():
    """Get users list"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        search = request.args.get('search', '')
        role = request.args.get('role', '')
        
        result = user_manager.get_users(
            page=page,
            per_page=per_page,
            search=search,
            role_filter=role
        )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/users', methods=['POST'])
@require_auth
@require_admin
def create_user():
    """Create new user"""
    try:
        data = request.get_json()
        result = user_manager.create_user(
            username=data.get('username'),
            email=data.get('email'),
            password=data.get('password'),
            display_name=data.get('display_name'),
            roles=data.get('roles', ['User']),
            status=data.get('status', 'active')
        )
        
        if result['success']:
            user_manager.log_audit(
                request.current_user['id'],
                'user_created',
                f"Created user: {data.get('username')}"
            )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/users/<user_id>', methods=['PUT'])
@require_auth
@require_admin
def update_user(user_id):
    """Update user"""
    try:
        data = request.get_json()
        result = user_manager.update_user(user_id, data)
        
        if result['success']:
            user_manager.log_audit(
                request.current_user['id'],
                'user_updated',
                f"Updated user: {user_id}"
            )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/users/<user_id>', methods=['DELETE'])
@require_auth
@require_admin
def delete_user(user_id):
    """Delete user"""
    try:
        result = user_manager.delete_user(user_id)
        
        if result['success']:
            user_manager.log_audit(
                request.current_user['id'],
                'user_deleted',
                f"Deleted user: {user_id}"
            )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/users/<user_id>/status', methods=['PUT'])
@require_auth
@require_admin
def update_user_status(user_id):
    """Update user status"""
    try:
        data = request.get_json()
        status = data.get('status')
        
        result = user_manager.update_user_status(user_id, status)
        
        if result['success']:
            user_manager.log_audit(
                request.current_user['id'],
                'user_status_changed',
                f"Changed user {user_id} status to {status}"
            )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# File Upload Route
@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file selected'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not PANDAS_AVAILABLE:
            return jsonify({'error': 'File processing unavailable - pandas not installed'}), 500
        
        # Secure filename
        filename = secure_filename(file.filename)
        if not filename.lower().endswith(('.csv', '.xlsx', '.xls')):
            return jsonify({'error': 'Only CSV and Excel files are supported'}), 400
        
        # Generate unique file ID
        file_id = str(uuid.uuid4())
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{file_id}_{filename}")
        file.save(file_path)
        
        # Process file
        try:
            if filename.lower().endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            
            # Clean data
            df = df.fillna('')
            data_dict = df.to_dict('records')
            
            # Store data
            uploaded_data[file_id] = {
                'filename': filename,
                'data': data_dict,
                'columns': list(df.columns),
                'rows': len(df)
            }
            
            return jsonify({
                'success': True,
                'file_id': file_id,
                'filename': filename,
                'rows': len(df),
                'columns': list(df.columns)
            })
            
        except Exception as e:
            return jsonify({'error': f'Error processing file: {str(e)}'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

# Data Routes
@app.route('/data/<file_id>')
def get_data(file_id):
    """Get paginated data for a file"""
    try:
        if file_id not in uploaded_data:
            return jsonify({'error': 'File not found'}), 404
        
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        
        data = uploaded_data[file_id]['data']
        total_items = len(data)
        total_pages = (total_items + per_page - 1) // per_page
        
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_data = data[start_idx:end_idx]
        
        return jsonify({
            'success': True,
            'data': paginated_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_items': total_items,
                'total_pages': total_pages
            },
            'file_info': {
                'filename': uploaded_data[file_id]['filename'],
                'columns': uploaded_data[file_id]['columns'],
                'rows': uploaded_data[file_id]['rows']
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Export Route
@app.route('/export/<file_id>/<format>')
def export_data(file_id, format):
    """Export data in specified format"""
    try:
        if file_id not in uploaded_data:
            return jsonify({'error': 'File not found'}), 404
        
        if format == 'pdf' and not REPORTLAB_AVAILABLE:
            return jsonify({'error': 'PDF export unavailable - reportlab not installed'}), 500
        
        if format != 'pdf' and not PANDAS_AVAILABLE:
            return jsonify({'error': 'Export unavailable - pandas not installed'}), 500
        
        data = uploaded_data[file_id]['data']
        filename = uploaded_data[file_id]['filename']
        
        if format == 'csv':
            df = pd.DataFrame(data)
            export_path = os.path.join(app.config['UPLOAD_FOLDER'], f"exported_{filename}")
            if not export_path.endswith('.csv'):
                export_path = export_path.rsplit('.', 1)[0] + '.csv'
            df.to_csv(export_path, index=False)
            return send_file(export_path, as_attachment=True, download_name=f"exported_{filename}")
        
        elif format == 'excel':
            df = pd.DataFrame(data)
            export_path = os.path.join(app.config['UPLOAD_FOLDER'], f"exported_{filename}")
            if not export_path.endswith(('.xlsx', '.xls')):
                export_path = export_path.rsplit('.', 1)[0] + '.xlsx'
            df.to_excel(export_path, index=False)
            return send_file(export_path, as_attachment=True, download_name=f"exported_{filename}")
        
        else:
            return jsonify({'error': 'Unsupported export format'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Export failed: {str(e)}'}), 500

# Reset Route
@app.route('/reset-workflow', methods=['POST'])
def reset_workflow():
    """Clear all uploaded data"""
    global uploaded_data
    uploaded_data.clear()
    return jsonify({'success': True, 'message': 'Workflow reset successfully'})

# Error Handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(413)
def file_too_large(error):
    return jsonify({'error': 'File too large'}), 413

if __name__ == '__main__':
    debug_mode = config.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print("=" * 60)
    print("🚀 FLASK APPLICATION STARTING")
    print("=" * 60)
    print(f"🔧 Debug Mode: {'ON' if debug_mode else 'OFF'}")
    print(f"📁 Upload Folder: {app.config['UPLOAD_FOLDER']}")
    print(f"🔐 User Management: ENABLED")
    print(f"📊 Pandas Support: {'ENABLED' if PANDAS_AVAILABLE else 'DISABLED'}")
    print(f"📄 PDF Export: {'ENABLED' if REPORTLAB_AVAILABLE else 'DISABLED'}")
    print(f"🌐 Server: http://127.0.0.1:5000")
    print("=" * 60)
    
    app.run(debug=debug_mode, host='127.0.0.1', port=5000)
