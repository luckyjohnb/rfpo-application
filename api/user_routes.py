"""
User Profile API Routes
Endpoints for user profile management
"""

from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, User
from api.utils import require_auth

user_api = Blueprint('user_api', __name__, url_prefix='/api/users')

@user_api.route('/profile', methods=['GET'])
@require_auth
def get_user_profile():
    """Get current user's profile"""
    try:
        user = request.current_user
        return jsonify({
            'success': True,
            'user': user.to_dict()
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@user_api.route('/profile', methods=['PUT'])
@require_auth
def update_user_profile():
    """Update current user's profile"""
    try:
        user = request.current_user
        data = request.get_json()
        
        # Update allowed fields
        updatable_fields = [
            'fullname', 'sex', 'position', 'company_code', 'company', 'department',
            'building_address', 'address1', 'address2', 'city', 'state', 'zip_code', 
            'country', 'phone', 'phone_ext', 'mobile', 'fax'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(user, field, data[field])
        
        # Update timestamp
        user.updated_at = datetime.utcnow()
        user.updated_by = user.email
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Profile updated successfully',
            'user': user.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@user_api.route('/change-password', methods=['POST'])
@require_auth
def change_password():
    """Change user password"""
    try:
        user = request.current_user
        data = request.get_json()
        
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return jsonify({'success': False, 'message': 'Current and new password required'}), 400
        
        # Verify current password
        if not check_password_hash(user.password_hash, current_password):
            return jsonify({'success': False, 'message': 'Current password is incorrect'}), 400
        
        # Validate new password
        if len(new_password) < 8:
            return jsonify({'success': False, 'message': 'New password must be at least 8 characters'}), 400
        
        # Update password and mark as no longer first-time login
        user.password_hash = generate_password_hash(new_password)
        user.last_visit = datetime.utcnow()  # Update last_visit to mark as no longer first-time
        user.updated_at = datetime.utcnow()
        user.updated_by = user.email
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Password changed successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
