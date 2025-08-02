#!/usr/bin/env python3
"""
Portfolio Analyzer Production Server
Run this to start the server with external access
"""

import os
import sys
import subprocess
import socket
from datetime import datetime

def get_local_ip():
    """Get the local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def setup_firewall():
    """Setup Windows Firewall rule"""
    try:
        # Check if rule already exists
        check_cmd = ['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name=Portfolio Analyzer Port 5001']
        result = subprocess.run(check_cmd, capture_output=True, text=True)
        
        if "No rules match" in result.stdout:
            # Add the rule
            add_cmd = [
                'netsh', 'advfirewall', 'firewall', 'add', 'rule',
                'name=Portfolio Analyzer Port 5001',
                'dir=in', 'action=allow', 'protocol=TCP',
                'localport=5001'
            ]
            subprocess.run(add_cmd, capture_output=True)
            print("+ Firewall rule added for port 5001")
        else:
            print("+ Firewall rule already exists")
    except Exception as e:
        print(f"Warning: Could not configure firewall: {e}")
        print("Note: You may need to manually allow port 5001 in Windows Firewall")

def main():
    print("="*70)
    print("PORTFOLIO ANALYZER - EXTERNAL ACCESS SERVER")
    print("="*70)
    
    # Get network information
    local_ip = get_local_ip()
    port = 5001
    
    print(f"Server IP: {local_ip}")
    print(f"Server Port: {port}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Setup firewall
    print("\nConfiguring Windows Firewall...")
    setup_firewall()
    
    print(f"\nACCESS URLS:")
    print(f"   Local: http://localhost:{port}")
    print(f"   Network: http://{local_ip}:{port}")
    print(f"   Any device on your network can access: http://{local_ip}:{port}")
    
    print(f"\nSHARE INSTRUCTIONS:")
    print(f"   1. Make sure devices are on the same WiFi network")
    print(f"   2. Give them this URL: http://{local_ip}:{port}")
    print(f"   3. They can access from phone, tablet, or computer")
    
    print(f"\nSECURITY NOTES:")
    print(f"   + Only accessible on your local network")
    print(f"   + For internet access, use ngrok or port forwarding")
    print(f"   + Server runs with basic security headers")
    
    print("\n" + "="*70)
    print("STARTING SERVER...")
    print("Press Ctrl+C to stop")
    print("="*70 + "\n")
    
    # Change to backend directory and start server
    backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
    os.chdir(backend_dir)
    sys.path.insert(0, backend_dir)
    
    try:
        # Import and run the Flask app
        from app import app
        app.run(debug=False, host='0.0.0.0', port=port, threaded=True)
    except KeyboardInterrupt:
        print(f"\n\nServer stopped at {datetime.now().strftime('%H:%M:%S')}")
        print("Thanks for using Portfolio Analyzer!")
    except Exception as e:
        print(f"\nServer error: {e}")
        print("Make sure all dependencies are installed")

if __name__ == "__main__":
    main()