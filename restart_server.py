#!/usr/bin/env python3

import os
import signal
import subprocess
import time
import sys

def kill_servers_on_port(port=5001):
    """Kill all processes using the specified port"""
    print(f"Stopping all servers on port {port}...")
    
    try:
        # Windows command to find and kill processes using port 5001
        result = subprocess.run(
            ['netstat', '-ano'], 
            capture_output=True, 
            text=True, 
            shell=True
        )
        
        lines = result.stdout.split('\n')
        pids_to_kill = []
        
        for line in lines:
            if f':{port}' in line and 'LISTENING' in line:
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    if pid.isdigit():
                        pids_to_kill.append(pid)
        
        # Kill the processes
        for pid in set(pids_to_kill):  # Remove duplicates
            try:
                subprocess.run(['taskkill', '/F', '/PID', pid], 
                             capture_output=True, shell=True)
                print(f"Killed process {pid}")
            except Exception as e:
                print(f"Could not kill process {pid}: {e}")
        
        print(f"Stopped {len(set(pids_to_kill))} server processes")
        
    except Exception as e:
        print(f"Error stopping servers: {e}")

def start_server():
    """Start the portfolio analyzer server"""
    print("Starting fresh server...")
    
    try:
        os.chdir('backend')
        print("Changed to backend directory")
        print("Starting python app.py...")
        
        # Start the server
        subprocess.Popen([sys.executable, 'app.py'])
        print("Server started!")
        print("Give it a few seconds to initialize...")
        
    except Exception as e:
        print(f"Error starting server: {e}")

if __name__ == '__main__':
    print("=== Portfolio Analyzer Server Restart ===")
    kill_servers_on_port(5001)
    time.sleep(2)  # Wait for processes to fully stop
    start_server()
    print("\nServer should be running at http://192.168.1.66:5001")
    print("Wait 5-10 seconds, then try accessing the application.")