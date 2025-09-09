"""
RFPO User-Facing Application
Port: 5000
API Consumer Only - All data operations go through API layer
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
import os
import requests
from datetime import datetime
import json

def create_user_app():
    """Create user-facing Flask application"""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('USER_APP_SECRET_KEY', 'user-app-secret-change-in-production')
    
    # Enable CORS
    CORS(app, origins="*", allow_headers=["Content-Type", "Authorization"])
    
    # API Configuration
    API_BASE_URL = os.environ.get('API_BASE_URL', 'http://127.0.0.1:5003/api')
    ADMIN_API_URL = os.environ.get('ADMIN_API_URL', 'http://127.0.0.1:5111/api')
    
    # Helper function to make API calls
    def make_api_request(endpoint, method='GET', data=None, use_admin_api=False):
        """Make API request with authentication"""
        base_url = ADMIN_API_URL if use_admin_api else API_BASE_URL
        url = f"{base_url}{endpoint}"
        
        headers = {'Content-Type': 'application/json'}
        
        # Add auth token if available
        if 'auth_token' in session:
            headers['Authorization'] = f"Bearer {session['auth_token']}"
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=10)
            else:
                return {'success': False, 'message': 'Unsupported method'}
            
            return response.json() if response.content else {'success': True}
            
        except requests.exceptions.RequestException as e:
            return {'success': False, 'message': f'API Error: {str(e)}'}

    # Routes
    @app.route('/')
    def landing():
        """Landing page"""
        return render_template('app/landing.html')
    
    @app.route('/login')
    def login_page():
        """Login page"""
        return render_template('app/login.html')
    
    @app.route('/dashboard')
    def dashboard():
        """Main dashboard"""
        if 'auth_token' not in session:
            return redirect(url_for('login_page'))
        
        # Get user info
        user_info = make_api_request('/auth/verify')
        if not user_info.get('authenticated'):
            session.pop('auth_token', None)
            return redirect(url_for('login_page'))
        
        # Check if this is first login (user needs to change password)
        user_profile = make_api_request('/users/profile')
        if user_profile.get('success'):
            user_data = user_profile['user']
            
            # More robust first-time login detection
            last_visit = user_data.get('last_visit')
            created_at = user_data.get('created_at')
            
            # First login if:
            # 1. No last_visit recorded, OR
            # 2. last_visit is exactly the same as created_at (never updated after creation)
            if not last_visit or (last_visit and created_at and last_visit == created_at):
                # First time login - redirect to password reset page
                return redirect(url_for('first_login_password_reset'))
        
        # Get recent RFPOs
        rfpos_response = make_api_request('/rfpos?per_page=5')
        recent_rfpos = rfpos_response.get('rfpos', []) if rfpos_response.get('success') else []
        
        # Get user's teams
        teams_response = make_api_request('/teams')
        user_teams = teams_response.get('teams', []) if teams_response.get('success') else []
        
        # Get user permissions summary to determine access levels
        permissions_response = make_api_request('/users/permissions-summary')
        user_permissions = permissions_response.get('permissions_summary', {}) if permissions_response.get('success') else {}
        
        # Determine if user has RFPO access
        has_rfpo_access = (
            user_permissions.get('summary_counts', {}).get('rfpos', 0) > 0 or
            user_permissions.get('summary_counts', {}).get('teams', 0) > 0 or
            user_permissions.get('summary_counts', {}).get('projects', 0) > 0 or
            user_permissions.get('is_super_admin', False)
        )
        
        return render_template('app/dashboard.html', 
                             user=user_info.get('user'),
                             recent_rfpos=recent_rfpos,
                             teams=user_teams,
                             user_permissions=user_permissions,
                             has_rfpo_access=has_rfpo_access)
    
    @app.route('/rfpos')
    def rfpos_list():
        """RFPOs list page"""
        if 'auth_token' not in session:
            return redirect(url_for('login_page'))
        
        return render_template('app/rfpos.html')
    
    @app.route('/rfpos/create')
    def rfpo_create():
        """Create RFPO page"""
        if 'auth_token' not in session:
            return redirect(url_for('login_page'))
        
        # Get teams for dropdown
        teams_response = make_api_request('/teams')
        teams = teams_response.get('teams', []) if teams_response.get('success') else []
        
        return render_template('app/rfpo_create.html', teams=teams)
    
    @app.route('/rfpos/<int:rfpo_id>')
    def rfpo_detail(rfpo_id):
        """RFPO detail page"""
        if 'auth_token' not in session:
            return redirect(url_for('login_page'))
        
        return render_template('app/rfpo_detail.html', rfpo_id=rfpo_id)
    
    @app.route('/teams')
    def teams_list():
        """Teams list page"""
        if 'auth_token' not in session:
            return redirect(url_for('login_page'))
        
        return render_template('app/teams.html')
    
    @app.route('/profile')
    def profile():
        """User profile page"""
        if 'auth_token' not in session:
            return redirect(url_for('login_page'))
        
        return render_template('app/profile.html')
    
    @app.route('/first-login-password-reset')
    def first_login_password_reset():
        """First login password reset page - forces password change"""
        if 'auth_token' not in session:
            return redirect(url_for('login_page'))
        
        return render_template('app/first_login_password_reset.html')
    
    # API Proxy Routes (for frontend AJAX calls)
    @app.route('/api/auth/login', methods=['POST'])
    def api_login():
        """Login API proxy"""
        data = request.get_json()
        response = make_api_request('/auth/login', 'POST', data)
        
        if response.get('success') and response.get('token'):
            session['auth_token'] = response['token']
            session['user'] = response['user']
        
        return jsonify(response)
    
    @app.route('/api/auth/logout', methods=['POST'])
    def api_logout():
        """Logout API proxy"""
        session.pop('auth_token', None)
        session.pop('user', None)
        return jsonify({'success': True, 'message': 'Logged out successfully'})
    
    @app.route('/api/auth/verify', methods=['GET'])
    def api_verify():
        """Verify auth API proxy"""
        if 'auth_token' not in session:
            return jsonify({'authenticated': False, 'message': 'No token'}), 401
        
        response = make_api_request('/auth/verify')
        return jsonify(response)
    
    @app.route('/api/rfpos', methods=['GET', 'POST'])
    def api_rfpos():
        """RFPOs API proxy"""
        if request.method == 'GET':
            # Forward query parameters
            params = '&'.join([f"{k}={v}" for k, v in request.args.items()])
            endpoint = f"/rfpos?{params}" if params else "/rfpos"
            response = make_api_request(endpoint)
        else:
            data = request.get_json()
            response = make_api_request('/rfpos', 'POST', data)
        
        return jsonify(response)
    
    @app.route('/api/rfpos/<int:rfpo_id>', methods=['GET', 'PUT', 'DELETE'])
    def api_rfpo_detail(rfpo_id):
        """RFPO detail API proxy"""
        if request.method == 'GET':
            response = make_api_request(f'/rfpos/{rfpo_id}')
        elif request.method == 'PUT':
            data = request.get_json()
            response = make_api_request(f'/rfpos/{rfpo_id}', 'PUT', data)
        else:  # DELETE
            response = make_api_request(f'/rfpos/{rfpo_id}', 'DELETE')
        
        return jsonify(response)

    @app.route('/api/teams', methods=['GET'])
    def api_teams():
        """Teams API proxy"""
        params = '&'.join([f"{k}={v}" for k, v in request.args.items()])
        endpoint = f"/teams?{params}" if params else "/teams"
        response = make_api_request(endpoint)
        return jsonify(response)
    
    @app.route('/api/teams/<int:team_id>', methods=['GET'])
    def api_team_detail(team_id):
        """Team detail API proxy"""
        response = make_api_request(f'/teams/{team_id}')
        return jsonify(response)
    
    @app.route('/api/users/profile', methods=['GET'])
    def api_user_profile():
        """User profile API proxy"""
        response = make_api_request('/users/profile')
        return jsonify(response)
    
    @app.route('/api/users/profile', methods=['PUT'])
    def api_update_profile():
        """Update user profile API proxy"""
        data = request.get_json()
        response = make_api_request('/users/profile', 'PUT', data)
        return jsonify(response)
    
    @app.route('/api/auth/change-password', methods=['POST'])
    def api_change_password():
        """Change password API proxy"""
        data = request.get_json()
        response = make_api_request('/auth/change-password', 'POST', data)
        return jsonify(response)
    
    @app.route('/api/users/permissions-summary', methods=['GET'])
    def api_user_permissions_summary():
        """User permissions summary API proxy"""
        response = make_api_request('/users/permissions-summary')
        return jsonify(response)
    
    # Health check
    @app.route('/health')
    def health_check():
        """Health check endpoint"""
        return jsonify({
            'status': 'healthy',
            'service': 'RFPO User App',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0',
            'api_connection': 'connected' if make_api_request('/health').get('status') == 'healthy' else 'disconnected'
        })
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return render_template('app/error.html', 
                             error_code=404, 
                             error_message='Page not found'), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('app/error.html', 
                             error_code=500, 
                             error_message='Internal server error'), 500

    return app

# Create app instance
app = create_user_app()

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 RFPO USER APPLICATION STARTING")
    print("=" * 60)
    print(f"🌐 Server: http://127.0.0.1:5000")
    print(f"🔍 Health Check: http://127.0.0.1:5000/health")
    print(f"📋 Dashboard: http://127.0.0.1:5000/dashboard")
    print(f"🔐 Login: http://127.0.0.1:5000/login")
    print("=" * 60)

    app.run(debug=True, host='0.0.0.0', port=5000)
