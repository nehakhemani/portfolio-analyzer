#!/usr/bin/env python3
"""
Portfolio Analyzer Setup Script
"""

import os
import sys
import subprocess

def create_directories():
    """Create necessary directories"""
    dirs = [
        'backend/models',
        'backend/services',
        'backend/utils',
        'backend/data',
        'frontend/css',
        'frontend/js',
        'uploads'
    ]
    
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)
        # Create __init__.py files for Python packages
        if dir_path.startswith('backend/') and '/' in dir_path[8:]:
            init_file = os.path.join(dir_path, '__init__.py')
            open(init_file, 'a').close()

def install_requirements():
    """Install Python requirements"""
    print("Installing Python requirements...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'backend/requirements.txt'])

def create_env_file():
    """Create .env file for configuration"""
    env_content = """# Portfolio Analyzer Configuration
DATABASE_PATH=backend/data/portfolio.db
UPLOAD_FOLDER=uploads
SECRET_KEY=your-secret-key-here
DEBUG=True
PORT=5000
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)

def main():
    print("Setting up Portfolio Analyzer...")
    
    # Create directory structure
    create_directories()
    print("✓ Created directory structure")
    
    # Install requirements
    install_requirements()
    print("✓ Installed Python requirements")
    
    # Create environment file
    create_env_file()
    print("✓ Created .env configuration file")
    
    print("\nSetup complete! To run the application:")
    print("1. cd backend")
    print("2. python app.py")
    print("3. Open http://localhost:5000 in your browser")

if __name__ == "__main__":
    main()