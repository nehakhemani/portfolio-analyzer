"""
Minimal version of the main app to isolate import issues
"""
from flask import Flask, jsonify, request, session
from flask_cors import CORS
import os
import sqlite3
from datetime import datetime

print("Basic imports successful")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'temp-secret-for-debug'
CORS(app, origins="*", supports_credentials=True)

print("Flask app configured")

# Basic database setup
def init_minimal_db():
    try:
        db_path = '/tmp/portfolio.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY, name TEXT)''')
        conn.commit()
        conn.close()
        return f"Database initialized at {db_path}"
    except Exception as e:
        return f"Database error: {str(e)}"

print("Database function defined")

@app.route('/')
def home():
    return jsonify({
        'status': 'Minimal Portfolio Analyzer',
        'database': init_minimal_db(),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/test-imports')
def test_imports():
    """Test importing the problematic modules one by one"""
    results = {}
    
    try:
        import pandas as pd
        results['pandas'] = f"OK - {pd.__version__}"
    except Exception as e:
        results['pandas'] = f"ERROR - {str(e)}"
    
    try:
        import numpy as np
        results['numpy'] = f"OK - {np.__version__}"
    except Exception as e:
        results['numpy'] = f"ERROR - {str(e)}"
    
    try:
        import yfinance as yf
        results['yfinance'] = "OK"
    except Exception as e:
        results['yfinance'] = f"ERROR - {str(e)}"
    
    try:
        from services.market_data import MarketDataService
        results['market_data'] = "OK"
    except Exception as e:
        results['market_data'] = f"ERROR - {str(e)}"
    
    try:
        from auth import security_manager
        results['auth'] = "OK"
    except Exception as e:
        results['auth'] = f"ERROR - {str(e)}"
    
    return jsonify(results)

print("Routes defined")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting minimal server on port {port}")
    app.run(debug=False, host='0.0.0.0', port=port)
else:
    print("Minimal app loaded as WSGI module")