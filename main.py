#!/usr/bin/env python3
"""
Portfolio Analyzer - Replit Entry Point
Main entry point for Replit deployment
"""

import os
import sys

# Add backend to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Import and run the Flask app
from app import app, init_db

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 Portfolio Analyzer Starting on Replit")
    print("="*50)
    
    # Initialize database
    init_db()
    print("✅ Database initialized")
    
    # Get port from environment (Replit sets this automatically)
    port = int(os.environ.get('PORT', 5000))
    
    print(f"✅ Server starting on port {port}")
    print("🌐 Your app will be available at your Replit URL")
    print("📊 Navigate to the web view to access the portfolio analyzer")
    print("="*50 + "\n")
    
    # Run Flask app
    app.run(
        debug=True,  # Enable debug mode for development
        host='0.0.0.0',  # Listen on all interfaces
        port=port,
        threaded=True  # Enable threading for better performance
    )