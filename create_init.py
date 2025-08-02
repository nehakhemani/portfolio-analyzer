#!/usr/bin/env python3
"""
Run this script from your portfolio-analyzer root directory
It will create all the necessary __init__.py files
"""

import os

# List of directories that need __init__.py files
directories = [
    'backend',
    'backend/models',
    'backend/services', 
    'backend/utils'
]

# Create __init__.py files
for directory in directories:
    init_file = os.path.join(directory, '__init__.py')
    
    # Create directory if it doesn't exist
    os.makedirs(directory, exist_ok=True)
    
    # Create empty __init__.py file
    with open(init_file, 'w') as f:
        f.write('# This file makes Python treat the directory as a package\n')
    
    print(f"✓ Created {init_file}")

print("\n✓ All __init__.py files created successfully!")
print("\nNow you can run your application:")
print("  cd backend")
print("  python app.py")