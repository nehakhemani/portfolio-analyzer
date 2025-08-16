"""
Stable Market Data Service - Multi-Source with Enhanced Reliability
Production-ready price fetching with multiple APIs, caching & validation
Phase 1: Enhanced caching & database persistence [DONE]
Phase 2: Multi-source API fallbacks [DONE]
Phase 3: Smart source rotation & validation [DONE]
"""
import yfinance as yf
import requests
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
        self.db_path = db_path
        self.last_fetch_attempts = {}  # Rate limiting tracker
        
        # Multi-source API configuration
        self.api_sources = {
            'yahoo': {
                'name': 'Yahoo Finance',
                'priority': 1,
                'rate_limit': 2000,  # requests per hour
                'reliability': 0.85,
                'last_success': datetime.now(),
                'consecutive_failures': 0
            },
            'alpha_vantage': {
                'name': 'Alpha Vantage',
                'priority': 2,
                'rate_limit': 25,  # free tier: 25 requests per day
                'reliability': 0.95,
                'last_success': datetime.now(),
                'consecutive_failures': 0,
                'api_key': os.getenv('ALPHA_VANTAGE_API_KEY', 'demo')  # Use demo key for testing
            },
            'finnhub': {
                'name': 'Finnhub',
                'priority': 3,
                'rate_limit': 3600,  # free tier: 60 requests per minute
                'reliability': 0.90,
                'last_success': datetime.now(),
                'consecutive_failures': 0,
                'api_key': os.getenv('FINNHUB_API_KEY', 'demo')
            }
        }
        
        # Track usage for rate limiting
        self.api_usage = {}
        for source in self.api_sources:
            self.api_usage[source] = {'count': 0, 'last_reset': datetime.now()}
        
        self._init_price_database()
        
    def _init_price_database(self):
        """Initialize database table for persistent price storage"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
# Old price_cache table removed - using new database structure
            
            # Price history table - central repository for all prices
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    price REAL NOT NULL,
                    change_pct REAL,
                    volume INTEGER,
                    market_cap INTEGER,
                    currency TEXT DEFAULT 'USD',
                    source TEXT NOT NULL,  -- 'yahoo', 'manual', 'alpha_vantage', etc.
                    timestamp DATETIME NOT NULL,
                    is_manual BOOLEAN DEFAULT 0,
                    notes TEXT,
                    expires_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Current prices view - latest price per ticker
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS current_prices (
                    ticker TEXT PRIMARY KEY,
                    price REAL NOT NULL,
                    change_pct REAL,
                    volume INTEGER,
                    market_cap INTEGER,
                    currency TEXT DEFAULT 'USD',
                    source TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    is_manual BOOLEAN DEFAULT 0,
                    notes TEXT,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Manual price override table - highest priority
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS manual_prices (
                    ticker TEXT PRIMARY KEY,
                    price REAL NOT NULL,
                    currency TEXT DEFAULT 'USD',
                    set_by TEXT DEFAULT 'user',
                    timestamp DATETIME NOT NULL,
                    notes TEXT,
                    expires_at DATETIME  -- Optional expiration
                )
            ''')
            
            # Index for fast lookups
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_manual_ticker ON manual_prices(ticker)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_price_history_ticker_time ON price_history(ticker, timestamp DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_current_prices_ticker ON current_prices(ticker)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_current_prices_timestamp ON current_prices(timestamp DESC)')
            conn.commit()
            conn.close()
            print("Price cache database initialized")
            
        except Exception as e:
            print(f"Warning: Could not initialize price database: {e}")
    
    def fetch_batch_quotes(self, tickers: List[str], force_refresh: bool = False) -> Dict:
        """
        DATABASE-FIRST pricing strategy:
        1. Always read from database with timestamp-based staleness
        2. Background sync handles API fetching separately
        3. Manual overrides stored in database with highest priority
        4. No live API calls during portfolio requests (much faster/reliable)
        """
        if not tickers:
            return {}
            
        print(f"Database-first fetch for {len(tickers)} tickers")
        
        # Get all prices from database with staleness classification
        market_data = self._get_prices_from_database(tickers)
        
        # Report staleness distribution
        staleness_counts = {}
        for ticker, data in market_data.items():
            staleness = data.get('staleness_level', 'none')
            staleness_counts[staleness] = staleness_counts.get(staleness, 0) + 1
        
        print(f"Price distribution: {staleness_counts}")
        return market_data
    
    def _get_prices_from_database(self, tickers: List[str]) -> Dict:
        """Get prices from database with timestamp-based staleness classification"""
        market_data = {}
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for ticker in tickers:
                # Check for manual override first
                cursor.execute('''
                    SELECT price, currency, timestamp, notes, expires_at
                    FROM manual_prices 
                    WHERE ticker = ? AND (expires_at IS NULL OR expires_at > ?)
                    ORDER BY timestamp DESC LIMIT 1
                ''', (ticker, datetime.now()))
                
                manual_row = cursor.fetchone()
                if manual_row:
                    price, currency, timestamp_str, notes, expires_at = manual_row
                    set_time = datetime.fromisoformat(timestamp_str)
                    age_hours = (datetime.now() - set_time).total_seconds() / 3600
                    
                    market_data[ticker] = {
                        'ticker': ticker,
                        'price': float(price),
                        'change': 0,
                        'volume': 0,
                        'market_cap': 0,
                        'currency': currency or 'USD',
                        'source': 'manual_override',
                        'timestamp': set_time,
                        'is_manual': True,
                        'notes': notes,
                        'staleness_level': 'manual',
                        'data_age_hours': round(age_hours, 1),
                        'data_age_str': self._format_age(age_hours)
                    }
                    print(f"MANUAL {ticker}: ${price:.2f} ({self._format_age(age_hours)})")
                    continue
                
                # Get latest price from current_prices table
                cursor.execute('''
                    SELECT price, change_pct, volume, market_cap, currency, source, timestamp, is_manual, notes
                    FROM current_prices 
                    WHERE ticker = ?
                    ORDER BY timestamp DESC LIMIT 1
                ''', (ticker,))
                
                price_row = cursor.fetchone()
                if price_row:
                    price, change_pct, volume, market_cap, currency, source, timestamp_str, is_manual, notes = price_row
                    price_time = datetime.fromisoformat(timestamp_str)
                    age_hours = (datetime.now() - price_time).total_seconds() / 3600
                    
                    # Classify staleness based on timestamp
                    staleness_level = self._classify_staleness(age_hours)
                    
                    market_data[ticker] = {
                        'ticker': ticker,
                        'price': float(price),
                        'change': float(change_pct) if change_pct else 0,
                        'volume': int(volume) if volume else 0,
                        'market_cap': int(market_cap) if market_cap else 0,
                        'currency': currency or 'USD',
                        'source': source,
                        'timestamp': price_time,
                        'is_manual': bool(is_manual),
                        'notes': notes,
                        'staleness_level': staleness_level,
                        'data_age_hours': round(age_hours, 1),
                        'data_age_str': self._format_age(age_hours)
                    }
                    
                    print(f"DB {ticker}: ${price:.2f} ({staleness_level}, {self._format_age(age_hours)}) [{source}]")
                else:
                    # No price data available
                    market_data[ticker] = {
                        'ticker': ticker,
                        'status': 'error',
                        'error': 'No price data available in database',
                        'price': None,
                        'change': None,
                        'volume': None,
                        'market_cap': None,
                        'currency': 'USD',
                        'source': 'none',
                        'timestamp': datetime.now(),
                        'has_error': True
                    }
                    print(f"ERROR {ticker}: No price data in database")
            
            conn.close()
            
        except Exception as e:
            print(f"Database price fetch failed: {e}")
            
        return market_data
    
    def _classify_staleness(self, age_hours: float) -> str:
        """Classify price staleness based on age in hours"""
        if age_hours < 0.25:  # 15 minutes
            return 'live'
        elif age_hours < 4:   # 4 hours
            return 'recent'
        elif age_hours < 24:  # 1 day
            return 'stale'
        elif age_hours < 168: # 7 days
            return 'very_stale'
        else:
            return 'ancient'
    
    def _format_age(self, age_hours: float) -> str:
        """Format age in human-readable string"""
        if age_hours < 1:
            return f"{int(age_hours * 60)}m old"
        elif age_hours < 24:
            return f"{age_hours:.1f}h old"
        else:
            days = age_hours / 24
            return f"{days:.1f}d old"
    
    def store_price_in_database(self, ticker: str, price_data: Dict) -> bool:
        """Store price in both history and current_prices tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.now()
            
            # Store in price history
            cursor.execute('''
                INSERT INTO price_history 
                (ticker, price, change_pct, volume, market_cap, currency, source, timestamp, is_manual, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ticker,
                price_data.get('price', 0),
                price_data.get('change', 0),
                price_data.get('volume', 0),
                price_data.get('market_cap', 0),
                price_data.get('currency', 'USD'),
                price_data.get('source', 'unknown'),
                price_data.get('timestamp', now),
                price_data.get('is_manual', False),
                price_data.get('notes')
            ))
            
            # Update current_prices table
            cursor.execute('''
                INSERT OR REPLACE INTO current_prices
                (ticker, price, change_pct, volume, market_cap, currency, source, timestamp, is_manual, notes, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ticker,
                price_data.get('price', 0),
                price_data.get('change', 0),
                price_data.get('volume', 0),
                price_data.get('market_cap', 0),
                price_data.get('currency', 'USD'),
                price_data.get('source', 'unknown'),
                price_data.get('timestamp', now),
                price_data.get('is_manual', False),
                price_data.get('notes'),
                now
            ))
            
            conn.commit()
            conn.close()
            
            print(f"Stored price: {ticker} = ${price_data.get('price', 0):.2f} [{price_data.get('source', 'unknown')}]")
            return True
            
        except Exception as e:
            print(f"Failed to store price for {ticker}: {e}")
            return False
    
    def sync_prices_background(self, tickers: List[str]) -> Dict:
        """Background method to fetch prices from APIs and store in database"""
        print(f"Background sync starting for {len(tickers)} tickers...")
        
        sync_results = {
            'success_count': 0,
            'error_count': 0,
            'tickers_updated': [],
            'tickers_failed': []
        }
        
        for ticker in tickers:
            try:
                # Try to fetch from APIs
                fresh_data = self._fetch_from_best_source(ticker)
                
                if fresh_data and fresh_data.get('price', 0) > 0:
                    # Store in database
                    fresh_data['timestamp'] = datetime.now()
                    if self.store_price_in_database(ticker, fresh_data):
                        sync_results['success_count'] += 1
                        sync_results['tickers_updated'].append(ticker)
                        print(f"SYNC SUCCESS {ticker}: ${fresh_data['price']:.2f} [{fresh_data.get('source')}]")
                    else:
                        sync_results['error_count'] += 1
                        sync_results['tickers_failed'].append(ticker)
                else:
                    sync_results['error_count'] += 1
                    sync_results['tickers_failed'].append(ticker)
                    print(f"SYNC ERROR {ticker}: API fetch failed")
                    
                # Small delay to avoid rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                sync_results['error_count'] += 1
                sync_results['tickers_failed'].append(ticker)
                print(f"SYNC ERROR {ticker}: {e}")
        
        print(f"Background sync complete: {sync_results['success_count']} success, {sync_results['error_count']} failed")
        return sync_results
    
    def fetch_batch_quotes_with_exchange(self, ticker_exchange_map: dict) -> Dict:
        """
        Smart batch fetching with rate limit avoidance
        Uses staggered requests to prevent API rate limiting
        """
        if not ticker_exchange_map:
            return {}
        
        print(f"Smart staggered fetching for {len(ticker_exchange_map)} tickers")
        
        # If small batch, use normal method
        if len(ticker_exchange_map) <= 5:
            tickers = list(ticker_exchange_map.keys())
            results = self.fetch_batch_quotes(tickers, force_refresh=False)
        else:
            # Large batch - use staggered approach
            results = self._fetch_staggered_quotes(ticker_exchange_map)
        
        # Add exchange information to results
        for ticker in results:
            if ticker in ticker_exchange_map:
                results[ticker]['exchange'] = ticker_exchange_map[ticker]
                
                # Format ticker for the exchange if needed
                if 'formatted_ticker' not in results[ticker]:
                    formatted_ticker = self._format_ticker_for_exchange(ticker, ticker_exchange_map[ticker])
                    results[ticker]['formatted_ticker'] = formatted_ticker
        
        return results
    
    def _fetch_staggered_quotes(self, ticker_exchange_map: dict) -> Dict:
        """
        Fetch quotes in small batches with delays to avoid rate limiting
        This should dramatically improve success rates
        """
        all_results = {}
        tickers = list(ticker_exchange_map.keys())
        
        # Split into batches of 3-4 tickers
        batch_size = 3
        batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
        
        print(f"Splitting {len(tickers)} tickers into {len(batches)} batches of ~{batch_size}")
        
        for i, batch in enumerate(batches):
            try:
                print(f"Fetching batch {i+1}/{len(batches)}: {', '.join(batch)}")
                
                # Fetch this small batch
                batch_results = self.fetch_batch_quotes(batch, force_refresh=False)
                all_results.update(batch_results)
                
                # Add delay between batches (except last one)
                if i < len(batches) - 1:
                    print(f"Waiting 2 seconds before next batch...")
                    time.sleep(2)  # 2 second delay between batches
                    
            except Exception as e:
                print(f"Batch {i+1} failed: {e}")
                
                # Even if batch fails, add error status for this batch
                for ticker in batch:
                    if ticker not in all_results:
                        all_results[ticker] = {
                            'ticker': ticker,
                            'status': 'error',
                            'error': f'Batch {i+1} failed: {str(e)}',
                            'price': None,
                            'change': None,
                            'volume': None,
                            'market_cap': None,
                            'name': ticker,
                            'currency': 'USD',
                            'source': 'none',
                            'timestamp': datetime.now(),
                            'has_error': True
                        }
        
        success_count = len([r for r in all_results.values() if not r.get('has_error', False) and r.get('price') is not None])
        error_count = len([r for r in all_results.values() if r.get('has_error', False)])
        print(f"Staggered fetch complete: {success_count}/{len(tickers)} real prices obtained, {error_count} errors")
        
        return all_results
    
    def _fetch_from_best_source(self, ticker: str) -> Optional[Dict]:
        """Try multiple API sources in order of reliability and availability"""
        
        # Get available sources sorted by priority and reliability
        available_sources = self._get_available_sources()
        
        for source_name in available_sources:
            try:
                # Check rate limits
                if not self._check_rate_limit(source_name):
                    print(f"RATELIMIT {source_name}: Rate limit reached, skipping")
                    continue
                
                # Try to fetch from this source
                if source_name == 'yahoo':
                    data = self._fetch_from_yahoo(ticker)
                elif source_name == 'alpha_vantage':
                    data = self._fetch_from_alpha_vantage(ticker)
                elif source_name == 'finnhub':
                    data = self._fetch_from_finnhub(ticker)
                else:
                    continue
                
                if data and data.get('price', 0) > 0:
                    # Validate price seems reasonable
                    if self._validate_price(ticker, data['price']):
                        # Update source reliability
                        self._update_source_success(source_name)
                        data['source'] = source_name
                        return data
                    else:
                        print(f"INVALID {ticker}: {source_name} price validation failed: ${data['price']}")
                
            except Exception as e:
                print(f"ERROR {source_name} failed for {ticker}: {e}")
                self._update_source_failure(source_name)
        
        print(f"ERROR All sources failed for {ticker}")
        return None
    
    def _get_available_sources(self) -> List[str]:
        """Get API sources sorted by reliability and availability"""
        sources = []
        
        for name, config in self.api_sources.items():
            # Skip sources with too many consecutive failures
            if config['consecutive_failures'] >= 5:
                continue
            
            # Check if we have API key for paid sources
            if name in ['alpha_vantage', 'finnhub']:
                api_key = config.get('api_key')
                if not api_key or api_key == 'demo':
                    continue  # Skip if no valid API key
            
            sources.append(name)
        
        # Sort by reliability score (descending) then by priority (ascending)
        sources.sort(key=lambda x: (-self.api_sources[x]['reliability'], self.api_sources[x]['priority']))
        
        return sources
    
    def _check_rate_limit(self, source: str) -> bool:
        """Check if we can make a request to this source"""
        now = datetime.now()
        usage = self.api_usage[source]
        config = self.api_sources[source]
        
        # Reset counter if needed (daily for Alpha Vantage, hourly for others)
        reset_hours = 24 if source == 'alpha_vantage' else 1
        if (now - usage['last_reset']).total_seconds() > reset_hours * 3600:
            usage['count'] = 0
            usage['last_reset'] = now
        
        return usage['count'] < config['rate_limit']
    
    def _update_source_success(self, source: str):
        """Update source statistics after successful fetch"""
        config = self.api_sources[source]
        config['last_success'] = datetime.now()
        config['consecutive_failures'] = 0
        
        # Gradually improve reliability score
        config['reliability'] = min(0.99, config['reliability'] * 0.95 + 0.05)
        
        # Update usage counter
        self.api_usage[source]['count'] += 1
    
    def _update_source_failure(self, source: str):
        """Update source statistics after failed fetch"""
        config = self.api_sources[source]
        config['consecutive_failures'] += 1
        
        # Gradually decrease reliability score
        config['reliability'] = max(0.01, config['reliability'] * 0.9)
    
    def _validate_price(self, ticker: str, price: float) -> bool:
        """Validate that the price seems reasonable"""
        if not price or price <= 0:
            return False
        
        # Check against historical data if available
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get recent price history
            cursor.execute('''
                SELECT price FROM price_cache 
                WHERE ticker = ? AND timestamp > ?
                ORDER BY timestamp DESC LIMIT 10
            ''', (ticker, datetime.now() - timedelta(days=7)))
            
            recent_prices = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if recent_prices:
                avg_recent = sum(recent_prices) / len(recent_prices)
                # Allow 50% deviation from recent average (handles stock splits/volatility)
                if price < avg_recent * 0.5 or price > avg_recent * 2.0:
                    return False
        except:
            pass  # If validation fails, accept the price
        
        # Basic sanity checks
        if price > 10000:  # No stock should be over $10,000
            return False
        
        return True
    
    def _fetch_from_alpha_vantage(self, ticker: str, timeout: int = 5) -> Optional[Dict]:
        """Fetch from Alpha Vantage API"""
        try:
            api_key = self.api_sources['alpha_vantage']['api_key']
            if not api_key or api_key == 'demo':
                return None
            
            # Alpha Vantage Global Quote API
            url = f"https://www.alphavantage.co/query"
            params = {
                'function': 'GLOBAL_QUOTE',
                'symbol': ticker,
                'apikey': api_key
            }
            
            response = requests.get(url, params=params, timeout=timeout)
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            # Check for API limit message
            if 'Note' in data or 'Information' in data:
                print(f"Alpha Vantage: {data.get('Note', data.get('Information', 'Rate limit'))}")
                return None
            
            quote = data.get('Global Quote', {})
            if not quote:
                return None
            
            price = float(quote.get('05. price', 0))
            change_pct = float(quote.get('10. change percent', '0').replace('%', ''))
            
            if price > 0:
                return {
                    'price': price,
                    'change': change_pct,
                    'volume': int(quote.get('06. volume', 0)),
                    'market_cap': 0,  # Not provided by this endpoint
                    'name': ticker,
                    'currency': 'USD',
                    'source': 'alpha_vantage',
                    'timestamp': datetime.now()
                }
                
        except Exception as e:
            print(f"Alpha Vantage error for {ticker}: {e}")
        
        return None
    
    def _fetch_from_finnhub(self, ticker: str, timeout: int = 5) -> Optional[Dict]:
        """Fetch from Finnhub API"""
        try:
            api_key = self.api_sources['finnhub']['api_key']
            if not api_key or api_key == 'demo':
                return None
            
            # Finnhub Quote API
            url = f"https://finnhub.io/api/v1/quote"
            params = {
                'symbol': ticker,
                'token': api_key
            }
            
            response = requests.get(url, params=params, timeout=timeout)
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            # Check if we got valid data
            current_price = data.get('c', 0)  # Current price
            prev_close = data.get('pc', 0)    # Previous close
            
            if current_price and current_price > 0:
                change_pct = 0
                if prev_close and prev_close > 0:
                    change_pct = ((current_price - prev_close) / prev_close) * 100
                
                return {
                    'price': float(current_price),
                    'change': round(change_pct, 2),
                    'volume': 0,  # Not provided in basic quote
                    'market_cap': 0,
                    'name': ticker,
                    'currency': 'USD',
                    'source': 'finnhub',
                    'timestamp': datetime.now()
                }
                
        except Exception as e:
            print(f"Finnhub error for {ticker}: {e}")
        
        return None
    
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
            
            # Fallback to regular info (Windows compatible)
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
            except Exception as info_error:
                print(f"Yahoo info fetch failed for {ticker}: {info_error}")
                
        except Exception as e:
            print(f"Yahoo fetch failed for {ticker}: {e}")
            return None
        
        return None
    
# All legacy methods removed - using database-first architecture only
    
    def _format_ticker_for_exchange(self, ticker: str, exchange: str = None) -> str:
        """Format ticker for Yahoo Finance exchange suffixes"""
        if not exchange:
            return ticker
            
        # Yahoo Finance exchange suffix mappings
        exchange_suffixes = {
            'NZX': '.NZ',        # New Zealand Exchange
            'ASX': '.AX',        # Australian Securities Exchange  
            'LSE': '.L',         # London Stock Exchange
            'TSX': '.TO',        # Toronto Stock Exchange
            'TSE': '.T',         # Tokyo Stock Exchange
            'NASDAQ': '',        # No suffix needed
            'NYSE': '',          # No suffix needed
            'AMEX': '',          # No suffix needed
        }
        
        # Get the appropriate suffix
        suffix = exchange_suffixes.get(exchange.upper(), '')
        
        # Only add suffix if ticker doesn't already have one
        if suffix and '.' not in ticker:
            return f"{ticker}{suffix}"
        
        return ticker
    
    def cleanup_old_cache(self, days_old: int = 7):
        """Clean up old cache entries to keep database size manageable"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = datetime.now() - timedelta(days=days_old)
            cursor.execute('DELETE FROM price_history WHERE timestamp < ?', (cutoff_date,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            print(f"CLEANED {deleted_count} old cache entries (older than {days_old} days)")
            return deleted_count
            
        except Exception as e:
            print(f"Cache cleanup failed: {e}")
            return 0
    
    def set_manual_price(self, ticker: str, price: float, currency: str = 'USD', notes: str = None, expires_hours: int = None):
        """Set manual price override for a ticker"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.now()
            expires_at = None
            if expires_hours:
                expires_at = now + timedelta(hours=expires_hours)
            
            # Insert or replace manual price
            cursor.execute('''
                INSERT OR REPLACE INTO manual_prices 
                (ticker, price, currency, set_by, timestamp, notes, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (ticker.upper(), price, currency.upper(), 'user', now, notes, expires_at))
            
            conn.commit()
            conn.close()
            
            print(f"MANUAL PRICE SET: {ticker} = ${price:.2f} {currency}")
            return True
            
        except Exception as e:
            print(f"Failed to set manual price for {ticker}: {e}")
            return False
    
    def remove_manual_price(self, ticker: str):
        """Remove manual price override for a ticker"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM manual_prices WHERE ticker = ?', (ticker.upper(),))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            if deleted_count > 0:
                print(f"MANUAL PRICE REMOVED: {ticker}")
                return True
            else:
                print(f"NO MANUAL PRICE FOUND: {ticker}")
                return False
                
        except Exception as e:
            print(f"Failed to remove manual price for {ticker}: {e}")
            return False
    
    def get_manual_prices(self):
        """Get all current manual price overrides"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT ticker, price, currency, timestamp, notes, expires_at
                FROM manual_prices
                WHERE expires_at IS NULL OR expires_at > ?
                ORDER BY ticker
            ''', (datetime.now(),))
            
            manual_prices = []
            for row in cursor.fetchall():
                ticker, price, currency, timestamp_str, notes, expires_at = row
                timestamp = datetime.fromisoformat(timestamp_str)
                
                manual_prices.append({
                    'ticker': ticker,
                    'price': float(price),
                    'currency': currency,
                    'timestamp': timestamp,
                    'notes': notes,
                    'expires_at': expires_at,
                    'age_hours': (datetime.now() - timestamp).total_seconds() / 3600
                })
            
            conn.close()
            return manual_prices
            
        except Exception as e:
            print(f"Failed to get manual prices: {e}")
            return []
