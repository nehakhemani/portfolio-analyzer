import yfinance as yf
from datetime import datetime
import time
import logging

class MarketDataService:
    def __init__(self):
        self.cache = {}
        self.cache_duration = 300  # 5 minutes
        
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
                
                # Fetch from Yahoo Finance
                stock = yf.Ticker(ticker)
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
    
    def _is_cached(self, ticker):
        """Check if ticker data is cached and still valid"""
        if ticker not in self.cache:
            return False
        
        cached_time = self.cache[ticker]['timestamp']
        age = (datetime.now() - cached_time).total_seconds()
        
        return age < self.cache_duration
    
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