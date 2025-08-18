"""
Daily Price Batch Job
Scheduled job to update all portfolio prices at 5PM daily
High-performance batch processing with extended timeouts and comprehensive error handling
"""
import asyncio
import schedule
import time
from datetime import datetime, timedelta
import logging
from typing import Dict, List
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.price_fetcher import get_price_fetcher
from config.database import get_db_manager

class DailyPriceBatchJob:
    """
    Robust daily price batch job with extended timeouts and smart error handling
    Features:
    - Runs at 5PM daily (after market close)
    - Extended API timeouts (up to 5 minutes per batch)
    - Smart batching to optimize API usage
    - Comprehensive error handling and recovery
    - Detailed logging and monitoring
    - Fallback to previous day prices when needed
    """
    
    def __init__(self):
        self.db_manager = get_db_manager()
        self.price_fetcher = get_price_fetcher()
        self.job_name = "daily_price_update"
        self.job_type = "daily_prices"
        
        # Batch job configuration
        self.config = {
            'batch_size': 50,  # Process 50 tickers at a time
            'api_timeout_per_batch': 300,  # 5 minutes per batch (extended)
            'max_retries': 3,
            'retry_delay_seconds': 60,
            'market_close_time': '17:00',  # 5PM
            'max_execution_hours': 2,  # Job should complete within 2 hours
            'enable_fallback_prices': True
        }
        
        # Job statistics
        self.stats = {
            'start_time': None,
            'end_time': None,
            'total_tickers': 0,
            'successful_fetches': 0,
            'failed_fetches': 0,
            'retries_attempted': 0,
            'fallback_prices_used': 0,
            'execution_time_seconds': 0
        }
    
    def schedule_daily_job(self):
        """Schedule the job to run daily at 5PM"""
        schedule.every().day.at(self.config['market_close_time']).do(self._run_job_wrapper)
        
        # Also schedule a weekend catch-up job (Saturday 9AM)
        schedule.every().saturday.at("09:00").do(self._run_weekend_catchup)
        
        logging.info(f"Scheduled daily price job for {self.config['market_close_time']} daily")
        logging.info("Scheduled weekend catch-up job for Saturday 9:00 AM")
        
        # Start scheduler in background thread
        scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        scheduler_thread.start()
        
        return scheduler_thread
    
    def _run_scheduler(self):
        """Background thread to run the scheduler"""
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logging.error(f"Scheduler error: {e}")
                time.sleep(60)
    
    def _run_job_wrapper(self):
        """Wrapper to run job with proper error handling"""
        try:
            asyncio.run(self.run_daily_price_update())
        except Exception as e:
            logging.error(f"Daily price job failed: {e}")
            self._log_job_failure(str(e))
    
    async def run_daily_price_update(self) -> Dict:
        """
        Main entry point for daily price updates
        Extended timeouts and comprehensive error handling
        """
        self.stats['start_time'] = datetime.now()
        job_start_time = time.time()
        
        logging.info("=== DAILY PRICE BATCH JOB STARTED ===")
        
        try:
            # Start job log
            log_id = self._start_job_log()
            
            # Get all tickers that need updates across all users
            stale_tickers = self._get_all_stale_tickers()
            self.stats['total_tickers'] = len(stale_tickers)
            
            if not stale_tickers:
                logging.info("No stale tickers found - job completed early")
                return await self._complete_job_successfully(log_id, "No updates needed")
            
            logging.info(f"Found {len(stale_tickers)} tickers needing price updates")
            
            # Process tickers in batches with extended timeouts
            price_results = await self._process_tickers_in_batches(stale_tickers)
            
            # Update all user portfolios with new prices
            update_results = await self._update_all_user_portfolios(price_results)
            
            # Handle failed tickers with fallback prices
            if self.config['enable_fallback_prices']:
                await self._handle_failed_tickers_with_fallback(price_results)
            
            # Calculate final statistics
            self.stats['end_time'] = datetime.now()
            self.stats['execution_time_seconds'] = time.time() - job_start_time
            
            # Complete job log
            await self._complete_job_successfully(log_id, "Batch job completed successfully", update_results)
            
            logging.info(f"=== DAILY PRICE BATCH JOB COMPLETED ===")
            logging.info(f"Statistics: {self.stats}")
            
            return {
                'success': True,
                'statistics': self.stats,
                'update_results': update_results
            }
            
        except Exception as e:
            self.stats['end_time'] = datetime.now()
            self.stats['execution_time_seconds'] = time.time() - job_start_time
            
            logging.error(f"Daily price batch job failed: {e}")
            self._log_job_failure(str(e))
            
            return {
                'success': False,
                'error': str(e),
                'statistics': self.stats
            }
    
    async def _process_tickers_in_batches(self, tickers: List[str]) -> Dict[str, Dict]:
        """Process tickers in batches with extended timeouts and retries"""
        all_results = {}
        batch_size = self.config['batch_size']
        
        # Split tickers into batches
        ticker_batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
        
        logging.info(f"Processing {len(tickers)} tickers in {len(ticker_batches)} batches")
        
        for batch_num, ticker_batch in enumerate(ticker_batches):
            logging.info(f"Processing batch {batch_num + 1}/{len(ticker_batches)}: {len(ticker_batch)} tickers")
            
            # Process batch with retries
            batch_results = await self._process_batch_with_retries(ticker_batch, batch_num + 1)
            all_results.update(batch_results)
            
            # Small delay between batches to be respectful to APIs
            if batch_num < len(ticker_batches) - 1:
                await asyncio.sleep(2)
        
        # Update statistics
        self.stats['successful_fetches'] = len([r for r in all_results.values() if 'error' not in r])
        self.stats['failed_fetches'] = len([r for r in all_results.values() if 'error' in r])
        
        logging.info(f"Batch processing completed: {self.stats['successful_fetches']} successful, {self.stats['failed_fetches']} failed")
        
        return all_results
    
    async def _process_batch_with_retries(self, ticker_batch: List[str], batch_num: int) -> Dict[str, Dict]:
        """Process a single batch with retry logic"""
        for attempt in range(self.config['max_retries']):
            try:
                logging.info(f"Batch {batch_num} attempt {attempt + 1}/{self.config['max_retries']}")
                
                # Fetch with extended timeout
                batch_results = await self.price_fetcher.fetch_prices_batch(
                    ticker_batch, 
                    timeout_seconds=self.config['api_timeout_per_batch']
                )
                
                if batch_results:
                    successful = len([r for r in batch_results.values() if 'error' not in r])
                    logging.info(f"Batch {batch_num} completed: {successful}/{len(ticker_batch)} successful")
                    return batch_results
                else:
                    logging.warning(f"Batch {batch_num} returned no results")
                
            except Exception as e:
                logging.error(f"Batch {batch_num} attempt {attempt + 1} failed: {e}")
                self.stats['retries_attempted'] += 1
                
                if attempt < self.config['max_retries'] - 1:
                    logging.info(f"Retrying batch {batch_num} in {self.config['retry_delay_seconds']} seconds...")
                    await asyncio.sleep(self.config['retry_delay_seconds'])
        
        # All retries failed - return empty results
        logging.error(f"Batch {batch_num} failed all retry attempts")
        return {}
    
    async def _update_all_user_portfolios(self, price_results: Dict[str, Dict]) -> Dict:
        """Update all user portfolios with the fetched prices"""
        if not price_results:
            return {'users_updated': 0, 'total_updates': 0}
        
        try:
            # Get all users who have holdings in the updated tickers
            successful_tickers = [ticker for ticker, data in price_results.items() if 'error' not in data]
            
            if not successful_tickers:
                return {'users_updated': 0, 'total_updates': 0}
            
            # Query to find all users with these tickers
            placeholders = ','.join(['%s'] * len(successful_tickers))
            query = f"""
                SELECT DISTINCT user_id 
                FROM portfolio_holdings 
                WHERE ticker IN ({placeholders}) AND is_active = true
            """
            
            users = self.db_manager.execute_query(query, tuple(successful_tickers))
            
            # Update each user's portfolio
            total_updates = 0
            users_updated = 0
            
            for user_row in users:
                user_id = user_row['user_id']
                
                # Prepare updates for this user's tickers only
                user_tickers = self._get_user_tickers(user_id, successful_tickers)
                user_price_updates = []
                
                for ticker in user_tickers:
                    if ticker in price_results and 'error' not in price_results[ticker]:
                        user_price_updates.append({
                            'ticker': ticker,
                            'price': price_results[ticker]['price'],
                            'source': 'batch_job'
                        })
                
                if user_price_updates:
                    update_result = self.db_manager.update_portfolio_prices(user_id, user_price_updates)
                    total_updates += update_result['success_count']
                    if update_result['success_count'] > 0:
                        users_updated += 1
            
            logging.info(f"Portfolio updates completed: {users_updated} users updated, {total_updates} total price updates")
            
            return {
                'users_updated': users_updated,
                'total_updates': total_updates,
                'successful_tickers': len(successful_tickers)
            }
            
        except Exception as e:
            logging.error(f"Error updating user portfolios: {e}")
            return {'users_updated': 0, 'total_updates': 0, 'error': str(e)}
    
    def _get_user_tickers(self, user_id: str, available_tickers: List[str]) -> List[str]:
        """Get the subset of tickers that a user actually owns"""
        try:
            placeholders = ','.join(['%s'] * len(available_tickers))
            query = f"""
                SELECT DISTINCT ticker 
                FROM portfolio_holdings 
                WHERE user_id = %s AND ticker IN ({placeholders}) AND is_active = true
            """
            
            params = (user_id,) + tuple(available_tickers)
            results = self.db_manager.execute_query(query, params)
            
            return [row['ticker'] for row in results]
            
        except Exception as e:
            logging.error(f"Error getting user tickers for {user_id}: {e}")
            return []
    
    async def _handle_failed_tickers_with_fallback(self, price_results: Dict[str, Dict]):
        """Handle failed tickers by using previous day prices as fallback"""
        failed_tickers = [ticker for ticker, data in price_results.items() if 'error' in data]
        
        if not failed_tickers:
            return
        
        logging.info(f"Applying fallback prices for {len(failed_tickers)} failed tickers")
        
        try:
            # Get previous day prices for failed tickers
            fallback_prices = self._get_fallback_prices(failed_tickers)
            
            if fallback_prices:
                # Update portfolios with fallback prices
                await self._apply_fallback_prices(fallback_prices)
                self.stats['fallback_prices_used'] = len(fallback_prices)
                logging.info(f"Applied {len(fallback_prices)} fallback prices")
            
        except Exception as e:
            logging.error(f"Error applying fallback prices: {e}")
    
    def _get_fallback_prices(self, failed_tickers: List[str]) -> Dict[str, Dict]:
        """Get the most recent prices for failed tickers (up to 7 days old)"""
        if not failed_tickers:
            return {}
        
        try:
            placeholders = ','.join(['%s'] * len(failed_tickers))
            query = f"""
                SELECT DISTINCT ON (ticker) 
                    ticker, price, source, price_date
                FROM price_history 
                WHERE ticker IN ({placeholders})
                  AND price_date >= CURRENT_DATE - INTERVAL '7 days'
                ORDER BY ticker, price_date DESC, created_at DESC
            """
            
            results = self.db_manager.execute_query(query, tuple(failed_tickers))
            
            fallback_prices = {}
            for row in results:
                fallback_prices[row['ticker']] = {
                    'price': float(row['price']),
                    'source': f"fallback_{row['source']}",
                    'original_date': row['price_date'],
                    'timestamp': datetime.now()
                }
            
            logging.info(f"Found fallback prices for {len(fallback_prices)}/{len(failed_tickers)} failed tickers")
            return fallback_prices
            
        except Exception as e:
            logging.error(f"Error getting fallback prices: {e}")
            return {}
    
    async def _apply_fallback_prices(self, fallback_prices: Dict[str, Dict]):
        """Apply fallback prices to all affected user portfolios"""
        try:
            tickers = list(fallback_prices.keys())
            placeholders = ','.join(['%s'] * len(tickers))
            
            # Get all users with these tickers
            query = f"""
                SELECT DISTINCT user_id 
                FROM portfolio_holdings 
                WHERE ticker IN ({placeholders}) AND is_active = true
            """
            
            users = self.db_manager.execute_query(query, tuple(tickers))
            
            for user_row in users:
                user_id = user_row['user_id']
                user_tickers = self._get_user_tickers(user_id, tickers)
                
                user_fallback_updates = []
                for ticker in user_tickers:
                    if ticker in fallback_prices:
                        user_fallback_updates.append({
                            'ticker': ticker,
                            'price': fallback_prices[ticker]['price'],
                            'source': fallback_prices[ticker]['source']
                        })
                
                if user_fallback_updates:
                    self.db_manager.update_portfolio_prices(user_id, user_fallback_updates)
            
        except Exception as e:
            logging.error(f"Error applying fallback prices: {e}")
    
    def _get_all_stale_tickers(self, hours_stale: int = 24) -> List[str]:
        """Get all unique tickers across all users that need updates"""
        return self.db_manager.get_stale_tickers(None, hours_stale)
    
    def _start_job_log(self) -> str:
        """Start batch job logging"""
        return self.db_manager.log_batch_job(
            job_name=self.job_name,
            job_type=self.job_type,
            status='RUNNING',
            start_time=self.stats['start_time']
        )
    
    async def _complete_job_successfully(self, log_id: str, message: str, update_results: Dict = None) -> Dict:
        """Complete job log with success status"""
        execution_details = {
            'statistics': self.stats,
            'message': message
        }
        
        if update_results:
            execution_details['update_results'] = update_results
        
        # Update job log
        query = """
            UPDATE batch_job_logs 
            SET end_time = %s, status = %s, 
                tickers_processed = %s, tickers_succeeded = %s, tickers_failed = %s,
                execution_details = %s
            WHERE log_id = %s
        """
        
        params = (
            self.stats['end_time'],
            'SUCCESS',
            self.stats['total_tickers'],
            self.stats['successful_fetches'],
            self.stats['failed_fetches'],
            json.dumps(execution_details),
            log_id
        )
        
        self.db_manager.execute_query(query, params, fetch_results=False)
        
        return execution_details
    
    def _log_job_failure(self, error_message: str):
        """Log job failure"""
        self.db_manager.log_batch_job(
            job_name=self.job_name,
            job_type=self.job_type,
            status='FAILED',
            start_time=self.stats['start_time'],
            end_time=self.stats['end_time'],
            tickers_processed=self.stats['total_tickers'],
            tickers_succeeded=self.stats['successful_fetches'],
            tickers_failed=self.stats['failed_fetches'],
            error_message=error_message,
            execution_details=self.stats
        )
    
    async def _run_weekend_catchup(self):
        """Weekend catch-up job for any missed updates"""
        logging.info("Running weekend catch-up price job...")
        
        # Find tickers that haven't been updated in 3+ days
        stale_tickers = self._get_all_stale_tickers(hours_stale=72)
        
        if stale_tickers:
            logging.info(f"Weekend catch-up: processing {len(stale_tickers)} very stale tickers")
            await self.run_daily_price_update()
        else:
            logging.info("Weekend catch-up: no stale tickers found")

def run_batch_job():
    """Standalone function to run the batch job (for manual execution)"""
    job = DailyPriceBatchJob()
    return asyncio.run(job.run_daily_price_update())

def start_scheduler():
    """Start the daily batch job scheduler"""
    job = DailyPriceBatchJob()
    return job.schedule_daily_job()

if __name__ == "__main__":
    # Run job immediately if called directly
    logging.basicConfig(level=logging.INFO)
    result = run_batch_job()
    print(f"Batch job result: {result}")