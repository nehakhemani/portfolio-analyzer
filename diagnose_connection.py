#!/usr/bin/env python3
"""
Connection Diagnostic Tool for Portfolio Analyzer
"""

import socket
import subprocess
import requests
import time
from datetime import datetime

def get_local_ip():
    """Get local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def check_port_listening(host, port):
    """Check if port is listening"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

def test_http_request(url):
    """Test HTTP request"""
    try:
        response = requests.get(url, timeout=5)
        return response.status_code, response.headers.get('server', 'Unknown')
    except requests.exceptions.Timeout:
        return None, "Timeout"
    except requests.exceptions.ConnectionError:
        return None, "Connection Error"
    except Exception as e:
        return None, str(e)

def check_firewall_rule():
    """Check Windows Firewall rule"""
    try:
        result = subprocess.run([
            'netsh', 'advfirewall', 'firewall', 'show', 'rule', 
            'name=Portfolio Analyzer Port 5001'
        ], capture_output=True, text=True)
        
        if "No rules match" in result.stdout:
            return False, "Rule not found"
        else:
            return True, "Rule exists"
    except:
        return False, "Could not check"

def main():
    print("=" * 70)
    print("PORTFOLIO ANALYZER - CONNECTION DIAGNOSTIC")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Get network info
    local_ip = get_local_ip()
    port = 5001
    
    print(f"\\nNetwork Information:")
    print(f"  Local IP: {local_ip}")
    print(f"  Port: {port}")
    
    # Test 1: Port listening
    print(f"\\n1. Port Listening Tests:")
    localhost_listening = check_port_listening('127.0.0.1', port)
    external_listening = check_port_listening(local_ip, port)
    
    print(f"  localhost:{port} -> {'[OK] LISTENING' if localhost_listening else '[X] NOT LISTENING'}")
    print(f"  {local_ip}:{port} -> {'[OK] LISTENING' if external_listening else '[X] NOT LISTENING'}")
    
    # Test 2: HTTP Requests
    print(f"\\n2. HTTP Request Tests:")
    
    # Test localhost
    localhost_url = f"http://localhost:{port}"
    status, server = test_http_request(localhost_url)
    print(f"  {localhost_url}")
    print(f"    Status: {status if status else 'FAILED'}")
    print(f"    Server: {server}")
    
    # Test external IP
    external_url = f"http://{local_ip}:{port}"
    status, server = test_http_request(external_url)
    print(f"  {external_url}")
    print(f"    Status: {status if status else 'FAILED'}")
    print(f"    Server: {server}")
    
    # Test 3: Firewall
    print(f"\\n3. Windows Firewall:")
    firewall_ok, firewall_msg = check_firewall_rule()
    print(f"  Firewall rule: {'[OK]' if firewall_ok else '[X]'} {firewall_msg}")
    
    # Test 4: Process check
    print(f"\\n4. Process Information:")
    try:
        result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
        lines = [line for line in result.stdout.split('\\n') if f':{port}' in line and 'LISTENING' in line]
        print(f"  Active processes on port {port}:")
        for line in lines:
            parts = line.split()
            if len(parts) >= 5:
                print(f"    PID {parts[-1]}: {parts[1]}")
    except:
        print("  Could not check processes")
    
    # Recommendations
    print(f"\\n" + "=" * 70)
    print("TROUBLESHOOTING RECOMMENDATIONS:")
    print("=" * 70)
    
    if not localhost_listening:
        print("[!] CRITICAL: Server not running!")
        print("   -> Run: python start_server.py")
    
    elif not external_listening:
        print("[!] CRITICAL: Server not binding to external interface!")
        print("   -> Check if server started with host='0.0.0.0'")
    
    elif not firewall_ok:
        print("[!] WARNING: Firewall rule missing!")
        print("   -> Run as Administrator: python start_server.py")
        print("   -> Or manually allow port 5001 in Windows Defender Firewall")
    
    else:
        print("[OK] Server appears to be running correctly!")
        print("\\nIf you still can't connect:")
        print("1. Try these URLs:")
        print(f"   - http://localhost:{port}")
        print(f"   - http://127.0.0.1:{port}")
        print(f"   - http://{local_ip}:{port}")
        print("\\n2. Check your browser:")
        print("   - Clear browser cache (Ctrl+F5)")
        print("   - Try incognito/private mode")
        print("   - Try a different browser")
        print("\\n3. Check network:")
        print("   - Disable VPN if active")
        print("   - Check if antivirus is blocking")
        print("   - Ensure devices on same WiFi network")
    
    print("\\n" + "=" * 70)
    print(f"Share this URL with others: http://{local_ip}:{port}")
    print("=" * 70)

if __name__ == "__main__":
    main()