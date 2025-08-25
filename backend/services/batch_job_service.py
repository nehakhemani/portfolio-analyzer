#!/usr/bin/env python3
"""
Multi-User Batch Job Service
Handles shared ticker price fetching for all users
"""

import yfinance as yf
import requests
import time
import os
from datetime import datetime
from typing import List, Dict, Tuple
from .database_service import DatabaseService

class BatchJobService:
    """Handle batch price fetching for shared ticker system"""
    
    def __init__(self, database_service: DatabaseService):
        self.db = database_service
    
    def run_price_sync_job(self, created_by_user_id: int = None) -> Dict:
        """Run comprehensive price sync for all tickers in system"""
        
        # Start batch job tracking
        job_start = datetime.now()
        job_id = self._log_job_start('price_sync', created_by_user_id)
        
        try:
            print(f"🔄 Starting batch job #{job_id}: Multi-user price sync")
            
            # Get all unique tickers from system
            all_tickers = self.db.get_all_unique_tickers()
            total_count = len(all_tickers)
            
            if total_count == 0:
                return self._complete_job(job_id, 0, 0, "No tickers found in system")
            
            print(f"📊 Found {total_count} unique tickers to update")
            
            # Use optimized bulk fetching
            price_results = self._fetch_prices_bulk_optimized(all_tickers)
            
            # Update ticker prices in database
            successful_count = 0
            errors = []
            
            for ticker in all_tickers:
                if ticker in price_results:
                    price, source = price_results[ticker]
                    success = self.db.update_ticker_price(ticker, price, source)
                    if success:
                        successful_count += 1
                        print(f"✅ Updated {ticker}: ${price:.2f} ({source})")
                    else:
                        errors.append(f"Database update failed for {ticker}")
                else:
                    errors.append(f"No price data found for {ticker}")
                    # Update failed fetch attempt
                    self._mark_ticker_fetch_failed(ticker)
            
            # Complete job tracking
            success_rate = (successful_count / total_count * 100) if total_count > 0 else 0
            duration = (datetime.now() - job_start).total_seconds()
            
            result = {
                'job_id': job_id,
                'total_tickers': total_count,
                'successful_tickers': successful_count,
                'failed_tickers': total_count - successful_count,
                'success_rate': success_rate,
                'duration_seconds': duration,
                'errors': errors[:10]  # Limit errors
            }
            
            self._complete_job(job_id, total_count, successful_count, '\n'.join(errors[:10]))
            
            print(f"🎉 Batch job #{job_id} completed: {successful_count}/{total_count} ({success_rate:.1f}% success)")
            print(f"📣 USER ACTION REQUIRED: Click '💹 Show Prices' button to view updated portfolio prices!")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Batch job #{job_id} failed: {error_msg}")
            self._fail_job(job_id, error_msg)
            return {
                'job_id': job_id,
                'error': error_msg,
                'total_tickers': 0,
                'successful_tickers': 0
            }
    
    def _fetch_prices_bulk_optimized(self, tickers: List[str]) -> Dict[str, Tuple[float, str]]:
        """Optimized bulk price fetching using multiple sources"""
        results = {}
        
        # Group tickers by exchange for optimization
        us_tickers = []
        au_tickers = []
        nz_tickers = []
        
        for ticker in tickers:
            base_ticker = ticker.split(' (')[0] if ' (' in ticker else ticker
            if '(AUD)' in ticker or '(AU)' in ticker:
                au_tickers.append((ticker, base_ticker + '.AX'))
            elif '(NZD)' in ticker or '(NZ)' in ticker:
                nz_tickers.append((ticker, base_ticker + '.NZ'))
            else:
                us_tickers.append((ticker, base_ticker))
        
        print(f"📦 Bulk fetching: {len(us_tickers)} US, {len(au_tickers)} AU, {len(nz_tickers)} NZ tickers")
        
        # Method 1: Yahoo Finance bulk (most efficient)
        all_yahoo_tickers = [yahoo_ticker for _, yahoo_ticker in us_tickers + au_tickers + nz_tickers]
        if all_yahoo_tickers:
            try:
                print(f"📡 Yahoo Finance bulk request for {len(all_yahoo_tickers)} tickers")
                tickers_str = ' '.join(all_yahoo_tickers)
                data = yf.download(tickers_str, period='1d', interval='1d', group_by='ticker', 
                                 auto_adjust=True, prepost=True, threads=True, proxy=None)
                
                if not data.empty:
                    ticker_mapping = {yahoo_ticker: original_ticker for original_ticker, yahoo_ticker in us_tickers + au_tickers + nz_tickers}
                    
                    if len(all_yahoo_tickers) == 1:
                        # Single ticker case
                        yahoo_ticker = all_yahoo_tickers[0]
                        original_ticker = ticker_mapping[yahoo_ticker]
                        if 'Close' in data.columns and not data['Close'].empty:
                            price = float(data['Close'].iloc[-1])
                            results[original_ticker] = (price, 'yahoo_bulk')
                    else:
                        # Multiple tickers case
                        for yahoo_ticker in all_yahoo_tickers:
                            original_ticker = ticker_mapping[yahoo_ticker]
                            try:
                                if hasattr(data.columns, 'levels') and yahoo_ticker in data.columns.levels[0]:
                                    close_prices = data[yahoo_ticker]['Close']
                                    if not close_prices.empty and not close_prices.iloc[-1] != close_prices.iloc[-1]:  # Check for NaN
                                        price = float(close_prices.iloc[-1])
                                        results[original_ticker] = (price, 'yahoo_bulk')
                            except Exception as e:
                                print(f"⚠️ Yahoo bulk error for {original_ticker}: {str(e)}")
                                continue
                    
                    print(f"🎉 Yahoo Finance bulk: {len(results)}/{len(all_yahoo_tickers)} successful")
                    
            except Exception as e:
                print(f"❌ Yahoo Finance bulk failed: {str(e)}")
        
        # Method 2: Alpha Vantage for missing tickers
        missing_tickers = [ticker for ticker in tickers if ticker not in results]
        alpha_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        
        if missing_tickers and alpha_key:
            print(f"📡 Alpha Vantage fallback for {len(missing_tickers)} missing tickers")
            for ticker in missing_tickers[:5]:  # Rate limit to 5
                try:
                    base_ticker = ticker.split(' (')[0] if ' (' in ticker else ticker
                    url = "https://www.alphavantage.co/query"
                    params = {
                        'function': 'GLOBAL_QUOTE',
                        'symbol': base_ticker,
                        'apikey': alpha_key
                    }
                    response = requests.get(url, params=params, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        if 'Global Quote' in data and '05. price' in data['Global Quote']:
                            price = float(data['Global Quote']['05. price'])
                            results[ticker] = (price, 'alpha_vantage')
                            print(f"✅ Alpha Vantage: {ticker} = ${price:.2f}")
                    
                    time.sleep(12)  # Rate limit: 5 per minute
                    
                except Exception as e:
                    print(f"❌ Alpha Vantage failed for {ticker}: {str(e)}")
        
        # Method 3: Finnhub for remaining missing tickers
        still_missing_tickers = [ticker for ticker in tickers if ticker not in results]
        finnhub_key = os.getenv('FINNHUB_API_KEY')
        
        if still_missing_tickers and finnhub_key:
            print(f"📡 Finnhub fallback for {len(still_missing_tickers)} remaining tickers")
            for ticker in still_missing_tickers:
                try:
                    base_ticker = ticker.split(' (')[0] if ' (' in ticker else ticker
                    url = "https://finnhub.io/api/v1/quote"
                    params = {
                        'symbol': base_ticker,
                        'token': finnhub_key
                    }
                    response = requests.get(url, params=params, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        if 'c' in data and data['c'] > 0:
                            price = float(data['c'])
                            results[ticker] = (price, 'finnhub')
                            print(f"✅ Finnhub: {ticker} = ${price:.2f}")
                    
                    time.sleep(1.5)  # Rate limit: 60 per minute
                    
                except Exception as e:
                    print(f"❌ Finnhub failed for {ticker}: {str(e)}")
        
        return results
    
    def _log_job_start(self, job_type: str, created_by_user_id: int = None) -> int:
        """Log batch job start"""
        conn = self.db.db_path
        import sqlite3
        
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO batch_jobs (job_type, started_at, status, created_by_user_id)
                VALUES (?, ?, ?, ?)
            """, (job_type, datetime.now().isoformat(), 'running', created_by_user_id))
            
            job_id = cursor.lastrowid
            conn.commit()
            return job_id
            
        except Exception as e:
            print(f"❌ Error logging job start: {e}")
            return None
        finally:
            conn.close()
    
    def _complete_job(self, job_id: int, total_tickers: int, successful_tickers: int, errors: str = None):
        """Mark batch job as completed"""
        import sqlite3
        
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        try:
            success_rate = (successful_tickers / total_tickers * 100) if total_tickers > 0 else 0
            
            cursor.execute("""
                UPDATE batch_jobs 
                SET completed_at = ?, status = ?, tickers_processed = ?, 
                    tickers_successful = ?, success_rate = ?, error_log = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), 'completed', total_tickers, 
                  successful_tickers, success_rate, errors, job_id))
            
            conn.commit()
            
        except Exception as e:
            print(f"❌ Error completing job: {e}")
        finally:
            conn.close()
    
    def _fail_job(self, job_id: int, error: str):
        """Mark batch job as failed"""
        import sqlite3
        
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE batch_jobs 
                SET completed_at = ?, status = ?, error_log = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), 'failed', error, job_id))
            
            conn.commit()
            
        except Exception as e:
            print(f"❌ Error failing job: {e}")
        finally:
            conn.close()
    
    def _mark_ticker_fetch_failed(self, ticker_symbol: str):
        """Mark ticker fetch attempt as failed"""
        import sqlite3
        
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE tickers 
                SET last_fetch_attempt = CURRENT_TIMESTAMP, fetch_success = 0
                WHERE ticker_symbol = ?
            """, (ticker_symbol,))
            
            conn.commit()
            
        except Exception as e:
            print(f"❌ Error marking ticker fetch failed: {e}")
        finally:
            conn.close()
    
    def get_batch_job_status(self, limit: int = 5) -> Dict:
        """Get recent batch job status"""
        import sqlite3
        
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, job_type, started_at, completed_at, status, 
                       tickers_processed, tickers_successful, success_rate, error_log
                FROM batch_jobs 
                ORDER BY started_at DESC 
                LIMIT ?
            """, (limit,))
            
            jobs = []
            for row in cursor.fetchall():
                job = {
                    'id': row[0],
                    'job_type': row[1],
                    'started_at': row[2],
                    'completed_at': row[3],
                    'status': row[4],
                    'tickers_processed': row[5] or 0,
                    'tickers_successful': row[6] or 0,
                    'success_rate': row[7] or 0,
                    'errors': row[8].split('\n') if row[8] else []
                }
                jobs.append(job)
            
            # Get database statistics
            stats = self.db.get_database_stats()
            
            return {
                'recent_jobs': jobs,
                'statistics': {
                    'tickers_with_prices': stats.get('tickers_with_prices', 0),
                    'total_tickers': stats.get('total_tickers', 0),
                    'active_users': stats.get('active_users', 0),
                    'total_positions': stats.get('total_positions', 0)
                }
            }
            
        except Exception as e:
            print(f"❌ Error getting batch job status: {e}")
            return {'recent_jobs': [], 'statistics': {}}
        finally:
            conn.close()