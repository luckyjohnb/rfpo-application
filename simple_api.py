#!/usr/bin/env python3
"""
Simple RFPO API Server
Just Flask + Database connection - nothing fancy
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import check_password_hash
import jwt
from datetime import datetime, timedelta
import os

# Import our models
from models import db, User, Team, RFPO

# Import admin routes
import sys
sys.path.append('api')
try:
    from admin_routes import admin_api
    ADMIN_ROUTES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Admin routes not available: {e}")
    ADMIN_ROUTES_AVAILABLE = False

# User routes are handled directly in this file
USER_ROUTES_AVAILABLE = False

# Create Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = 'simple-api-secret'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.abspath("instance/rfpo_admin.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

# Enable CORS
CORS(app)

# Register admin routes if available
if ADMIN_ROUTES_AVAILABLE:
    app.register_blueprint(admin_api)
    print("✅ Admin API routes registered")

# User routes are handled directly in this file (not as blueprint)

# JWT Secret
JWT_SECRET = 'simple-jwt-secret'

# Simple authentication decorator
def require_auth(f):
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token or not token.startswith('Bearer '):
            return jsonify({'error': 'No token provided'}), 401
        
        try:
            token = token[7:]  # Remove 'Bearer '
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            user = User.query.get(payload['user_id'])
            if not user or not user.active:
                return jsonify({'error': 'Invalid user'}), 401
            request.current_user = user
        except:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def require_admin(f):
    def wrapper(*args, **kwargs):
        if not hasattr(request, 'current_user') or not request.current_user:
            return jsonify({'error': 'Authentication required'}), 401
        
        user_permissions = request.current_user.get_permissions() or []
        if 'GOD' not in user_permissions:
            return jsonify({'error': 'Admin access required'}), 403
        
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# Routes
@app.route('/api/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'Simple RFPO API'})

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('username')  # Frontend sends as 'username' but it's email
    password = data.get('password')
    
    print(f"Login attempt: {email}")
    
    if not email or not password:
        return jsonify({'success': False, 'message': 'Email and password required'}), 400
    
    # Find user
    user = User.query.filter_by(email=email).first()
    
    print(f"User found: {user is not None}")
    if user:
        print(f"User active: {user.active}")
    
    if not user or not user.active:
        return jsonify({'success': False, 'message': 'User not found or inactive'}), 401
    
    # Check password
    if not check_password_hash(user.password_hash, password):
        print("Password check failed")
        return jsonify({'success': False, 'message': 'Invalid password'}), 401
    
    print("Login successful!")
    
    # Create token
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }, JWT_SECRET, algorithm='HS256')
    
    return jsonify({
        'success': True,
        'token': token,
        'user': {
            'id': user.id,
            'username': user.email,
            'display_name': user.fullname,
            'email': user.email,
            'roles': user.get_permissions()
        }
    })

@app.route('/api/auth/verify')
@require_auth
def verify():
    user = request.current_user
    return jsonify({
        'authenticated': True,
        'user': {
            'id': user.id,
            'username': user.email,
            'display_name': user.fullname,
            'email': user.email,
            'roles': user.get_permissions()
        }
    })

@app.route('/api/teams')
@require_auth
def list_teams():
    teams = Team.query.filter_by(active=True).all()
    return jsonify({
        'success': True,
        'teams': [{'id': t.id, 'name': t.name, 'abbrev': t.abbrev, 'description': t.description} for t in teams]
    })

@app.route('/api/auth/change-password', methods=['POST'])
@require_auth
def change_password():
    """Change user password"""
    try:
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return jsonify({'success': False, 'message': 'Current and new passwords required'}), 400
        
        user = request.current_user
        
        # Verify current password
        if not check_password_hash(user.password_hash, current_password):
            return jsonify({'success': False, 'message': 'Current password is incorrect'}), 400
        
        # Validate new password
        if len(new_password) < 8:
            return jsonify({'success': False, 'message': 'New password must be at least 8 characters'}), 400
        
        # Update password
        from werkzeug.security import generate_password_hash
        user.password_hash = generate_password_hash(new_password)
        user.updated_at = datetime.utcnow()
        
        # Mark as no longer first-time user by updating last_visit
        user.last_visit = datetime.utcnow()
        
        db.session.commit()
        
        # Send password change notification email
        try:
            # Get user's IP address for security notification
            user_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'Unknown'))
            
            # Try to send email notification
            try:
                from email_service import send_password_changed_email
                email_sent = send_password_changed_email(user.email, user.fullname, user_ip)
                if email_sent:
                    print(f"✅ Password change notification sent to {user.email}")
                else:
                    print(f"⚠️ Password change notification failed for {user.email}")
            except ImportError:
                print("⚠️ Email service not available - password change notification not sent")
            except Exception as email_error:
                print(f"⚠️ Email notification error: {email_error}")
        except Exception as e:
            print(f"⚠️ Error sending password change notification: {e}")
        
        return jsonify({'success': True, 'message': 'Password changed successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/users/profile', methods=['GET'])
@require_auth
def get_user_profile():
    """Get current user's profile"""
    try:
        user = request.current_user
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'record_id': user.record_id,
                'fullname': user.fullname,
                'email': user.email,
                'sex': user.sex,
                'company_code': user.company_code,
                'company': user.company,
                'position': user.position,
                'department': user.department,
                'building_address': user.building_address,
                'address1': user.address1,
                'address2': user.address2,
                'city': user.city,
                'state': user.state,
                'zip_code': user.zip_code,
                'country': user.country,
                'phone': user.phone,
                'phone_ext': user.phone_ext,
                'mobile': user.mobile,
                'fax': user.fax,
                'last_visit': user.last_visit.isoformat() if user.last_visit else None,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'active': user.active,
                'permissions': user.get_permissions()
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/users/profile', methods=['PUT'])
@require_auth
def update_user_profile():
    """Update current user's profile"""
    try:
        data = request.get_json()
        user = request.current_user
        
        # Update allowed fields (excluding sensitive fields like permissions)
        updateable_fields = [
            'fullname', 'sex', 'company_code', 'company', 'position', 'department',
            'building_address', 'address1', 'address2', 'city', 'state', 'zip_code',
            'country', 'phone', 'phone_ext', 'mobile', 'fax'
        ]
        
        for field in updateable_fields:
            if field in data:
                setattr(user, field, data[field])
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Profile updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/rfpos')
@require_auth
def list_rfpos():
    rfpos = RFPO.query.all()
    return jsonify({
        'success': True,
        'rfpos': [{'id': r.id, 'rfpo_id': r.rfpo_id, 'title': r.title, 'status': r.status, 'created_at': r.created_at.isoformat() if r.created_at else None} for r in rfpos]
    })

if __name__ == '__main__':
    print("🚀 Starting Simple RFPO API")
    print(f"📂 Database: {app.config['SQLALCHEMY_DATABASE_URI']}")
    
    with app.app_context():
        print(f"👥 Users in database: {User.query.count()}")
    
    app.run(debug=False, host='0.0.0.0', port=5002)
