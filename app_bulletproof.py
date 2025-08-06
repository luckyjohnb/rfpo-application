#!/usr/bin/env python3
"""
Bulletproof User Management API - Fixed Version
This version eliminates all potential sources of the "string indices" error
"""
from flask import Flask, render_template, request, jsonify
import os
import json
import bcrypt
import jwt
from datetime import datetime, timedelta
from functools import wraps

try:
    import pandas as pd
except ImportError:
    pd = None

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-for-testing'

# JWT Configuration
JWT_SECRET_KEY = 'dev-jwt-secret-for-testing'

# Create directories
os.makedirs('config', exist_ok=True)

def safe_load_users():
    """Safely load users with error handling"""
    try:
        with open('config/users.json', 'r') as f:
            data = json.load(f)
        
        # Ensure we have a dictionary
        if not isinstance(data, dict):
            print(f"ERROR: Expected dict, got {type(data)}")
            return {}
        
        return data
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"ERROR loading users: {e}")
        return {}

def get_users_as_list():
    """Get users as a safe list for API responses"""
    try:
        users_dict = safe_load_users()
        users_list = []
        
        for username, user_data in users_dict.items():
            if isinstance(user_data, dict):
                # Create a clean user object
                clean_user = {
                    'id': user_data.get('id', username),
                    'username': user_data.get('username', username),
                    'display_name': user_data.get('display_name', ''),
                    'email': user_data.get('email', ''),
                    'roles': user_data.get('roles', []),
                    'status': user_data.get('status', 'active'),
                    'created_at': user_data.get('created_at', ''),
                    'last_login': user_data.get('last_login', ''),
                    'is_active': user_data.get('status', 'active') == 'active'
                }
                users_list.append(clean_user)
            else:
                print(f"WARNING: Skipping invalid user data for {username}: {type(user_data)}")
        
        return users_list
    except Exception as e:
        print(f"ERROR in get_users_as_list: {e}")
        return []

def authenticate_user_simple(username, password):
    """Simple authentication function"""
    try:
        users_dict = safe_load_users()
        user_data = users_dict.get(username)
        
        if not user_data or not isinstance(user_data, dict):
            return None
        
        password_hash = user_data.get('password_hash', '')
        if bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
            return user_data
        
        return None
    except Exception as e:
        print(f"ERROR in authenticate_user_simple: {e}")
        return None

def token_required_simple(f):
    """Simple token verification decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'success': False, 'message': 'No token provided'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
            username = payload.get('username')
            
            users_dict = safe_load_users()
            user_data = users_dict.get(username)
            
            if not user_data or not isinstance(user_data, dict):
                return jsonify({'success': False, 'message': 'User not found'}), 401
            
            return f(user_data, *args, **kwargs)
            
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'message': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'success': False, 'message': 'Invalid token'}), 401
        except Exception as e:
            print(f"ERROR in token verification: {e}")
            return jsonify({'success': False, 'message': 'Authentication error'}), 401
            
    return decorated_function

@app.route('/api/auth/login', methods=['POST'])
def login_simple():
    """Simple login endpoint"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        user = authenticate_user_simple(username, password)
        if not user:
            return jsonify({'success': False, 'message': 'Invalid credentials'})
        
        # Create JWT token
        token_payload = {
            'username': username,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        token = jwt.encode(token_payload, JWT_SECRET_KEY, algorithm='HS256')
        
        # Update last login
        users_dict = safe_load_users()
        if username in users_dict:
            users_dict[username]['last_login'] = datetime.now().isoformat()
            with open('config/users.json', 'w') as f:
                json.dump(users_dict, f, indent=2)
        
        return jsonify({
            'success': True,
            'token': token,
            'user': {
                'username': user.get('username', username),
                'display_name': user.get('display_name', ''),
                'email': user.get('email', ''),
                'roles': user.get('roles', [])
            }
        })
    except Exception as e:
        print(f"ERROR in login: {e}")
        return jsonify({'success': False, 'message': 'Login error'}), 500

@app.route('/api/auth/verify', methods=['GET'])
@token_required_simple
def verify_simple(current_user):
    """Simple token verification"""
    return jsonify({
        'success': True,
        'user': {
            'username': current_user.get('username', ''),
            'display_name': current_user.get('display_name', ''),
            'email': current_user.get('email', ''),
            'roles': current_user.get('roles', [])
        }
    })

@app.route('/api/users', methods=['GET'])
@token_required_simple
def get_users_simple(current_user):
    """Simple get users endpoint"""
    try:
        # Check if user is admin
        user_roles = current_user.get('roles', [])
        if 'admin' not in user_roles:
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        
        users_list = get_users_as_list()
        return jsonify({'success': True, 'users': users_list})
        
    except Exception as e:
        print(f"ERROR in get_users_simple: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/api/users', methods=['POST'])
@token_required_simple
def create_user_simple(current_user):
    """Simple create user endpoint"""
    try:
        # Check if user is admin
        user_roles = current_user.get('roles', [])
        if 'admin' not in user_roles:
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        
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
        users_dict = safe_load_users()
        if username in users_dict:
            return jsonify({'success': False, 'message': 'Username already exists'})
        
        # Create new user
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        new_user = {
            'id': f'{username}-{datetime.now().strftime("%Y%m%d")}',
            'username': username,
            'password_hash': hashed_password,
            'display_name': display_name,
            'email': email,
            'roles': roles,
            'status': 'active',
            'created_at': datetime.now().isoformat(),
            'last_login': None,
            'failed_login_attempts': 0,
            'locked_until': None,
            'audit_log': []
        }
        
        # Add to users dict and save
        users_dict[username] = new_user
        with open('config/users.json', 'w') as f:
            json.dump(users_dict, f, indent=2)
        
        return jsonify({'success': True, 'message': 'User created successfully'})
        
    except Exception as e:
        print(f"ERROR in create_user_simple: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/upload', methods=['POST'])
def upload_file_simple():
    """Simple file upload endpoint"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        if file:
            filename = file.filename
            # Ensure uploads directory exists
            os.makedirs('uploads', exist_ok=True)
            filepath = os.path.join('uploads', filename)
            file.save(filepath)
            
            # Try to read the file for basic info
            try:
                if pd is None:
                    return jsonify({
                        'success': True,
                        'filename': filename,
                        'rows': 'Unknown (pandas not installed)',
                        'columns': ['File uploaded successfully']
                    })
                    
                if filename.endswith('.csv'):
                    df = pd.read_csv(filepath)
                elif filename.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(filepath)
                else:
                    return jsonify({'success': False, 'error': 'Unsupported file format'})
                
                return jsonify({
                    'success': True,
                    'filename': filename,
                    'rows': len(df),
                    'columns': list(df.columns)
                })
            except Exception as e:
                return jsonify({
                    'success': True,
                    'filename': filename,
                    'rows': 'Unknown',
                    'columns': ['File uploaded but could not be parsed']
                })
        
    except Exception as e:
        print(f"ERROR in upload_file_simple: {e}")
        return jsonify({'success': False, 'error': f'Upload error: {str(e)}'})

@app.route('/api/users/<username>', methods=['DELETE'])
@token_required_simple
def delete_user_simple(current_user, username):
    """Simple delete user endpoint"""
    try:
        # Check if user is admin
        user_roles = current_user.get('roles', [])
        if 'admin' not in user_roles:
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        
        if username == 'admin':
            return jsonify({'success': False, 'message': 'Cannot delete admin user'}), 400
        
        # Load users and remove the specified user
        users_dict = safe_load_users()
        if username in users_dict:
            del users_dict[username]
            with open('config/users.json', 'w') as f:
                json.dump(users_dict, f, indent=2)
            return jsonify({'success': True, 'message': 'User deleted successfully'})
        else:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
    except Exception as e:
        print(f"ERROR in delete_user_simple: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

# Copy other routes from the main app
@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/app')
def main_app():
    return render_template('index.html')

@app.route('/hello')
def hello():
    return jsonify({'message': 'Hello from Flask!', 'status': 'success'})

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 BULLETPROOF FLASK APPLICATION")
    print("=" * 60)
    print("🌐 Server: http://127.0.0.1:5000")
    print("📝 Available endpoints:")
    print("   http://127.0.0.1:5000/app")
    print("   http://127.0.0.1:5000/api/auth/login (POST)")
    print("   http://127.0.0.1:5000/api/users (GET)")
    print("📋 Login credentials:")
    print("   Username: admin")
    print("   Password: Administrator123!")
    print("=" * 60)
    
    app.run(debug=True, host='127.0.0.1', port=5000)
