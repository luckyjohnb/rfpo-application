from flask import Flask, render_template, request, jsonify, send_file
import os
import uuid
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from functools import wraps

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-for-testing'
app.config['UPLOAD_FOLDER'] = 'uploads'

# Create directories
os.makedirs('uploads', exist_ok=True)
os.makedirs('config', exist_ok=True)

@app.route('/')
def landing():
    """Landing page"""
    try:
        return render_template('landing.html')
    except Exception as e:
        return f"""
        <h1>🎉 Flask is Working!</h1>
        <p>Template loading failed, but Flask is running.</p>
        <p>Error: {str(e)}</p>
        <a href="/hello">Try Hello Page</a> | <a href="/test">Try Test API</a>
        """

@app.route('/hello')
def hello():
    """Simple hello world"""
    return '<h1>🎉 Flask is Working!</h1><p>Your Flask application is running successfully.</p><a href="/app">Go to Main App</a> | <a href="/test">Test API</a>'

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
        'routes': ['/hello', '/test', '/app', '/']
    })

# Error Handlers
@app.errorhandler(404)
def not_found(error):
    return f"""
    <h1>404 - Page Not Found</h1>
    <p>The requested URL was not found on the server.</p>
    <p><a href="/hello">Go to Hello Page</a></p>
    <p><a href="/test">Go to Test API</a></p>
    """, 404

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 SIMPLE FLASK APPLICATION STARTING")
    print("=" * 60)
    print("🌐 Server: http://127.0.0.1:5000")
    print("📝 Test these URLs:")
    print("   http://127.0.0.1:5000/hello")
    print("   http://127.0.0.1:5000/test")
    print("   http://127.0.0.1:5000/")
    print("=" * 60)
    
    app.run(debug=True, host='127.0.0.1', port=5000)
