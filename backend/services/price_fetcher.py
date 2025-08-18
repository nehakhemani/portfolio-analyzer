"""
Optimized Price Fetching Service
High-performance price fetching with PostgreSQL integration and smart batching
"""
import asyncio
import aiohttp
import yfinance as yf
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import time
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

from config.database import get_db_manager

class OptimizedPriceFetcher:
    """
    High-performance price fetcher optimized for specific tickers only
    Features:
    - Async/concurrent fetching for better performance  
    - Smart batching to avoid API limits
    - Fallback between multiple API sources
    - PostgreSQL integration for caching
    - Rate limiting and error handling
    """
    
    def __init__(self):
        self.db_manager = get_db_manager()
        
        # API configuration with rate limits and timeouts
        self.api_sources = {
            'yahoo': {
                'batch_size': 100,  # Yahoo can handle large batches
                'timeout': 10,
                'rate_limit_per_minute': 2000,
                'priority': 1
            },
            'alpha_vantage': {
                'batch_size': 1,    # Alpha Vantage is single ticker only
                'timeout': 5,
                'rate_limit_per_minute': 25,
                'priority': 2,
                'api_key': 'demo'  # Replace with real key
            },
            'finnhub': {
                'batch_size': 1,    # Finnhub is single ticker only
                'timeout': 5,
                'rate_limit_per_minute': 60,
                'priority': 3,
                'api_key': 'demo'  # Replace with real key
            }
        }
        
        # Performance tracking
        self.fetch_stats = {
            'total_requests': 0,
            'successful_fetches': 0,
            'failed_fetches': 0,
            'cache_hits': 0,
            'api_calls': 0
        }
    
    async def fetch_prices_for_user(self, user_id: str, force_refresh: bool = False) -> Dict:
        """
        Fetch prices for all holdings of a specific user
        Only fetches the tickers this user actually owns (optimized!)
        """
        start_time = time.time()
        
        try:
            # Get user's portfolio tickers (optimized query)
            holdings = self.db_manager.get_portfolio_holdings(user_id, include_stale=True)
            tickers = list(set([holding['ticker'] for holding in holdings]))
            
            if not tickers:
                return {'success': 0, 'failed': 0, 'message': 'No holdings found for user'}
            
            logging.info(f"Fetching prices for user {user_id}: {len(tickers)} unique tickers")
            
            # Check cache first unless force refresh
            if not force_refresh:
                cached_prices = self._get_cached_prices(tickers)
            else:
                cached_prices = {}
            
            # Identify which tickers need fresh API calls
            stale_tickers = [ticker for ticker in tickers if ticker not in cached_prices]
            
            if not stale_tickers:
                logging.info(f"All prices cached for user {user_id}")
                price_results = cached_prices
                self.fetch_stats['cache_hits'] += len(tickers)
            else:
                logging.info(f"Fetching {len(stale_tickers)} stale prices via API")
                # Fetch fresh prices for stale tickers
                fresh_prices = await self._fetch_prices_batch(stale_tickers)
                
                # Combine cached and fresh prices
                price_results = {**cached_prices, **fresh_prices}
                self.fetch_stats['api_calls'] += len(stale_tickers)
            
            # Update user's portfolio with new prices
            update_results = self._update_user_portfolio_prices(user_id, price_results)
            
            duration = time.time() - start_time
            logging.info(f"Price fetch completed for user {user_id} in {duration:.2f}s: {update_results}")
            
            return {
                'success': update_results['success_count'],
                'failed': update_results['error_count'],
                'duration_seconds': duration,
                'cache_hits': len(cached_prices),
                'api_calls': len(stale_tickers),
                'total_tickers': len(tickers)
            }
            
        except Exception as e:
            logging.error(f"Error fetching prices for user {user_id}: {e}")
            return {'error': str(e)}
    
    async def fetch_prices_batch(self, tickers: List[str], timeout_seconds: int = 30) -> Dict[str, Dict]:
        """
        Fetch prices for a specific list of tickers
        Used by batch jobs and targeted API calls
        """
        if not tickers:
            return {}
        
        start_time = time.time()
        logging.info(f"Batch fetching prices for {len(tickers)} tickers (timeout: {timeout_seconds}s)")
        
        try:
            # Use asyncio with timeout for better performance
            price_results = await asyncio.wait_for(
                self._fetch_prices_batch(tickers),
                timeout=timeout_seconds
            )
            
            duration = time.time() - start_time
            success_count = len([p for p in price_results.values() if 'error' not in p])
            logging.info(f"Batch fetch completed in {duration:.2f}s: {success_count}/{len(tickers)} successful")
            
            return price_results
            
        except asyncio.TimeoutError:
            logging.warning(f"Batch price fetch timed out after {timeout_seconds}s")
            return {}
        except Exception as e:
            logging.error(f"Batch price fetch error: {e}")
            return {}
    
    async def _fetch_prices_batch(self, tickers: List[str]) -> Dict[str, Dict]:
        """Internal async batch price fetching with source fallbacks"""
        price_results = {}
        
        # Try Yahoo Finance first (fastest for batches)
        yahoo_results = await self._fetch_yahoo_batch(tickers)
        price_results.update(yahoo_results)
        
        # Identify failed tickers for fallback APIs
        failed_tickers = [ticker for ticker in tickers if ticker not in price_results or 'error' in price_results.get(ticker, {})]
        
        if failed_tickers and len(failed_tickers) <= 10:  # Only use fallback for small batches
            logging.info(f"Using fallback APIs for {len(failed_tickers)} failed tickers")
            
            # Try Alpha Vantage and Finnhub for failed tickers
            fallback_results = await self._fetch_fallback_apis(failed_tickers)
            price_results.update(fallback_results)
        
        return price_results
    
    async def _fetch_yahoo_batch(self, tickers: List[str]) -> Dict[str, Dict]:
        """Fetch prices from Yahoo Finance (optimized for batches)"""
        if not tickers:
            return {}
        
        try:
            # Use yfinance for batch downloading (most efficient)
            tickers_str = " ".join(tickers)
            
            # Execute in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=4) as executor:
                future = executor.submit(self._yahoo_download, tickers_str)
                data = await loop.run_in_executor(None, lambda: future.result(timeout=10))
            
            if data is None or data.empty:
                return {}
            
            results = {}
            for ticker in tickers:
                try:
                    if ticker in data.columns:
                        ticker_data = data[ticker].dropna()
                        if not ticker_data.empty:
                            current_price = float(ticker_data.iloc[-1])
                            results[ticker] = {
                                'price': current_price,
                                'source': 'yahoo',
                                'timestamp': datetime.now(),
                                'currency': 'USD'
                            }
                        else:
                            results[ticker] = {'error': 'No data returned from Yahoo'}
                    else:
                        results[ticker] = {'error': 'Ticker not found in Yahoo response'}
                        
                except (KeyError, IndexError, ValueError) as e:
                    results[ticker] = {'error': f'Yahoo data parsing error: {e}'}
            
            successful = len([r for r in results.values() if 'error' not in r])
            logging.info(f"Yahoo Finance batch: {successful}/{len(tickers)} successful")
            
            # Record API usage
            self.db_manager.record_api_usage(
                api_source='yahoo',
                endpoint_type='batch_download',
                tickers_requested=tickers,
                success_count=successful,
                error_count=len(tickers) - successful,
                response_time_ms=int(time.time() * 1000)
            )
            
            return results
            
        except Exception as e:
            logging.error(f"Yahoo batch fetch error: {e}")
            return {}
    
    def _yahoo_download(self, tickers_str: str):
        """Synchronous Yahoo Finance download (for thread pool)"""
        try:
            return yf.download(tickers_str, period="1d", interval="1d", group_by='ticker', progress=False, show_errors=False)
        except Exception as e:
            logging.error(f"Yahoo download error: {e}")
            return None
    
    async def _fetch_fallback_apis(self, tickers: List[str]) -> Dict[str, Dict]:
        """Fetch from Alpha Vantage and Finnhub for failed tickers"""
        results = {}
        
        # Limit fallback API calls to avoid rate limits
        limited_tickers = tickers[:5]  # Only try top 5 failed tickers
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            for ticker in limited_tickers:
                # Try Alpha Vantage
                task = self._fetch_alpha_vantage_single(session, ticker)
                tasks.append(task)
        
            if tasks:
                fallback_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for ticker, result in zip(limited_tickers, fallback_results):
                    if isinstance(result, dict) and 'error' not in result:
                        results[ticker] = result
        
        return results
    
    async def _fetch_alpha_vantage_single(self, session: aiohttp.ClientSession, ticker: str) -> Dict:
        """Fetch single ticker from Alpha Vantage"""
        try:
            api_key = self.api_sources['alpha_vantage']['api_key']
            url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={api_key}"
            
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    quote = data.get('Global Quote', {})
                    
                    if quote and '05. price' in quote:
                        return {
                            'price': float(quote['05. price']),
                            'source': 'alpha_vantage',
                            'timestamp': datetime.now(),
                            'currency': 'USD'
                        }
            
            return {'error': 'Alpha Vantage API failed'}
            
        except Exception as e:
            return {'error': f'Alpha Vantage error: {e}'}
    
    def _get_cached_prices(self, tickers: List[str], max_age_hours: int = 4) -> Dict[str, Dict]:
        """Get cached prices from database (if recent enough)"""
        if not tickers:
            return {}
        
        try:
            placeholders = ','.join(['%s'] * len(tickers))
            query = f"""
                SELECT DISTINCT ON (ticker) 
                    ticker, price, source, price_time as timestamp
                FROM price_history 
                WHERE ticker IN ({placeholders})
                  AND price_time >= CURRENT_TIMESTAMP - INTERVAL '%s hours'
                ORDER BY ticker, price_time DESC
            """
            
            params = tuple(tickers) + (max_age_hours,)
            results = self.db_manager.execute_query(query, params)
            
            cached = {}
            for row in results:
                cached[row['ticker']] = {
                    'price': float(row['price']),
                    'source': f"{row['source']}_cached",
                    'timestamp': row['timestamp'],
                    'currency': 'USD'
                }
            
            logging.info(f"Found {len(cached)}/{len(tickers)} cached prices")
            return cached
            
        except Exception as e:
            logging.error(f"Cache lookup error: {e}")
            return {}
    
    def _update_user_portfolio_prices(self, user_id: str, price_data: Dict[str, Dict]) -> Dict[str, int]:
        """Update user's portfolio holdings with new prices"""
        if not price_data:
            return {'success_count': 0, 'error_count': 0}
        
        try:
            # Prepare batch updates
            price_updates = []
            for ticker, data in price_data.items():
                if 'error' not in data and 'price' in data:
                    price_updates.append({
                        'ticker': ticker,
                        'price': data['price'],
                        'source': data['source']
                    })
            
            # Execute batch update
            results = self.db_manager.update_portfolio_prices(user_id, price_updates)
            
            # Also store in price history for caching
            self._store_price_history(price_updates)
            
            return results
            
        except Exception as e:
            logging.error(f"Error updating portfolio prices for user {user_id}: {e}")
            return {'success_count': 0, 'error_count': len(price_data)}
    
    def _store_price_history(self, price_updates: List[Dict]):
        """Store prices in price_history table for caching"""
        try:
            queries = []
            for update in price_updates:
                queries.append({
                    'query': """
                        INSERT INTO price_history (ticker, price, price_date, source, fetch_duration_ms)
                        VALUES (%s, %s, CURRENT_DATE, %s, %s)
                        ON CONFLICT (ticker, price_date, source) DO UPDATE SET
                            price = EXCLUDED.price,
                            price_time = CURRENT_TIMESTAMP
                    """,
                    'params': (
                        update['ticker'],
                        update['price'],
                        update['source'],
                        50  # Approximate fetch duration
                    )
                })
            
            self.db_manager.execute_transaction(queries)
            logging.debug(f"Stored {len(price_updates)} prices in history")
            
        except Exception as e:
            logging.error(f"Error storing price history: {e}")
    
    def get_stale_tickers_for_user(self, user_id: str, hours_stale: int = 24) -> List[str]:
        """Get tickers that need updates for a specific user"""
        return self.db_manager.get_stale_tickers(user_id, hours_stale)
    
    def get_all_stale_tickers(self, hours_stale: int = 24) -> List[str]:
        """Get all tickers across all users that need updates"""
        return self.db_manager.get_stale_tickers(None, hours_stale)
    
    def get_fetch_stats(self) -> Dict:
        """Get performance statistics"""
        return {
            **self.fetch_stats,
            'cache_hit_rate': (self.fetch_stats['cache_hits'] / max(1, self.fetch_stats['total_requests'])) * 100
        }

# Global price fetcher instance
price_fetcher: Optional[OptimizedPriceFetcher] = None

def get_price_fetcher() -> OptimizedPriceFetcher:
    """Get or create price fetcher singleton"""
    global price_fetcher
    if price_fetcher is None:
        price_fetcher = OptimizedPriceFetcher()
    return price_fetcher