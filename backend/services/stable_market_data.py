"""
Stable Market Data Service - Phase 1: Enhanced Caching & Database Persistence
Production-ready price fetching with graceful degradation and reliability
"""
import yfinance as yf
from datetime import datetime, timedelta
import time
import logging
import sqlite3
import os
import json
import random
from typing import Dict, List, Optional, Tuple

class StableMarketDataService:
    def __init__(self, db_path='data/portfolio.db'):
        self.memory_cache = {}
        self.short_cache_duration = 300  # 5 minutes for active trading
        self.long_cache_duration = 14400  # 4 hours for stable fallback
        self.db_path = db_path
        self.last_fetch_attempts = {}
        self._init_price_database()
        
    def _init_price_database(self):
        """Initialize database table for persistent price storage"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS price_cache (
                    ticker TEXT PRIMARY KEY,
                    price REAL NOT NULL,
                    change_pct REAL,
                    volume INTEGER,
                    market_cap INTEGER,
                    currency TEXT DEFAULT 'USD',
                    source TEXT DEFAULT 'yahoo',
                    timestamp DATETIME NOT NULL,
                    last_updated DATETIME NOT NULL,
                    fetch_count INTEGER DEFAULT 1,
                    reliability_score REAL DEFAULT 1.0
                )
            ''')
            
            # Index for fast lookups
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_ticker_timestamp ON price_cache(ticker, timestamp)')
            conn.commit()
            conn.close()
            print("✓ Price cache database initialized")
            
        except Exception as e:
            print(f"Warning: Could not initialize price database: {e}")
    
    def fetch_batch_quotes(self, tickers: List[str], force_refresh: bool = False) -> Dict:
        """
        Fetch market data with multi-level fallback strategy:
        1. Memory cache (5 min)
        2. Yahoo Finance API 
        3. Database cache (4 hours)
        4. Simulated pricing (last resort)
        """
        if not tickers:
            return {}
            
        market_data = {}
        failed_tickers = []
        
        print(f"📊 Fetching prices for {len(tickers)} tickers (force_refresh={force_refresh})")
        
        for ticker in tickers:
            try:
                # Level 1: Memory cache check
                if not force_refresh and self._is_memory_cached(ticker):
                    market_data[ticker] = self.memory_cache[ticker]['data']
                    print(f"✓ {ticker}: Memory cache")
                    continue
                
                # Level 2: Try fresh API fetch
                fresh_data = self._fetch_from_yahoo(ticker)
                if fresh_data and fresh_data.get('price', 0) > 0:
                    # Success - store in both memory and database
                    self._store_in_memory(ticker, fresh_data)
                    self._store_in_database(ticker, fresh_data)
                    market_data[ticker] = fresh_data
                    print(f"✓ {ticker}: Fresh API data - ${fresh_data['price']:.2f}")
                    continue
                
                # Level 3: Database fallback
                db_data = self._get_from_database(ticker)
                if db_data:
                    # Add aging indicator
                    age_hours = (datetime.now() - db_data['timestamp']).total_seconds() / 3600
                    db_data['data_age_hours'] = round(age_hours, 1)
                    db_data['is_cached'] = True
                    
                    market_data[ticker] = db_data
                    print(f"⚠ {ticker}: Database cache ({age_hours:.1f}h old) - ${db_data['price']:.2f}")
                    continue
                
                # Level 4: Last resort - simulated pricing
                fallback_data = self._generate_fallback_price(ticker)
                market_data[ticker] = fallback_data
                failed_tickers.append(ticker)
                print(f"🔄 {ticker}: Fallback pricing - ${fallback_data['price']:.2f}")
                
            except Exception as e:
                print(f"❌ {ticker}: All methods failed - {e}")
                # Still provide fallback data
                fallback_data = self._generate_fallback_price(ticker)
                market_data[ticker] = fallback_data
                failed_tickers.append(ticker)
        
        # Report success rate
        success_rate = ((len(tickers) - len(failed_tickers)) / len(tickers)) * 100
        print(f"📈 Price fetch success: {success_rate:.1f}% ({len(tickers)-len(failed_tickers)}/{len(tickers)})")
        
        if failed_tickers:
            print(f"⚠ Failed tickers: {', '.join(failed_tickers)}")
        
        return market_data
    
    def _fetch_from_yahoo(self, ticker: str, timeout: int = 3) -> Optional[Dict]:
        """Fetch from Yahoo Finance with timeout and error handling"""
        try:
            # Rate limiting - don't hammer the API
            now = datetime.now()
            if ticker in self.last_fetch_attempts:
                time_since_last = (now - self.last_fetch_attempts[ticker]).total_seconds()
                if time_since_last < 1:  # Minimum 1 second between attempts
                    time.sleep(1 - time_since_last)
            
            self.last_fetch_attempts[ticker] = now
            
            # Format ticker for exchange
            formatted_ticker = self._format_ticker_for_exchange(ticker)
            stock = yf.Ticker(formatted_ticker)
            
            # Try fast_info first (faster method)
            try:
                fast_info = stock.fast_info
                current_price = fast_info.get('last_price', 0)
                if current_price and current_price > 0:
                    return {
                        'price': float(current_price),
                        'change': 0,  # Fast fetch - skip change calc
                        'volume': 0,
                        'market_cap': 0,
                        'name': ticker,
                        'currency': 'USD',
                        'source': 'yahoo_fast',
                        'timestamp': datetime.now()
                    }
            except:
                pass  # Fallback to regular info
            
            # Fallback to regular info with timeout
            import signal
            def timeout_handler(signum, frame):
                raise TimeoutError("Yahoo Finance timeout")
            
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout)
            
            try:
                info = stock.info
                current_price = info.get('regularMarketPrice', info.get('previousClose', 0))
                prev_close = info.get('previousClose', current_price)
                
                if current_price and current_price > 0:
                    # Calculate change percentage
                    change_pct = 0
                    if prev_close and prev_close != 0:
                        change_pct = ((current_price - prev_close) / prev_close) * 100
                    
                    return {
                        'price': float(current_price),
                        'change': round(change_pct, 2),
                        'volume': info.get('regularMarketVolume', 0),
                        'market_cap': info.get('marketCap', 0),
                        'name': info.get('longName', ticker),
                        'currency': info.get('currency', 'USD'),
                        'source': 'yahoo_full',
                        'timestamp': datetime.now()
                    }
            finally:
                signal.alarm(0)
                
        except Exception as e:
            print(f"Yahoo fetch failed for {ticker}: {e}")
            return None
        
        return None
    
    def _store_in_memory(self, ticker: str, data: Dict):
        """Store successful fetch in memory cache"""
        self.memory_cache[ticker] = {
            'data': data,
            'timestamp': datetime.now()
        }
    
    def _store_in_database(self, ticker: str, data: Dict):
        """Store successful fetch in database for long-term caching"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.now()
            
            # Upsert the price data
            cursor.execute('''
                INSERT OR REPLACE INTO price_cache 
                (ticker, price, change_pct, volume, market_cap, currency, source, timestamp, last_updated, fetch_count, reliability_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 
                        COALESCE((SELECT fetch_count FROM price_cache WHERE ticker = ?) + 1, 1),
                        COALESCE((SELECT reliability_score FROM price_cache WHERE ticker = ?) * 0.95 + 0.05, 1.0))
            ''', (
                ticker, data['price'], data.get('change', 0), data.get('volume', 0),
                data.get('market_cap', 0), data.get('currency', 'USD'), 
                data.get('source', 'yahoo'), now, now, ticker, ticker
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Database store failed for {ticker}: {e}")
    
    def _get_from_database(self, ticker: str) -> Optional[Dict]:
        """Retrieve cached price from database if recent enough"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get most recent entry within cache duration
            cursor.execute('''
                SELECT ticker, price, change_pct, volume, market_cap, currency, source, timestamp, reliability_score
                FROM price_cache 
                WHERE ticker = ? AND timestamp > ?
                ORDER BY timestamp DESC LIMIT 1
            ''', (ticker, datetime.now() - timedelta(seconds=self.long_cache_duration)))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'price': float(row[1]),
                    'change': float(row[2]) if row[2] else 0,
                    'volume': int(row[3]) if row[3] else 0,
                    'market_cap': int(row[4]) if row[4] else 0,
                    'name': ticker,
                    'currency': row[5] or 'USD',
                    'source': f"{row[6]}_cached",
                    'timestamp': datetime.fromisoformat(row[7]),
                    'reliability_score': float(row[8]) if row[8] else 1.0
                }
        except Exception as e:
            print(f"Database retrieve failed for {ticker}: {e}")
        
        return None
    
    def _generate_fallback_price(self, ticker: str) -> Dict:
        """Generate reasonable fallback price when all else fails"""
        # Try to get historical average from database
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get average price from last 30 days
            cursor.execute('''
                SELECT AVG(price) FROM price_cache 
                WHERE ticker = ? AND timestamp > ?
            ''', (ticker, datetime.now() - timedelta(days=30)))
            
            avg_price = cursor.fetchone()[0]
            conn.close()
            
            if avg_price and avg_price > 0:
                # Add small random variation
                variation = random.uniform(-0.01, 0.01)  # ±1%
                base_price = float(avg_price) * (1 + variation)
            else:
                # Use ticker-based estimation
                base_price = self._estimate_price_from_ticker(ticker)
                
        except:
            base_price = self._estimate_price_from_ticker(ticker)
        
        return {
            'price': round(max(base_price, 0.01), 2),
            'change': 0,
            'volume': 0,
            'market_cap': 0,
            'name': ticker,
            'currency': 'USD',
            'source': 'fallback',
            'timestamp': datetime.now(),
            'is_estimated': True,
            'reliability_score': 0.1
        }
    
    def _estimate_price_from_ticker(self, ticker: str) -> float:
        """Estimate reasonable price based on ticker characteristics"""
        # Simple heuristics for common price ranges
        if any(x in ticker.upper() for x in ['TSLA', 'NVDA', 'GOOGL']):
            return random.uniform(150, 400)
        elif any(x in ticker.upper() for x in ['AAPL', 'MSFT', 'AMZN']):
            return random.uniform(100, 200)
        elif ticker.upper().endswith('.NZ'):
            return random.uniform(1, 10)  # NZX typically lower prices
        elif ticker.upper().endswith('.AX'):
            return random.uniform(0.5, 20)  # ASX range
        else:
            return random.uniform(10, 100)  # Default range
    
    def _is_memory_cached(self, ticker: str) -> bool:
        """Check if ticker is in fresh memory cache"""
        if ticker not in self.memory_cache:
            return False
        
        age = (datetime.now() - self.memory_cache[ticker]['timestamp']).total_seconds()
        return age < self.short_cache_duration
    
    def _format_ticker_for_exchange(self, ticker: str, exchange: str = None) -> str:
        """Format ticker for Yahoo Finance exchange suffixes"""
        if '.' in ticker:  # Already has suffix
            return ticker
            
        # Common exchange mappings
        exchange_suffixes = {
            'NZX': '.NZ', 'ASX': '.AX', 'LSE': '.L', 
            'TSX': '.TO', 'TSE': '.T'
        }
        
        if exchange and exchange.upper() in exchange_suffixes:
            return f"{ticker}{exchange_suffixes[exchange.upper()]}"
        
        return ticker
    
    def get_cache_stats(self) -> Dict:
        """Get cache performance statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*), AVG(reliability_score), MAX(timestamp) FROM price_cache')
            stats = cursor.fetchone()
            
            cursor.execute('SELECT COUNT(*) FROM price_cache WHERE timestamp > ?', 
                         (datetime.now() - timedelta(hours=1),))
            recent_count = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total_cached_tickers': stats[0] or 0,
                'average_reliability': round(stats[1] or 0, 2),
                'last_update': stats[2] or 'Never',
                'recent_updates': recent_count or 0,
                'memory_cache_size': len(self.memory_cache)
            }
        except:
            return {'error': 'Could not retrieve cache stats'}
    
    def cleanup_old_cache(self, days_old: int = 7):
        """Clean up old cache entries to keep database size manageable"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = datetime.now() - timedelta(days=days_old)
            cursor.execute('DELETE FROM price_cache WHERE timestamp < ?', (cutoff_date,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            print(f"✓ Cleaned up {deleted_count} old cache entries (older than {days_old} days)")
            return deleted_count
            
        except Exception as e:
            print(f"Cache cleanup failed: {e}")
            return 0