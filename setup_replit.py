#!/usr/bin/env python3
"""
Replit Setup Helper
Run this script to verify your Replit deployment is ready
"""

import os
import sys
import json

def check_replit_setup():
    """Check if all files are ready for Replit deployment"""
    
    print("Checking Replit Deployment Setup")
    print("=" * 50)
    
    required_files = [
        'main.py',
        'requirements.txt', 
        '.replit',
        'replit.nix',
        'backend/app.py',
        'frontend/index.html',
        'backend/services/market_data.py'
    ]
    
    missing_files = []
    present_files = []
    
    for file_path in required_files:
        if os.path.exists(file_path):
            present_files.append(file_path)
            print(f"[OK] {file_path}")
        else:
            missing_files.append(file_path)
            print(f"[MISSING] {file_path}")
    
    print("\n" + "=" * 50)
    
    if missing_files:
        print(f"WARNING: {len(missing_files)} files are missing:")
        for file in missing_files:
            print(f"   - {file}")
        print("\nPlease ensure all files are uploaded to Replit.")
        return False
    else:
        print(f"SUCCESS: All {len(present_files)} required files are present!")
        
    # Check if we're running on Replit
    if 'REPL_SLUG' in os.environ:
        print("Running on Replit!")
        print(f"   Repl name: {os.environ.get('REPL_SLUG', 'unknown')}")
        print(f"   User: {os.environ.get('REPL_OWNER', 'unknown')}")
    else:
        print("Running locally (not on Replit)")
    
    # Check environment variables
    print("\nEnvironment Variables:")
    env_vars = ['PORT', 'REDDIT_CLIENT_ID', 'REDDIT_CLIENT_SECRET']
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            if 'SECRET' in var:
                print(f"   {var}: ***hidden***")
            else:
                print(f"   {var}: {value}")
        else:
            print(f"   {var}: Not set")
    
    print("\n" + "=" * 50)
    print("Setup check complete!")
    
    if 'REPL_SLUG' in os.environ:
        print("\nNext steps:")
        print("1. Click the 'Run' button to start your app")
        print("2. Open the web view to access the portfolio analyzer")
        print("3. Login with: admin / portfolio123")
        print("4. Upload a CSV file to test the functionality")
    else:
        print("\nTo deploy to Replit:")
        print("1. Go to replit.com")
        print("2. Create a new Python Repl")
        print("3. Upload all your project files")
        print("4. Run this setup script again on Replit")
    
    return True

if __name__ == '__main__':
    try:
        success = check_replit_setup()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nERROR: Error during setup check: {e}")
        sys.exit(1)