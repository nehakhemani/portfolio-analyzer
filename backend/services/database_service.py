#!/usr/bin/env python3
"""
Multi-User Database Service
Handles user management, shared ticker data, and user-specific portfolios
"""

import sqlite3
import hashlib
import secrets
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd

class DatabaseService:
    """Multi-user database service with proper architecture"""
    
    def __init__(self, db_path: str = '/app/data/portfolio_multiuser.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database with multi-user schema"""
        # Ensure the data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Read and execute schema
        schema_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'schema_multiuser.sql')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if os.path.exists(schema_path):
                with open(schema_path, 'r') as f:
                    schema_sql = f.read()
                cursor.executescript(schema_sql)
            else:
                # Fallback: create basic schema inline
                self._create_basic_schema(cursor)
            
            conn.commit()
            print(f"✅ Multi-user database initialized at {self.db_path}")
            
        except Exception as e:
            print(f"❌ Database initialization error: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def _create_basic_schema(self, cursor):
        """Fallback schema creation if file not found"""
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            );
            
            CREATE TABLE IF NOT EXISTS tickers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker_symbol VARCHAR(20) UNIQUE NOT NULL,
                current_price DECIMAL(15,4),
                price_updated_at TIMESTAMP,
                price_source VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS user_portfolios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ticker_id INTEGER NOT NULL,
                quantity DECIMAL(15,8) NOT NULL,
                average_cost DECIMAL(15,4) NOT NULL,
                total_cost DECIMAL(15,2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (ticker_id) REFERENCES tickers(id),
                UNIQUE(user_id, ticker_id)
            );
        """)
    
    # =========================================================================
    # USER MANAGEMENT
    # =========================================================================
    
    def create_user(self, username: str, email: str, password: str, 
                   first_name: str = None, last_name: str = None) -> Optional[int]:
        """Create a new user account"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            password_hash = self._hash_password(password)
            
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, first_name, last_name)
                VALUES (?, ?, ?, ?, ?)
            """, (username, email, password_hash, first_name, last_name))
            
            user_id = cursor.lastrowid
            conn.commit()
            
            print(f"✅ User created: {username} (ID: {user_id})")
            return user_id
            
        except sqlite3.IntegrityError as e:
            if 'username' in str(e):
                print(f"❌ Username '{username}' already exists")
            elif 'email' in str(e):
                print(f"❌ Email '{email}' already exists")
            return None
        except Exception as e:
            print(f"❌ Error creating user: {e}")
            return None
        finally:
            conn.close()
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate user login"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, username, email, password_hash, first_name, last_name, is_active
                FROM users WHERE username = ? AND is_active = 1
            """, (username,))
            
            user = cursor.fetchone()
            if not user:
                return None
            
            user_id, username, email, stored_hash, first_name, last_name, is_active = user
            
            if self._verify_password(password, stored_hash):
                # Update last login
                cursor.execute("""
                    UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?
                """, (user_id,))
                conn.commit()
                
                return {
                    'id': user_id,
                    'username': username,
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'full_name': f"{first_name} {last_name}".strip() or username
                }
            
            return None
            
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            return None
        finally:
            conn.close()
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user information by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, username, email, first_name, last_name, created_at, last_login
                FROM users WHERE id = ? AND is_active = 1
            """, (user_id,))
            
            user = cursor.fetchone()
            if user:
                return {
                    'id': user[0],
                    'username': user[1],
                    'email': user[2],
                    'first_name': user[3],
                    'last_name': user[4],
                    'created_at': user[5],
                    'last_login': user[6]
                }
            return None
            
        except Exception as e:
            print(f"❌ Error getting user: {e}")
            return None
        finally:
            conn.close()
    
    # =========================================================================
    # TICKER MANAGEMENT (SHARED DATA)
    # =========================================================================
    
    def get_or_create_ticker(self, ticker_symbol: str, exchange: str = None, 
                           company_name: str = None) -> int:
        """Get existing ticker ID or create new ticker entry"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Check if ticker exists
            cursor.execute("SELECT id FROM tickers WHERE ticker_symbol = ?", (ticker_symbol.upper(),))
            result = cursor.fetchone()
            
            if result:
                return result[0]
            
            # Create new ticker
            cursor.execute("""
                INSERT INTO tickers (ticker_symbol, exchange, company_name)
                VALUES (?, ?, ?)
            """, (ticker_symbol.upper(), exchange, company_name))
            
            ticker_id = cursor.lastrowid
            conn.commit()
            
            return ticker_id
            
        except Exception as e:
            print(f"❌ Error with ticker {ticker_symbol}: {e}")
            return None
        finally:
            conn.close()
    
    def update_ticker_price(self, ticker_symbol: str, price: float, 
                           source: str = 'batch_job') -> bool:
        """Update ticker price (called by batch job)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE tickers 
                SET current_price = ?, price_updated_at = CURRENT_TIMESTAMP, 
                    price_source = ?, fetch_success = 1, last_fetch_attempt = CURRENT_TIMESTAMP
                WHERE ticker_symbol = ?
            """, (price, source, ticker_symbol.upper()))
            
            if cursor.rowcount > 0:
                conn.commit()
                return True
            
            # Ticker doesn't exist - create it
            ticker_id = self.get_or_create_ticker(ticker_symbol)
            if ticker_id:
                cursor.execute("""
                    UPDATE tickers 
                    SET current_price = ?, price_updated_at = CURRENT_TIMESTAMP, 
                        price_source = ?, fetch_success = 1, last_fetch_attempt = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (price, source, ticker_id))
                conn.commit()
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Error updating price for {ticker_symbol}: {e}")
            return False
        finally:
            conn.close()
    
    def get_all_unique_tickers(self) -> List[str]:
        """Get all unique ticker symbols for batch price fetching"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT DISTINCT t.ticker_symbol
                FROM tickers t
                WHERE t.ticker_symbol IS NOT NULL
                ORDER BY t.ticker_symbol
            """)
            
            return [row[0] for row in cursor.fetchall()]
            
        except Exception as e:
            print(f"❌ Error getting tickers: {e}")
            return []
        finally:
            conn.close()
    
    # =========================================================================
    # USER PORTFOLIO MANAGEMENT
    # =========================================================================
    
    def add_portfolio_position(self, user_id: int, ticker_symbol: str, 
                             quantity: float, average_cost: float, 
                             exchange: str = None) -> bool:
        """Add or update portfolio position for user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get or create ticker
            ticker_id = self.get_or_create_ticker(ticker_symbol, exchange)
            if not ticker_id:
                return False
            
            total_cost = quantity * average_cost
            
            # Insert or update portfolio position
            cursor.execute("""
                INSERT OR REPLACE INTO user_portfolios 
                (user_id, ticker_id, quantity, average_cost, total_cost, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, ticker_id, quantity, average_cost, total_cost))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"❌ Error adding position {ticker_symbol} for user {user_id}: {e}")
            return False
        finally:
            conn.close()
    
    def get_user_portfolio(self, user_id: int) -> List[Dict]:
        """Get user's complete portfolio with current prices"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    t.ticker_symbol,
                    t.company_name,
                    t.exchange,
                    t.current_price,
                    t.price_updated_at,
                    t.price_source,
                    up.quantity,
                    up.average_cost,
                    up.total_cost,
                    CASE 
                        WHEN t.current_price IS NOT NULL 
                        THEN up.quantity * t.current_price 
                        ELSE NULL 
                    END as current_value,
                    CASE 
                        WHEN t.current_price IS NOT NULL 
                        THEN ((up.quantity * t.current_price) - up.total_cost)
                        ELSE NULL 
                    END as unrealized_pnl,
                    CASE 
                        WHEN t.current_price IS NOT NULL AND up.total_cost > 0
                        THEN (((up.quantity * t.current_price) - up.total_cost) / up.total_cost * 100)
                        ELSE NULL 
                    END as return_percentage
                FROM user_portfolios up
                JOIN tickers t ON up.ticker_id = t.id
                WHERE up.user_id = ? AND up.is_active = 1 AND up.quantity > 0
                ORDER BY up.total_cost DESC
            """, (user_id,))
            
            holdings = []
            for row in cursor.fetchall():
                holding = {
                    'ticker': row[0],
                    'company_name': row[1],
                    'exchange': row[2],
                    'current_price': row[3],
                    'price_updated_at': row[4],
                    'price_source': row[5],
                    'quantity': row[6],
                    'average_cost': row[7],
                    'total_cost': row[8],
                    'current_value': row[9],
                    'unrealized_pnl': row[10],
                    'return_percentage': row[11],
                    'has_price': row[3] is not None
                }
                holdings.append(holding)
            
            return holdings
            
        except Exception as e:
            print(f"❌ Error getting portfolio for user {user_id}: {e}")
            return []
        finally:
            conn.close()
    
    def clear_user_portfolio(self, user_id: int) -> bool:
        """Clear user's portfolio"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE user_portfolios 
                SET is_active = 0, updated_at = CURRENT_TIMESTAMP 
                WHERE user_id = ?
            """, (user_id,))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"❌ Error clearing portfolio for user {user_id}: {e}")
            return False
        finally:
            conn.close()
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def _hash_password(self, password: str) -> str:
        """Hash password with salt"""
        salt = secrets.token_hex(32)
        return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex() + ':' + salt
    
    def _verify_password(self, password: str, hash_with_salt: str) -> bool:
        """Verify password against hash"""
        try:
            password_hash, salt = hash_with_salt.split(':')
            return password_hash == hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()
        except:
            return False
    
    def get_database_stats(self) -> Dict:
        """Get database statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            stats = {}
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
            stats['active_users'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM tickers")
            stats['total_tickers'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM tickers WHERE current_price IS NOT NULL")
            stats['tickers_with_prices'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM user_portfolios WHERE is_active = 1")
            stats['total_positions'] = cursor.fetchone()[0]
            
            return stats
            
        except Exception as e:
            print(f"❌ Error getting database stats: {e}")
            return {}
        finally:
            conn.close()