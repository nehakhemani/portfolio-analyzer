"""
Stable Market Data Service - Multi-Source with Enhanced Reliability
Production-ready price fetching with multiple APIs, caching & validation
Phase 1: Enhanced caching & database persistence ✓
Phase 2: Multi-source API fallbacks ✓
Phase 3: Smart source rotation & validation ✓
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
        self.memory_cache = {}
        self.short_cache_duration = 300  # 5 minutes for active trading
        self.long_cache_duration = 14400  # 4 hours for stable fallback
        self.db_path = db_path
        self.last_fetch_attempts = {}
        
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
            print("Price cache database initialized")
            
        except Exception as e:
            print(f"Warning: Could not initialize price database: {e}")
    
    def fetch_batch_quotes(self, tickers: List[str], force_refresh: bool = False) -> Dict:
        """
        Fetch market data with multi-source fallback strategy:
        1. Memory cache (5 min)
        2. Multi-source API fetch (Yahoo → Alpha Vantage → Finnhub)
        3. Database cache (4 hours)
        4. Simulated pricing (last resort)
        """
        if not tickers:
            return {}
            
        market_data = {}
        failed_tickers = []
        
        print(f"Multi-source fetching for {len(tickers)} tickers (force_refresh={force_refresh})")
        
        for ticker in tickers:
            try:
                # Level 1: Memory cache check
                if not force_refresh and self._is_memory_cached(ticker):
                    market_data[ticker] = self.memory_cache[ticker]['data']
                    print(f"CACHE {ticker}: Memory cache")
                    continue
                
                # Level 2: Try multi-source API fetch
                fresh_data = self._fetch_from_best_source(ticker)
                if fresh_data and fresh_data.get('price', 0) > 0:
                    # Success - store in both memory and database
                    self._store_in_memory(ticker, fresh_data)
                    self._store_in_database(ticker, fresh_data)
                    market_data[ticker] = fresh_data
                    print(f"LIVE {ticker}: Fresh {fresh_data.get('source', 'API')} data - ${fresh_data['price']:.2f}")
                    continue
                
                # Level 3: Database fallback
                db_data = self._get_from_database(ticker)
                if db_data:
                    # Add aging indicator
                    age_hours = (datetime.now() - db_data['timestamp']).total_seconds() / 3600
                    db_data['data_age_hours'] = round(age_hours, 1)
                    db_data['is_cached'] = True
                    
                    market_data[ticker] = db_data
                    print(f"DB {ticker}: Database cache ({age_hours:.1f}h old) - ${db_data['price']:.2f}")
                    continue
                
                # Level 4: Last resort - simulated pricing
                fallback_data = self._generate_fallback_price(ticker)
                market_data[ticker] = fallback_data
                failed_tickers.append(ticker)
                print(f"SIM {ticker}: Fallback pricing - ${fallback_data['price']:.2f}")
                
            except Exception as e:
                print(f"ERROR {ticker}: All methods failed - {e}")
                # Still provide fallback data
                fallback_data = self._generate_fallback_price(ticker)
                market_data[ticker] = fallback_data
                failed_tickers.append(ticker)
        
        # Report success rate
        success_rate = ((len(tickers) - len(failed_tickers)) / len(tickers)) * 100
        print(f"SUCCESS: Price fetch success: {success_rate:.1f}% ({len(tickers)-len(failed_tickers)}/{len(tickers)})")
        
        if failed_tickers:
            print(f"FAILED tickers: {', '.join(failed_tickers)}")
        
        return market_data
    
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
                
                # Even if batch fails, add fallback prices for this batch
                for ticker in batch:
                    if ticker not in all_results:
                        all_results[ticker] = self._generate_fallback_price(ticker)
        
        success_count = len([r for r in all_results.values() if not r.get('is_estimated', False)])
        print(f"Staggered fetch complete: {success_count}/{len(tickers)} real prices obtained")
        
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
        """Use last known good price instead of random simulation"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get most recent actual price (within last 30 days)
            cursor.execute('''
                SELECT price, change_pct, volume, market_cap, currency, timestamp, reliability_score
                FROM price_cache 
                WHERE ticker = ? AND timestamp > ? AND price > 0
                ORDER BY timestamp DESC LIMIT 1
            ''', (ticker, datetime.now() - timedelta(days=30)))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                # Use last known good price
                price, change_pct, volume, market_cap, currency, timestamp_str, reliability = result
                last_update = datetime.fromisoformat(timestamp_str)
                age_hours = (datetime.now() - last_update).total_seconds() / 3600
                
                return {
                    'price': float(price),
                    'change': float(change_pct) if change_pct else 0,
                    'volume': int(volume) if volume else 0,
                    'market_cap': int(market_cap) if market_cap else 0,
                    'name': ticker,
                    'currency': currency or 'USD',
                    'source': 'cached_historical',
                    'timestamp': last_update,
                    'is_estimated': False,  # This is real historical data
                    'data_age_hours': round(age_hours, 1),
                    'reliability_score': float(reliability) if reliability else 0.8
                }
            else:
                # No historical data - try to get a reasonable estimate
                # But mark it clearly as estimated
                base_price = self._get_reasonable_estimate(ticker)
                
                return {
                    'price': base_price,
                    'change': 0,
                    'volume': 0,
                    'market_cap': 0,
                    'name': ticker,
                    'currency': 'USD',
                    'source': 'estimated',
                    'timestamp': datetime.now(),
                    'is_estimated': True,
                    'reliability_score': 0.1,
                    'note': 'No historical data available'
                }
                
        except Exception as e:
            print(f"Fallback price lookup failed for {ticker}: {e}")
            
            # Last resort - reasonable estimate
            base_price = self._get_reasonable_estimate(ticker)
            
            return {
                'price': base_price,
                'change': 0,
                'volume': 0,
                'market_cap': 0,
                'name': ticker,
                'currency': 'USD',
                'source': 'emergency_fallback',
                'timestamp': datetime.now(),
                'is_estimated': True,
                'reliability_score': 0.05
            }
    
    def _get_reasonable_estimate(self, ticker: str) -> float:
        """Get a reasonable price estimate based on ticker characteristics - MUCH BETTER than random"""
        # Known price ranges for common tickers (as of 2024)
        ticker_upper = ticker.upper()
        
        # High-value tech stocks
        if ticker_upper in ['TSLA', 'NVDA', 'GOOGL', 'GOOG']:
            return 200.0  # Reasonable for these high-value stocks
        elif ticker_upper in ['AAPL', 'MSFT', 'AMZN']:
            return 180.0  # Apple/Microsoft range
        elif ticker_upper in ['META', 'NFLX']:
            return 400.0  # Meta/Netflix range
        elif ticker_upper in ['SPY', 'QQQ']:
            return 400.0  # Major ETFs
        
        # Exchange-specific estimates
        elif ticker.endswith('.NZ'):
            return 5.0  # New Zealand stocks typically lower
        elif ticker.endswith('.AX'):
            return 8.0  # Australian stocks
        elif ticker.upper() in ['ANZ', 'RIO']:
            return 120.0  # Major Australian stocks
        
        # ETFs and funds - order matters, specific tickers first
        elif ticker_upper in ['SMH']:
            return 200.0  # Semiconductor ETF - much higher
        elif ticker_upper in ['IXJ', 'IXUS']:
            return 65.0  # International ETFs
        elif any(x in ticker_upper for x in ['ETF', 'FUND', 'INDEX']):
            return 50.0  # General ETF range
        
        # Default by ticker length and pattern
        elif len(ticker) <= 3:
            return 100.0  # Major stocks usually 3 chars
        elif len(ticker) == 4 and not any(x in ticker for x in '.'):
            return 80.0  # Many 4-char tickers
        else:
            return 50.0  # Conservative default
    
    def _estimate_price_from_ticker(self, ticker: str) -> float:
        """Legacy method - kept for compatibility"""
        return self._get_reasonable_estimate(ticker)
    
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
        """Get comprehensive cache and API source statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Basic cache stats
            cursor.execute('SELECT COUNT(*), AVG(reliability_score), MAX(timestamp) FROM price_cache')
            stats = cursor.fetchone()
            
            cursor.execute('SELECT COUNT(*) FROM price_cache WHERE timestamp > ?', 
                         (datetime.now() - timedelta(hours=1),))
            recent_count = cursor.fetchone()[0]
            
            # Source usage statistics
            cursor.execute('''
                SELECT source, COUNT(*), AVG(price), MAX(timestamp)
                FROM price_cache 
                WHERE timestamp > ?
                GROUP BY source
                ORDER BY COUNT(*) DESC
            ''', (datetime.now() - timedelta(days=1),))
            
            source_stats = {}
            for row in cursor.fetchall():
                source_stats[row[0] or 'unknown'] = {
                    'requests_24h': row[1],
                    'avg_price': round(row[2] or 0, 2),
                    'last_used': row[3] or 'Never'
                }
            
            conn.close()
            
            # API source health
            api_health = {}
            for source, config in self.api_sources.items():
                usage = self.api_usage.get(source, {'count': 0, 'last_reset': datetime.now()})
                api_health[source] = {
                    'name': config['name'],
                    'reliability': round(config['reliability'], 3),
                    'consecutive_failures': config['consecutive_failures'],
                    'usage_count': usage['count'],
                    'rate_limit': config['rate_limit'],
                    'last_success': config['last_success'].isoformat() if config['last_success'] else 'Never',
                    'available': config['consecutive_failures'] < 5
                }
            
            return {
                'total_cached_tickers': stats[0] or 0,
                'average_reliability': round(stats[1] or 0, 2),
                'last_update': stats[2] or 'Never',
                'recent_updates': recent_count or 0,
                'memory_cache_size': len(self.memory_cache),
                'api_sources': api_health,
                'source_usage': source_stats,
                'system_version': 'Multi-Source Stable v2.0'
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
            
            print(f"CLEANED {deleted_count} old cache entries (older than {days_old} days)")
            return deleted_count
            
        except Exception as e:
            print(f"Cache cleanup failed: {e}")
            return 0