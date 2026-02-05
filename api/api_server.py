"""
Standalone API Server
Can be run independently or imported by other applications
"""

from flask import Flask, jsonify
from flask_cors import CORS
import os
from datetime import datetime

# Import models and initialize database
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db

# Import API blueprints
from auth_routes import auth_api
from team_routes import team_api
from rfpo_routes import rfpo_api
from user_routes import user_api

# Import error handling
from error_handlers import register_error_handlers
from logging_config import setup_logging

def create_api_app():
    """Create Flask API application"""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('API_SECRET_KEY', 'api-secret-key-change-in-production')
    # Get the parent directory (project root) and then the database path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(project_root, 'instance', 'rfpo_admin.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', f'sqlite:///{db_path}')
    print(f"DEBUG: Database path: {db_path}")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Setup logging
    logger = setup_logging('api', log_to_file=True)
    app.logger = logger
    
    # Register error handlers
    register_error_handlers(app, 'api')
    
    # Enable CORS for all origins (configure for production)
    CORS(app, origins="*", allow_headers=["Content-Type", "Authorization"])
    
    # Initialize extensions
    db.init_app(app)
    
    # Register blueprints
    app.register_blueprint(auth_api)
    app.register_blueprint(team_api)
    app.register_blueprint(rfpo_api)
    app.register_blueprint(user_api)
    
    # Health check endpoint
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """API health check"""
        return jsonify({
            'status': 'healthy',
            'service': 'RFPO API',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0'
        })
    
    # Root endpoint
    @app.route('/api', methods=['GET'])
    def api_root():
        """API root endpoint"""
        return jsonify({
            'message': 'RFPO API Server',
            'version': '1.0.0',
            'endpoints': {
                'health': '/api/health',
                'auth': '/api/auth',
                'teams': '/api/teams',
                'rfpos': '/api/rfpos'
            },
            'timestamp': datetime.utcnow().isoformat()
        })
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'success': False, 'message': 'Endpoint not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({'success': False, 'message': 'Bad request'}), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403
    
    return app

# For standalone execution
if __name__ == '__main__':
    app = create_api_app()
    
    # Create tables if they don't exist
    with app.app_context():
        db.create_all()
        print("✅ Database tables created/verified")
    
    print("=" * 60)
    print("🚀 RFPO API SERVER STARTING")
    print("=" * 60)
    print(f"🌐 Server: http://127.0.0.1:5003")
    print(f"🔍 Health Check: http://127.0.0.1:5003/api/health")
    print(f"📋 Endpoints: http://127.0.0.1:5003/api")
    print("=" * 60)
    
    app.run(debug=True, host='127.0.0.1', port=5003)
