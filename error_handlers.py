"""
Flask Error Handlers for RFPO Application

Provides centralized error handling for Flask applications with proper
logging and user-friendly error responses.
"""

from flask import jsonify, render_template, request
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from exceptions import (
    RFPOException, DatabaseException, AuthenticationException,
    AuthorizationException, ValidationException, ResourceNotFoundException
)
from logging_config import get_logger, log_exception


def register_error_handlers(app, app_name='rfpo'):
    """
    Register all error handlers for a Flask application
    
    Args:
        app: Flask application instance
        app_name: Application name for logging
    """
    logger = get_logger(app_name)
    
    @app.errorhandler(RFPOException)
    def handle_rfpo_exception(error):
        """Handle custom RFPO exceptions"""
        log_exception(logger, error, {
            'path': request.path,
            'method': request.method,
            'ip': request.remote_addr
        })
        
        response = {
            'success': False,
            'error': error.message,
            'error_type': error.__class__.__name__
        }
        
        # Add additional payload data if available
        if error.payload:
            response['details'] = error.payload
        
        # Return JSON for API requests, HTML for web requests
        if request.path.startswith('/api/'):
            return jsonify(response), error.status_code
        else:
            return render_template(
                'error.html',
                error=error.message,
                status_code=error.status_code
            ), error.status_code
    
    @app.errorhandler(DatabaseException)
    def handle_database_exception(error):
        """Handle database-related errors"""
        logger.error(
            f'Database error: {error.message}',
            extra={'path': request.path, 'method': request.method}
        )
        
        response = {
            'success': False,
            'error': 'A database error occurred. Please try again later.',
            'error_type': 'DatabaseException'
        }
        
        if request.path.startswith('/api/'):
            return jsonify(response), 500
        else:
            return render_template(
                'error.html',
                error='Database error. Please try again later.',
                status_code=500
            ), 500
    
    @app.errorhandler(SQLAlchemyError)
    def handle_sqlalchemy_error(error):
        """Handle SQLAlchemy errors"""
        log_exception(logger, error, {
            'path': request.path,
            'method': request.method
        })
        
        response = {
            'success': False,
            'error': 'A database error occurred. Please try again later.',
            'error_type': 'SQLAlchemyError'
        }
        
        if request.path.startswith('/api/'):
            return jsonify(response), 500
        else:
            return render_template(
                'error.html',
                error='Database error. Please try again later.',
                status_code=500
            ), 500
    
    @app.errorhandler(AuthenticationException)
    def handle_authentication_exception(error):
        """Handle authentication failures"""
        logger.warning(
            f'Authentication failed: {error.message}',
            extra={'path': request.path, 'ip': request.remote_addr}
        )
        
        response = {
            'success': False,
            'error': error.message,
            'error_type': 'AuthenticationException'
        }
        
        if request.path.startswith('/api/'):
            return jsonify(response), 401
        else:
            return render_template(
                'error.html',
                error=error.message,
                status_code=401
            ), 401
    
    @app.errorhandler(AuthorizationException)
    def handle_authorization_exception(error):
        """Handle authorization failures"""
        logger.warning(
            f'Authorization denied: {error.message}',
            extra={'path': request.path, 'ip': request.remote_addr}
        )
        
        response = {
            'success': False,
            'error': error.message,
            'error_type': 'AuthorizationException'
        }
        
        if request.path.startswith('/api/'):
            return jsonify(response), 403
        else:
            return render_template(
                'error.html',
                error=error.message,
                status_code=403
            ), 403
    
    @app.errorhandler(ValidationException)
    def handle_validation_exception(error):
        """Handle validation errors"""
        logger.info(
            f'Validation error: {error.message}',
            extra={'path': request.path}
        )
        
        response = {
            'success': False,
            'error': error.message,
            'error_type': 'ValidationException'
        }
        
        if error.payload:
            response['validation_errors'] = error.payload
        
        if request.path.startswith('/api/'):
            return jsonify(response), 400
        else:
            return render_template(
                'error.html',
                error=error.message,
                status_code=400
            ), 400
    
    @app.errorhandler(ResourceNotFoundException)
    def handle_not_found_exception(error):
        """Handle resource not found errors"""
        logger.info(
            f'Resource not found: {error.message}',
            extra={'path': request.path}
        )
        
        response = {
            'success': False,
            'error': error.message,
            'error_type': 'ResourceNotFoundException'
        }
        
        if request.path.startswith('/api/'):
            return jsonify(response), 404
        else:
            return render_template(
                'error.html',
                error=error.message,
                status_code=404
            ), 404
    
    @app.errorhandler(404)
    def handle_404(error):
        """Handle 404 Not Found"""
        logger.info(f'404 Not Found: {request.path}')
        
        if request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'error': 'Endpoint not found',
                'error_type': 'NotFound'
            }), 404
        else:
            return render_template(
                'error.html',
                error='Page not found',
                status_code=404
            ), 404
    
    @app.errorhandler(500)
    def handle_500(error):
        """Handle 500 Internal Server Error"""
        log_exception(logger, error, {
            'path': request.path,
            'method': request.method
        })
        
        if request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'error': 'Internal server error',
                'error_type': 'InternalServerError'
            }), 500
        else:
            return render_template(
                'error.html',
                error='Internal server error. Please try again later.',
                status_code=500
            ), 500
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        """Handle all other HTTP exceptions"""
        logger.warning(
            f'HTTP {error.code}: {error.description}',
            extra={'path': request.path}
        )
        
        if request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'error': error.description,
                'error_type': error.name
            }), error.code
        else:
            return render_template(
                'error.html',
                error=error.description,
                status_code=error.code
            ), error.code
    
    @app.errorhandler(Exception)
    def handle_unexpected_exception(error):
        """Handle all unexpected exceptions"""
        log_exception(logger, error, {
            'path': request.path,
            'method': request.method,
            'ip': request.remote_addr
        })
        
        if request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'error': 'An unexpected error occurred',
                'error_type': 'UnexpectedException'
            }), 500
        else:
            return render_template(
                'error.html',
                error='An unexpected error occurred. Please try again later.',
                status_code=500
            ), 500
    
    logger.info(f'Error handlers registered for {app_name}')
