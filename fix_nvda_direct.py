#!/usr/bin/env python3
"""
Fix NVDA initial investment value - Direct version
Change the INITIAL_INVESTMENT value below to your actual NVDA investment
"""

import sqlite3
import os

# *** CHANGE THIS TO YOUR ACTUAL NVDA INITIAL INVESTMENT ***
INITIAL_INVESTMENT = 1128.05  # Your actual NVDA initial investment

def fix_nvda_investment():
    """Fix NVDA's initial investment value"""
    
    # Connect to database
    db_path = os.path.join('backend', 'data', 'portfolio.db')
    if not os.path.exists(db_path):
        db_path = os.path.join('data', 'portfolio.db')
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check current NVDA data
    cursor.execute("SELECT * FROM holdings WHERE ticker = 'NVDA'")
    nvda_data = cursor.fetchone()
    
    if nvda_data:
        print("BEFORE:")
        print(f"  NVDA Start Value: ${nvda_data[4]}")
        print(f"  NVDA End Value: ${nvda_data[5]}")
        print()
        
        # Update the database
        cursor.execute("""
            UPDATE holdings 
            SET start_value = ? 
            WHERE ticker = 'NVDA'
        """, (INITIAL_INVESTMENT,))
        
        conn.commit()
        
        # Show updated data
        cursor.execute("SELECT * FROM holdings WHERE ticker = 'NVDA'")
        updated_data = cursor.fetchone()
        
        print("AFTER:")
        print(f"  NVDA Start Value: ${updated_data[4]:.2f}")
        print(f"  NVDA End Value: ${updated_data[5]:.2f}")
        
        # Calculate new return for NVDA
        nvda_return = ((updated_data[5] - updated_data[4]) / updated_data[4] * 100) if updated_data[4] > 0 else 0
        print(f"  NVDA return: {nvda_return:.2f}%")
        print()
        print("NVDA data has been fixed!")
        print("Refresh your browser to see the updated portfolio return.")
        
    else:
        print("NVDA not found in database")
    
    conn.close()

if __name__ == "__main__":
    print(f"Fixing NVDA initial investment to ${INITIAL_INVESTMENT}")
    print("If this is wrong, edit fix_nvda_direct.py and change INITIAL_INVESTMENT")
    print()
    fix_nvda_investment()