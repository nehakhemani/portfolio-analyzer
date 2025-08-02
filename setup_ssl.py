#!/usr/bin/env python3
"""
SSL/HTTPS Setup for Portfolio Analyzer
Generates self-signed certificates for HTTPS
"""

import os
import sys
import subprocess
from datetime import datetime, timedelta

def check_openssl():
    """Check if OpenSSL is available"""
    try:
        result = subprocess.run(['openssl', 'version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"OpenSSL found: {result.stdout.strip()}")
            return True
        return False
    except FileNotFoundError:
        return False

def generate_self_signed_cert():
    """Generate self-signed SSL certificate"""
    cert_dir = os.path.join(os.path.dirname(__file__), 'ssl')
    os.makedirs(cert_dir, exist_ok=True)
    
    key_file = os.path.join(cert_dir, 'server.key')
    cert_file = os.path.join(cert_dir, 'server.crt')
    
    # Generate private key
    key_cmd = [
        'openssl', 'genrsa', '-out', key_file, '2048'
    ]
    
    # Generate certificate
    cert_cmd = [
        'openssl', 'req', '-new', '-x509', '-key', key_file,
        '-out', cert_file, '-days', '365',
        '-subj', '/C=US/ST=State/L=City/O=Portfolio Analyzer/CN=localhost'
    ]
    
    try:
        print("Generating private key...")
        result = subprocess.run(key_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error generating key: {result.stderr}")
            return None, None
        
        print("Generating certificate...")
        result = subprocess.run(cert_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error generating certificate: {result.stderr}")
            return None, None
        
        print(f"SSL certificate generated successfully!")
        print(f"Key file: {key_file}")
        print(f"Certificate file: {cert_file}")
        
        return key_file, cert_file
        
    except Exception as e:
        print(f"Error generating SSL certificate: {e}")
        return None, None

def create_https_server():
    """Create HTTPS server configuration"""
    https_server_code = '''#!/usr/bin/env python3
"""
HTTPS Portfolio Analyzer Server
"""

import os
import sys
import ssl
from flask import Flask

# Add backend to path
backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_dir)

from app import app

def main():
    print("="*70)
    print("SECURE PORTFOLIO ANALYZER (HTTPS)")
    print("="*70)
    
    # SSL configuration
    ssl_dir = os.path.join(os.path.dirname(__file__), 'ssl')
    cert_file = os.path.join(ssl_dir, 'server.crt')
    key_file = os.path.join(ssl_dir, 'server.key')
    
    if not os.path.exists(cert_file) or not os.path.exists(key_file):
        print("SSL certificates not found!")
        print("Run: python setup_ssl.py")
        return
    
    # Configure SSL context
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_file, key_file)
    
    # Enable secure session cookies for HTTPS
    app.config['SESSION_COOKIE_SECURE'] = True
    
    print("Server will start with HTTPS encryption")
    print("Access URL: https://localhost:5443")
    print("Note: You'll see a security warning (self-signed certificate)")
    print("Click 'Advanced' and 'Proceed to localhost' in your browser")
    print("="*70)
    
    try:
        app.run(
            host='0.0.0.0',
            port=5443,
            ssl_context=context,
            debug=False,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\\nHTTPS server stopped")

if __name__ == "__main__":
    main()
'''
    
    https_server_path = os.path.join(os.path.dirname(__file__), 'start_https_server.py')
    with open(https_server_path, 'w') as f:
        f.write(https_server_code)
    
    print(f"HTTPS server script created: {https_server_path}")

def main():
    print("="*70)
    print("SSL/HTTPS SETUP FOR PORTFOLIO ANALYZER")
    print("="*70)
    
    # Check OpenSSL
    if not check_openssl():
        print("OpenSSL not found!")
        print("Please install OpenSSL:")
        print("- Windows: Download from https://slproweb.com/products/Win32OpenSSL.html")
        print("- Or use Git Bash which includes OpenSSL")
        return
    
    # Generate certificate
    key_file, cert_file = generate_self_signed_cert()
    if not key_file or not cert_file:
        print("Failed to generate SSL certificate")
        return
    
    # Create HTTPS server
    create_https_server()
    
    print("\\n" + "="*70)
    print("SSL SETUP COMPLETE!")
    print("="*70)
    print("Next steps:")
    print("1. Run: python start_https_server.py")
    print("2. Access: https://localhost:5443")
    print("3. Accept the security warning in your browser")
    print("\\nFor production, use a real SSL certificate from:")
    print("- Let's Encrypt (free)")
    print("- Commercial SSL provider")
    print("="*70)

if __name__ == "__main__":
    main()