"""
Minimal Flask app for debugging cloud deployment issues
"""
from flask import Flask, jsonify
import os
from datetime import datetime

print("Starting debug app initialization...")

app = Flask(__name__)

print("Flask app created")

@app.route('/')
def home():
    """Basic home route"""
    return jsonify({
        'message': 'Portfolio Analyzer Debug Mode',
        'status': 'running',
        'timestamp': datetime.now().isoformat(),
        'env': {
            'PORT': os.environ.get('PORT', 'not set'),
            'PWD': os.environ.get('PWD', 'not set'),
            'PYTHONPATH': os.environ.get('PYTHONPATH', 'not set')
        }
    })

@app.route('/health')
def health():
    """Health check"""
    return jsonify({'status': 'healthy'}), 200

@app.route('/test')
def test():
    """Test route"""
    try:
        import pandas as pd
        import numpy as np
        return jsonify({
            'status': 'dependencies ok',
            'pandas': str(pd.__version__),
            'numpy': str(np.__version__)
        })
    except Exception as e:
        return jsonify({
            'status': 'dependency error',
            'error': str(e)
        }), 500

print("Routes defined")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting debug server on port {port}")
    app.run(debug=True, host='0.0.0.0', port=port)
else:
    print("Debug app loaded as WSGI module")