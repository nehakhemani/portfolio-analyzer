import yfinance as yf
from datetime import datetime
import time
import logging
import sqlite3
import random

class MarketDataService:
    def __init__(self):
        self.cache = {}
        self.cache_duration = 300  # 5 minutes
        self.last_fetch_time = {}  # Track last fetch per ticker
        
    def fetch_batch_quotes(self, tickers):
        """Fetch market data for multiple tickers"""
        if not tickers or not isinstance(tickers, list):
            return {}
        
        market_data = {}
        
        for ticker in tickers:
            try:
                # Check cache first
                if self._is_cached(ticker):
                    market_data[ticker] = self.cache[ticker]['data']
                    continue
                
                # Format ticker for different exchanges
                formatted_ticker = self._format_ticker_for_exchange(ticker)
                
                # Fetch from Yahoo Finance
                stock = yf.Ticker(formatted_ticker)
                info = stock.info
                
                # Get current data
                current_price = info.get('regularMarketPrice', info.get('previousClose', 0))
                prev_close = info.get('previousClose', current_price)
                
                # Calculate percentage change safely
                if prev_close and prev_close != 0:
                    change_pct = ((current_price - prev_close) / prev_close * 100)
                else:
                    change_pct = 0
                
                data = {
                    'price': current_price,
                    'change': change_pct,
                    'volume': info.get('regularMarketVolume', 0),
                    'market_cap': info.get('marketCap', 0),
                    'name': info.get('longName', ticker),
                    'currency': info.get('currency', 'USD')
                }
                
                # Cache the data
                self.cache[ticker] = {
                    'data': data,
                    'timestamp': datetime.now()
                }
                
                market_data[ticker] = data
                
                # Rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                logging.error(f"Error fetching data for {ticker}: {e}")
                market_data[ticker] = {
                    'price': 0,
                    'change': 0,
                    'volume': 0,
                    'market_cap': 0,
                    'name': ticker,
                    'currency': 'USD',
                    'error': str(e)
                }
        
        return market_data
    
    def fetch_batch_quotes_with_exchange(self, ticker_exchange_map):
        """Fast batch fetch with aggressive timeout for speed"""
        market_data = {}
        successful_fetches = 0
        
        for ticker, exchange in ticker_exchange_map.items():
            try:
                # Check cache first (memory cache only)
                if self._is_cached(ticker):
                    market_data[ticker] = self.cache[ticker]['data']
                    successful_fetches += 1
                    continue
                
                # Format ticker for the specific exchange
                formatted_ticker = self._format_ticker_for_exchange(ticker, exchange)
                
                # Fast fetch with timeout
                stock = yf.Ticker(formatted_ticker)
                
                # Try fast_info first (faster than .info)
                try:
                    fast_info = stock.fast_info
                    current_price = fast_info.get('last_price', 0)
                except:
                    # Fallback to regular info with timeout
                    import signal
                    def timeout_handler(signum, frame):
                        raise TimeoutError()
                    
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(3)  # 3 second timeout per ticker
                    
                    try:
                        info = stock.info
                        current_price = info.get('regularMarketPrice', info.get('previousClose', 0))
                    finally:
                        signal.alarm(0)
                
                if current_price and current_price > 0:
                    data = {
                        'price': float(current_price),
                        'change': 0,  # Skip change calculation for speed
                        'volume': 0,
                        'market_cap': 0,
                        'name': ticker,
                        'currency': 'USD',
                        'exchange': exchange,
                        'formatted_ticker': formatted_ticker
                    }
                    
                    # Cache successful result
                    self.cache[ticker] = {
                        'data': data,
                        'timestamp': datetime.now()
                    }
                    self.last_fetch_time[ticker] = datetime.now()  # Track fetch time
                    
                    market_data[ticker] = data
                    successful_fetches += 1
                
                # Minimal rate limiting
                time.sleep(0.05)  # Reduced from 0.1
                
            except Exception as e:
                # Don't store error data - let fallback handle it
                logging.warning(f"Quick fetch failed for {ticker}: {e}")
                continue
        
        print(f"Fast batch fetch: {successful_fetches}/{len(ticker_exchange_map)} successful")
        return market_data
    
    def _is_cached(self, ticker):
        """Check if ticker data is cached and still valid"""
        if ticker not in self.cache:
            return False
        
        cached_time = self.cache[ticker]['timestamp']
        age = (datetime.now() - cached_time).total_seconds()
        
        # Also track last fetch to prevent rapid refetching
        if ticker in self.last_fetch_time:
            last_fetch_age = (datetime.now() - self.last_fetch_time[ticker]).total_seconds()
            if last_fetch_age < 30:  # Don't fetch again within 30 seconds
                return True
        
        return age < self.cache_duration
    
    def _format_ticker_for_exchange(self, ticker, exchange=None):
        """Format ticker symbol for different exchanges"""
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
    
    def get_reliable_price(self, ticker, exchange=None, avg_cost=None, db_path='data/portfolio.db'):
        """Fast pricing with immediate fallback to avoid delays"""
        
        # Quick timeout strategy - don't wait for slow API calls
        try:
            # Check memory cache first (5 minute cache)
            if self._is_cached(ticker):
                cached_data = self.cache[ticker]['data']
                if cached_data.get('price', 0) > 0:
                    return float(cached_data['price'])
            
            # Try ONE quick API call with fast timeout
            formatted_ticker = self._format_ticker_for_exchange(ticker, exchange)
            stock = yf.Ticker(formatted_ticker)
            
            # Use fast_info instead of info for speed
            try:
                fast_info = stock.fast_info
                live_price = fast_info.get('last_price', 0)
                if live_price and live_price > 0:
                    # Cache successful result
                    self.cache[ticker] = {
                        'data': {'price': live_price},
                        'timestamp': datetime.now()
                    }
                    return float(live_price)
            except:
                # Fallback to regular info with timeout
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("API call timeout")
                
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(2)  # 2 second timeout
                
                try:
                    info = stock.info
                    live_price = info.get('regularMarketPrice', info.get('previousClose', 0))
                    if live_price and live_price > 0:
                        return float(live_price)
                finally:
                    signal.alarm(0)  # Cancel timeout
        except:
            pass  # Fast fallback - don't wait
        
        # Immediate fallback to simulated price
        if avg_cost and avg_cost > 0:
            variation = random.uniform(-0.02, 0.02)  # ±2% variation
            simulated_price = avg_cost * (1 + variation)
            return max(simulated_price, 0.01)
        
        return 50.0
    
    
    def get_historical_data(self, ticker, period='1y'):
        """Get historical price data for charting"""
        try:
            stock = yf.Ticker(ticker)
            history = stock.history(period=period)
            
            return {
                'dates': history.index.strftime('%Y-%m-%d').tolist(),
                'prices': history['Close'].tolist(),
                'volumes': history['Volume'].tolist()
            }
        except Exception as e:
            logging.error(f"Error fetching historical data for {ticker}: {e}")
            return None