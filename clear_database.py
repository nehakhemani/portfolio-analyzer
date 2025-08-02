#!/usr/bin/env python3
"""
Clear Portfolio Database
Removes all holdings data for fresh start
"""

import sqlite3
import os
import sys

def clear_database():
    """Clear all holdings from the portfolio database"""
    
    # Database path
    db_path = os.path.join('backend', 'data', 'portfolio.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at: {db_path}")
        return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check current data
        cursor.execute("SELECT COUNT(*) FROM holdings")
        count_before = cursor.fetchone()[0]
        print(f"Holdings before clearing: {count_before}")
        
        # Clear all holdings
        cursor.execute("DELETE FROM holdings")
        
        # Check after clearing
        cursor.execute("SELECT COUNT(*) FROM holdings")
        count_after = cursor.fetchone()[0]
        
        # Commit changes
        conn.commit()
        conn.close()
        
        print(f"Holdings after clearing: {count_after}")
        print("[OK] Database cleared successfully!")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Error clearing database: {e}")
        return False

def reset_database():
    """Reset database with fresh tables"""
    
    db_path = os.path.join('backend', 'data', 'portfolio.db')
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Drop existing table
        cursor.execute("DROP TABLE IF EXISTS holdings")
        
        # Recreate table
        cursor.execute('''
            CREATE TABLE holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                exchange TEXT,
                currency TEXT DEFAULT 'USD',
                start_value REAL NOT NULL,
                end_value REAL NOT NULL,
                start_price REAL DEFAULT 0,
                end_price REAL DEFAULT 0,
                dividends REAL DEFAULT 0,
                fees REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        
        print("[OK] Database reset with fresh table structure!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error resetting database: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("PORTFOLIO DATABASE CLEANER")
    print("=" * 50)
    
    if len(sys.argv) > 1 and sys.argv[1] == '--reset':
        print("Resetting database with fresh table structure...")
        reset_database()
    else:
        print("Clearing all holdings data...")
        clear_database()
    
    print("\nDatabase is now empty and ready for fresh data!")
    print("=" * 50)