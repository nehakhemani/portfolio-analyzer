#!/usr/bin/env python3
"""
Portfolio Analyzer Deployment Script
Allows external access to your portfolio analyzer
"""

import os
import sys
import socket
import subprocess
from datetime import datetime

def get_local_ip():
    """Get the local IP address"""
    try:
        # Connect to a remote server to get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def check_firewall():
    """Check Windows Firewall status"""
    try:
        result = subprocess.run(['netsh', 'advfirewall', 'show', 'allprofiles'], 
                              capture_output=True, text=True)
        return "State                                 ON" in result.stdout
    except:
        return False

def open_firewall_port(port):
    """Open port in Windows Firewall"""
    try:
        # Add inbound rule for the port
        cmd = [
            'netsh', 'advfirewall', 'firewall', 'add', 'rule',
            f'name=Portfolio Analyzer Port {port}',
            'dir=in', 'action=allow', 'protocol=TCP',
            f'localport={port}'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

def main():
    print("="*60)
    print("🚀 PORTFOLIO ANALYZER DEPLOYMENT SETUP")
    print("="*60)
    
    # Get network info
    local_ip = get_local_ip()
    port = 5001
    
    print(f"📍 Local IP Address: {local_ip}")
    print(f"🔌 Server Port: {port}")
    print(f"🌐 Local URL: http://{local_ip}:{port}")
    
    # Check firewall
    print("\n🔥 Checking Windows Firewall...")
    if check_firewall():
        print("   ⚠️  Windows Firewall is ON")
        print(f"   Opening port {port}...")
        
        if open_firewall_port(port):
            print(f"   ✅ Port {port} opened successfully!")
        else:
            print(f"   ❌ Failed to open port {port}")
            print("   💡 You may need to run this script as Administrator")
    else:
        print("   ✅ Windows Firewall is OFF or port already open")
    
    print("\n📋 DEPLOYMENT OPTIONS:")
    print("-" * 40)
    
    print("\n🏠 OPTION 1: Local Network Access")
    print(f"   • URL: http://{local_ip}:{port}")
    print("   • Accessible to devices on your WiFi/LAN")
    print("   • No additional setup needed")
    
    print("\n🌍 OPTION 2: Internet Access (ngrok)")
    print("   • Requires ngrok installation")
    print("   • Creates secure tunnel to internet")
    print("   • Free tier available")
    print("   • Run: ngrok http 5001")
    
    print("\n🔧 OPTION 3: Router Port Forwarding")
    print(f"   • Forward external port to {local_ip}:{port}")
    print("   • Configure in your router settings")
    print("   • Requires static IP or DDNS")
    
    print("\n" + "="*60)
    print("🚀 STARTING PORTFOLIO ANALYZER SERVER")
    print("="*60)
    
    print(f"✅ Server will be accessible at:")
    print(f"   📱 Local: http://localhost:{port}")
    print(f"   🌐 Network: http://{local_ip}:{port}")
    
    print(f"\n🔗 Share this URL with others on your network:")
    print(f"   http://{local_ip}:{port}")
    
    print(f"\n⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📝 Press Ctrl+C to stop the server")
    print("-" * 60)

if __name__ == "__main__":
    main()