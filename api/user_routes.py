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
from utils import require_auth

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

@user_api.route('/permissions-summary', methods=['GET'])
@require_auth
def get_user_permissions_summary():
    """Get comprehensive permissions summary for current user"""
    try:
        from models import Team, Consortium, Project, RFPO
        
        user = request.current_user
        
        # System permissions
        system_permissions = user.get_permissions() or []
        
        # Team associations
        user_teams = user.get_teams()
        team_data = []
        accessible_consortium_ids = set()
        
        for team in user_teams:
            team_info = {
                'id': team.id,
                'record_id': team.record_id,
                'name': team.name,
                'abbrev': team.abbrev,
                'consortium_id': team.consortium_consort_id,
                'consortium_name': None
            }
            
            # Get consortium info
            if team.consortium_consort_id:
                consortium = Consortium.query.filter_by(consort_id=team.consortium_consort_id).first()
                if consortium:
                    team_info['consortium_name'] = consortium.name
                    accessible_consortium_ids.add(team.consortium_consort_id)
            
            team_data.append(team_info)
        
        # Direct consortium access
        direct_consortium_access = []
        all_consortiums = Consortium.query.all()
        for consortium in all_consortiums:
            viewer_users = consortium.get_rfpo_viewer_users()
            admin_users = consortium.get_rfpo_admin_users()
            
            access_type = None
            if user.record_id in admin_users:
                access_type = 'admin'
            elif user.record_id in viewer_users:
                access_type = 'viewer'
            
            if access_type:
                direct_consortium_access.append({
                    'consort_id': consortium.consort_id,
                    'name': consortium.name,
                    'abbrev': consortium.abbrev,
                    'access_type': access_type
                })
                accessible_consortium_ids.add(consortium.consort_id)
        
        # Project access
        project_access = []
        all_projects = Project.query.all()
        accessible_project_ids = []
        
        for project in all_projects:
            viewer_users = project.get_rfpo_viewer_users()
            if user.record_id in viewer_users:
                project_access.append({
                    'project_id': project.project_id,
                    'name': project.name,
                    'ref': project.ref,
                    'consortium_ids': project.get_consortium_ids()
                })
                accessible_project_ids.append(project.project_id)
        
        # Calculate accessible RFPOs
        accessible_rfpos = []
        
        # 1. RFPOs from user's teams
        team_ids = [team.id for team in user_teams]
        if team_ids:
            team_rfpos = RFPO.query.filter(RFPO.team_id.in_(team_ids)).all()
            accessible_rfpos.extend(team_rfpos)
        
        # 2. RFPOs from projects user has access to
        if accessible_project_ids:
            project_rfpos = RFPO.query.filter(RFPO.project_id.in_(accessible_project_ids)).all()
            accessible_rfpos.extend(project_rfpos)
        
        # Remove duplicates
        accessible_rfpos = list({rfpo.id: rfpo for rfpo in accessible_rfpos}.values())
        
        rfpo_summary = []
        for rfpo in accessible_rfpos[:10]:  # Limit to first 10 for performance
            rfpo_summary.append({
                'id': rfpo.id,
                'rfpo_id': rfpo.rfpo_id,
                'title': rfpo.title,
                'status': rfpo.status,
                'total_amount': float(rfpo.total_amount or 0),
                'created_at': rfpo.created_at.isoformat() if rfpo.created_at else None
            })
        
        # Approval workflow access (for users with admin permissions)
        approval_access = []
        if user.is_rfpo_admin() or user.is_super_admin():
            # They can see all approval workflows
            approval_access = ['All approval workflows (Admin access)']
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'record_id': user.record_id,
                'email': user.email,
                'display_name': user.get_display_name()
            },
            'permissions_summary': {
                'system_permissions': system_permissions,
                'is_super_admin': user.is_super_admin(),
                'is_rfpo_admin': user.is_rfpo_admin(),
                'is_rfpo_user': user.is_rfpo_user(),
                'team_associations': team_data,
                'direct_consortium_access': direct_consortium_access,
                'project_access': project_access,
                'accessible_rfpos_count': len(accessible_rfpos),
                'accessible_rfpos_sample': rfpo_summary,
                'approval_access': approval_access,
                'summary_counts': {
                    'teams': len(team_data),
                    'consortiums': len(accessible_consortium_ids),
                    'projects': len(project_access),
                    'rfpos': len(accessible_rfpos)
                }
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@user_api.route('/approver-status', methods=['GET'])
@require_auth
def get_user_approver_status():
    """Get detailed approver status for current user"""
    try:
        user = request.current_user
        approver_info = user.check_approver_status()
        approver_summary = user.get_approver_summary()
        
        return jsonify({
            'success': True,
            'user_id': user.id,
            'record_id': user.record_id,
            'is_approver': user.is_approver,
            'approver_updated_at': user.approver_updated_at.isoformat() if user.approver_updated_at else None,
            'approver_info': approver_info,
            'approver_summary': approver_summary
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@user_api.route('/sync-approver-status', methods=['POST'])
@require_auth
def sync_user_approver_status():
    """Sync approver status for current user (force refresh)"""
    try:
        user = request.current_user
        status_changed = user.update_approver_status(updated_by=user.email)
        
        if status_changed:
            db.session.commit()
            message = f"Approver status updated to: {'Approver' if user.is_approver else 'Not an approver'}"
        else:
            message = "Approver status is already up to date"
        
        return jsonify({
            'success': True,
            'message': message,
            'status_changed': status_changed,
            'is_approver': user.is_approver,
            'approver_summary': user.get_approver_summary()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
