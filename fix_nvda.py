#!/usr/bin/env python3
"""
Fix NVDA initial investment value
"""

import sqlite3
import os

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
        print("Current NVDA data:")
        print(f"  Ticker: {nvda_data[1]}")
        print(f"  Start Value: ${nvda_data[4]}")
        print(f"  End Value: ${nvda_data[5]}")
        print(f"  Start Price: ${nvda_data[6]}")
        print(f"  End Price: ${nvda_data[7]}")
        print()
        
        print("What was your actual initial investment in NVDA?")
        print("(Enter the dollar amount you originally invested, e.g., 1500)")
        
        try:
            initial_investment = float(input("Initial investment amount: $"))
            
            # Update the database
            cursor.execute("""
                UPDATE holdings 
                SET start_value = ? 
                WHERE ticker = 'NVDA'
            """, (initial_investment,))
            
            conn.commit()
            print(f"\nNVDA initial investment updated to ${initial_investment:.2f}")
            
            # Show updated data
            cursor.execute("SELECT * FROM holdings WHERE ticker = 'NVDA'")
            updated_data = cursor.fetchone()
            print(f"Updated NVDA: ${updated_data[4]:.2f} -> ${updated_data[5]:.2f}")
            
            # Calculate new return for NVDA
            nvda_return = ((updated_data[5] - updated_data[4]) / updated_data[4] * 100) if updated_data[4] > 0 else 0
            print(f"NVDA return: {nvda_return:.2f}%")
            
        except ValueError:
            print("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
    else:
        print("NVDA not found in database")
    
    conn.close()

if __name__ == "__main__":
    fix_nvda_investment()