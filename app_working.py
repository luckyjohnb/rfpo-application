#!/usr/bin/env python3
"""
Working Flask App with Login - Simplified Version
This version has built-in user management to avoid import issues
"""
from flask import Flask, render_template, request, jsonify, send_file
import os
import uuid
import json
import bcrypt
import jwt
from datetime import datetime, timedelta
from functools import wraps

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-for-testing'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16777216  # 16MB

# JWT Configuration
JWT_SECRET_KEY = 'dev-jwt-secret-for-testing'

# Create directories
os.makedirs('uploads', exist_ok=True)
os.makedirs('config', exist_ok=True)

# Simple User Management Functions
def load_users():
    """Load users from JSON file"""
    try:
        with open('config/users.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_users(users):
    """Save users to JSON file"""
    with open('config/users.json', 'w') as f:
        json.dump(users, f, indent=2)

def load_users_list():
    """Load users as list for API"""
    try:
        users_dict = load_users()
        print(f"DEBUG: load_users returned: {type(users_dict)} - {users_dict}")
        
        if isinstance(users_dict, dict):
            users_list = list(users_dict.values())
            print(f"DEBUG: Converted to list: {users_list}")
            return users_list
        else:
            print(f"DEBUG: Expected dict but got {type(users_dict)}")
            return []
    except Exception as e:
        print(f"DEBUG: Error in load_users_list: {e}")
        return []

def save_users_list(users_list):
    """Save users list to JSON file"""
    users_dict = {user['username']: user for user in users_list}
    save_users(users_dict)

def authenticate_user(username, password):
    """Authenticate user with username and password"""
    users = load_users()
    user = users.get(username)
    
    if not user:
        return None
    
    # Check password
    password_hash = user.get('password_hash', '')
    if bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
        return user
    
    return None

# Authentication decorator
def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'success': False, 'message': 'No token provided'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
            users = load_users()
            user = users.get(payload.get('username'))
            
            if not user:
                return jsonify({'success': False, 'message': 'User not found'}), 401
                
            request.current_user = user
            
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'message': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'success': False, 'message': 'Invalid token'}), 401
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 401
            
        return f(*args, **kwargs)
    return decorated_function

# Authentication decorator with user parameter
def token_required(f):
    """Decorator to require authentication and pass current user"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'success': False, 'message': 'No token provided'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
            users_list = load_users()
            # Convert list to dict for lookup
            users_dict = {user['username']: user for user in users_list}
            user = users_dict.get(payload.get('username'))
            
            if not user:
                return jsonify({'success': False, 'message': 'User not found'}), 401
                
            # Pass user as first argument to the decorated function
            return f(user, *args, **kwargs)
            
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'message': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'success': False, 'message': 'Invalid token'}), 401
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 401
            
    return decorated_function

# Routes
@app.route('/')
def landing():
    """Landing page"""
    try:
        return render_template('landing.html')
    except Exception as e:
        return f"""
        <h1>🎉 Flask is Working!</h1>
        <p>Template error: {str(e)}</p>
        <p><a href="/hello">Hello Test</a> | <a href="/app">Main App</a> | <a href="/test">API Test</a></p>
        """

@app.route('/hello')
def hello():
    """Simple hello world"""
    return '''
    <h1>🎉 Flask is Working!</h1>
    <p>Your Flask application is running successfully.</p>
    <ul>
        <li><a href="/app">Go to Main App</a></li>
        <li><a href="/test">Test API</a></li>
        <li><a href="/">Landing Page</a></li>
    </ul>
    '''

@app.route('/app')
def index():
    """Main application"""
    try:
        return render_template('index.html')
    except Exception as e:
        return f"""
        <h1>🎯 Main Application</h1>
        <p>Template error: {str(e)}</p>
        <p><a href="/hello">← Back to Hello</a></p>
        """

@app.route('/test')
def test():
    """Test API endpoint"""
    return jsonify({
        'status': 'success',
        'message': 'Flask application is working correctly!',
        'timestamp': datetime.utcnow().isoformat(),
        'routes': ['/hello', '/test', '/app', '/', '/api/auth/login'],
        'users_file_exists': os.path.exists('config/users.json')
    })

# Authentication Routes
@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No JSON data provided'})
        
        username = data.get('username')
        password = data.get('password')
        remember_me = data.get('remember_me', False)
        
        if not username or not password:
            return jsonify({'success': False, 'message': 'Username and password required'})
        
        # Authenticate user
        user = authenticate_user(username, password)
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
        users = load_users()
        users[username]['last_login'] = datetime.utcnow().isoformat()
        save_users(users)
        
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
        return jsonify({'success': False, 'message': f'Login error: {str(e)}'})

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
        users = load_users()
        user = users.get(payload.get('username'))
        
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

# Simple file upload
@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file selected'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        return jsonify({
            'success': True,
            'message': f'File {file.filename} uploaded successfully (demo)',
            'filename': file.filename
        })
        
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

# User Management API Endpoints
@app.route('/api/auth/verify', methods=['GET'])
@token_required
def verify_token(current_user):
    """Verify if token is valid and return user info"""
    return jsonify({
        'success': True,
        'user': {
            'username': current_user['username'],
            'display_name': current_user.get('display_name'),
            'email': current_user.get('email'),
            'roles': current_user.get('roles', [])
        }
    })

@app.route('/api/users', methods=['GET'])
@token_required
def get_users(current_user):
    """Get all users (admin only)"""
    if 'admin' not in current_user.get('roles', []) and 'Administrator' not in current_user.get('roles', []):
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    try:
        users = load_users_list()
        print(f"DEBUG: Loaded users: {users}")  # Debug print
        # Remove passwords from response and normalize fields
        safe_users = []
        for user in users:
            print(f"DEBUG: Processing user: {user}")  # Debug print
            print(f"DEBUG: User type: {type(user)}")  # Debug print
            
            # Create a new dict instead of copying
            safe_user = {
                'id': user.get('id', ''),
                'username': user.get('username', ''),
                'display_name': user.get('display_name', ''),
                'email': user.get('email', ''),
                'roles': user.get('roles', []),
                'status': user.get('status', 'active'),
                'created_at': user.get('created_at', ''),
                'last_login': user.get('last_login', '')
            }
            
            # Normalize status field - convert status to is_active
            safe_user['is_active'] = safe_user['status'] == 'active'
                
            print(f"DEBUG: Safe user after processing: {safe_user}")  # Debug print
            safe_users.append(safe_user)
        
        print(f"DEBUG: Final safe_users: {safe_users}")  # Debug print
        return jsonify({'success': True, 'users': safe_users})
    except Exception as e:
        print(f"DEBUG: Error in get_users: {str(e)}")  # Debug print
        import traceback
        traceback.print_exc()  # Print full traceback
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/users', methods=['POST'])
@token_required
def create_user(current_user):
    """Create new user (admin only)"""
    if 'admin' not in current_user.get('roles', []) and 'Administrator' not in current_user.get('roles', []):
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        display_name = data.get('display_name', '').strip()
        email = data.get('email', '').strip()
        roles = data.get('roles', ['user'])
        
        # Validation
        if not username or not password:
            return jsonify({'success': False, 'message': 'Username and password are required'})
        
        if len(password) < 8:
            return jsonify({'success': False, 'message': 'Password must be at least 8 characters'})
        
        # Check if user exists
        users = load_users_list()
        if any(user['username'] == username for user in users):
            return jsonify({'success': False, 'message': 'Username already exists'})
        
        # Create new user
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        new_user = {
            'id': f'{username}-{str(uuid.uuid4())[:8]}',
            'username': username,
            'password_hash': hashed_password,
            'display_name': display_name,
            'email': email,
            'roles': roles,
            'status': 'active',
            'is_active': True,
            'created_at': datetime.now().isoformat(),
            'last_login': None,
            'failed_login_attempts': 0,
            'locked_until': None,
            'audit_log': []
        }
        
        users.append(new_user)
        save_users_list(users)
        
        return jsonify({'success': True, 'message': 'User created successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/users/<username>', methods=['DELETE'])
@token_required
def delete_user(current_user, username):
    """Delete user (admin only)"""
    if 'admin' not in current_user.get('roles', []) and 'Administrator' not in current_user.get('roles', []):
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    if username == 'admin':
        return jsonify({'success': False, 'message': 'Cannot delete admin user'}), 400
    
    try:
        users = load_users_list()
        users = [user for user in users if user['username'] != username]
        save_users_list(users)
        
        return jsonify({'success': True, 'message': 'User deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Error Handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 FLASK APPLICATION STARTING (WORKING VERSION)")
    print("=" * 60)
    print("🌐 Server: http://127.0.0.1:5000")
    print("📝 Available endpoints:")
    print("   http://127.0.0.1:5000/hello")
    print("   http://127.0.0.1:5000/test")
    print("   http://127.0.0.1:5000/app")
    print("   http://127.0.0.1:5000/api/auth/login (POST)")
    print("📋 Login credentials:")
    print("   Username: admin")
    print("   Password: Administrator123!")
    print("=" * 60)
    
    app.run(debug=True, host='127.0.0.1', port=5000)
