#!/usr/bin/env python3
"""
Simple Flask App Debug Version
Test if basic Flask functionality works
"""
from flask import Flask, jsonify
import os

# Create simple Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'test-secret-key'

@app.route('/')
def home():
    return '''
    <h1>🎉 Flask Debug App is Working!</h1>
    <p>This confirms Flask is running properly.</p>
    <ul>
        <li><a href="/hello">Hello Test</a></li>
        <li><a href="/test">JSON Test</a></li>
        <li><a href="/debug">Debug Info</a></li>
    </ul>
    '''

@app.route('/hello')
def hello():
    return '<h1>🎉 Hello World!</h1><p>The /hello route is working perfectly.</p><a href="/">← Back to Home</a>'

@app.route('/test')
def test():
    return jsonify({
        'status': 'success',
        'message': 'Flask is working correctly!',
        'routes': ['/', '/hello', '/test', '/debug']
    })

@app.route('/debug')
def debug():
    return f'''
    <h1>🔍 Debug Information</h1>
    <p><strong>Flask App:</strong> Running</p>
    <p><strong>Python Version:</strong> {os.sys.version}</p>
    <p><strong>Current Directory:</strong> {os.getcwd()}</p>
    <p><strong>App Name:</strong> {app.name}</p>
    <p><strong>Debug Mode:</strong> {app.debug}</p>
    <a href="/">← Back to Home</a>
    '''

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 FLASK DEBUG APP STARTING")
    print("=" * 50)
    print("🌐 Server: http://127.0.0.1:5000")
    print("📝 Routes available:")
    print("   http://127.0.0.1:5000/")
    print("   http://127.0.0.1:5000/hello")
    print("   http://127.0.0.1:5000/test")
    print("   http://127.0.0.1:5000/debug")
    print("=" * 50)
    
    app.run(debug=True, host='127.0.0.1', port=5000)
