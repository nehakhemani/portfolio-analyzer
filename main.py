#!/usr/bin/env python3


import os
import sys
 
# Add backend directory to Python path
backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_dir)
sys.path.insert(0, os.path.dirname(__file__))
 
# Now import the Flask app
from backend.app import app, init_db
 
if __name__ == '__main__':
    # Initialize database
    init_db()
 
    # Get port from environment
    port = int(os.environ.get('PORT', 8080))
 
    # Run Flask app
    app.run(
        debug=False,
        host='0.0.0.0',
        port=port,
        threaded=True
    )
 
# For gunicorn
application = app