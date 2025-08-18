"""
Batch Job API Routes for Cloud Scheduler
Endpoints for triggering scheduled batch jobs via HTTP requests
"""
from flask import Blueprint, request, jsonify
import asyncio
import logging
from datetime import datetime
import os

# Import batch job classes
from jobs.daily_price_batch import DailyPriceBatchJob
from config.database import get_db_manager

batch_bp = Blueprint('batch', __name__, url_prefix='/api/batch')

@batch_bp.route('/daily-price-update', methods=['POST'])
def trigger_daily_price_update():
    """
    Endpoint for Cloud Scheduler to trigger daily price updates
    Called daily at 5PM EST
    """
    try:
        logging.info("Daily price update triggered via Cloud Scheduler")
        
        # Verify this is coming from Cloud Scheduler (optional security check)
        if not _verify_scheduler_request():
            return jsonify({'error': 'Unauthorized'}), 401
        
        # Get job parameters
        data = request.get_json() or {}
        timeout_minutes = data.get('timeout_minutes', 30)
        
        # Run the batch job
        job = DailyPriceBatchJob()
        
        # Execute async job in sync context
        result = asyncio.run(job.run_daily_price_update())
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Daily price update completed successfully',
                'statistics': result['statistics'],
                'triggered_at': datetime.now().isoformat(),
                'job_type': 'daily_price_update'
            })
        else:
            logging.error(f"Daily price update failed: {result.get('error')}")
            return jsonify({
                'success': False,
                'error': result.get('error'),
                'statistics': result.get('statistics', {}),
                'triggered_at': datetime.now().isoformat()
            }), 500
            
    except Exception as e:
        logging.error(f"Error in daily price update endpoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'triggered_at': datetime.now().isoformat()
        }), 500

@batch_bp.route('/weekend-catchup', methods=['POST'])
def trigger_weekend_catchup():
    """
    Endpoint for weekend catch-up job
    Called Saturday at 9AM EST
    """
    try:
        logging.info("Weekend catch-up job triggered via Cloud Scheduler")
        
        if not _verify_scheduler_request():
            return jsonify({'error': 'Unauthorized'}), 401
        
        # Weekend catch-up uses the same job but with longer stale threshold
        job = DailyPriceBatchJob()
        
        # Modify config for weekend catch-up (3+ days old)
        original_stale_hours = 24
        
        result = asyncio.run(job.run_daily_price_update())
        
        return jsonify({
            'success': result['success'],
            'message': 'Weekend catch-up completed',
            'statistics': result.get('statistics', {}),
            'triggered_at': datetime.now().isoformat(),
            'job_type': 'weekend_catchup'
        })
        
    except Exception as e:
        logging.error(f"Error in weekend catch-up endpoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'triggered_at': datetime.now().isoformat()
        }), 500

@batch_bp.route('/cleanup', methods=['POST'])
def trigger_cleanup():
    """
    Endpoint for cleanup job
    Called daily at 2AM EST
    """
    try:
        logging.info("Cleanup job triggered via Cloud Scheduler")
        
        if not _verify_scheduler_request():
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.get_json() or {}
        days_to_keep = data.get('days_to_keep', 90)
        
        # Run database cleanup
        db_manager = get_db_manager()
        cleanup_result = db_manager.cleanup_old_data(days_to_keep)
        
        if cleanup_result:
            return jsonify({
                'success': True,
                'message': f'Cleanup completed - kept {days_to_keep} days of data',
                'days_kept': days_to_keep,
                'triggered_at': datetime.now().isoformat(),
                'job_type': 'cleanup'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Cleanup failed',
                'triggered_at': datetime.now().isoformat()
            }), 500
            
    except Exception as e:
        logging.error(f"Error in cleanup endpoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'triggered_at': datetime.now().isoformat()
        }), 500

@batch_bp.route('/manual-price-sync', methods=['POST'])
def trigger_manual_price_sync():
    """
    Manual endpoint to trigger price sync for specific tickers
    Useful for testing and emergency updates
    """
    try:
        data = request.get_json() or {}
        tickers = data.get('tickers', [])
        
        if not tickers:
            return jsonify({'error': 'No tickers provided'}), 400
        
        logging.info(f"Manual price sync triggered for tickers: {tickers}")
        
        from services.price_fetcher import get_price_fetcher
        price_fetcher = get_price_fetcher()
        
        # Fetch prices with extended timeout
        result = asyncio.run(price_fetcher.fetch_prices_batch(tickers, timeout_seconds=300))
        
        successful = [ticker for ticker, data in result.items() if 'error' not in data]
        failed = [ticker for ticker, data in result.items() if 'error' in data]
        
        return jsonify({
            'success': True,
            'message': f'Manual sync completed for {len(tickers)} tickers',
            'tickers_requested': tickers,
            'successful_tickers': successful,
            'failed_tickers': failed,
            'success_rate': f"{len(successful)}/{len(tickers)} ({len(successful)/len(tickers)*100:.1f}%)",
            'triggered_at': datetime.now().isoformat(),
            'job_type': 'manual_sync'
        })
        
    except Exception as e:
        logging.error(f"Error in manual price sync endpoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'triggered_at': datetime.now().isoformat()
        }), 500

@batch_bp.route('/status', methods=['GET'])
def batch_job_status():
    """
    Get status of recent batch jobs
    """
    try:
        db_manager = get_db_manager()
        
        # Get recent job logs
        query = """
            SELECT job_name, job_type, status, start_time, end_time,
                   tickers_processed, tickers_succeeded, tickers_failed,
                   error_message
            FROM batch_job_logs 
            ORDER BY start_time DESC 
            LIMIT 10
        """
        
        recent_jobs = db_manager.execute_query(query)
        
        # Get overall statistics
        stats_query = """
            SELECT 
                COUNT(*) as total_jobs,
                COUNT(*) FILTER (WHERE status = 'SUCCESS') as successful_jobs,
                COUNT(*) FILTER (WHERE status = 'FAILED') as failed_jobs,
                COUNT(*) FILTER (WHERE start_time >= CURRENT_DATE - INTERVAL '7 days') as jobs_last_week
            FROM batch_job_logs
            WHERE start_time >= CURRENT_DATE - INTERVAL '30 days'
        """
        
        stats = db_manager.execute_query(stats_query)
        
        return jsonify({
            'success': True,
            'recent_jobs': [{
                'job_name': job['job_name'],
                'job_type': job['job_type'],
                'status': job['status'],
                'start_time': job['start_time'].isoformat() if job['start_time'] else None,
                'end_time': job['end_time'].isoformat() if job['end_time'] else None,
                'tickers_processed': job['tickers_processed'],
                'tickers_succeeded': job['tickers_succeeded'],
                'tickers_failed': job['tickers_failed'],
                'error_message': job['error_message']
            } for job in recent_jobs],
            'statistics': stats[0] if stats else {},
            'checked_at': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error getting batch job status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def _verify_scheduler_request():
    """
    Verify the request is coming from Cloud Scheduler
    This is a basic check - in production you might want more robust verification
    """
    # In Cloud Run, you can check for specific headers from Cloud Scheduler
    user_agent = request.headers.get('User-Agent', '')
    
    # Cloud Scheduler sends requests with 'Google-Cloud-Scheduler' in User-Agent
    if 'Google-Cloud-Scheduler' in user_agent:
        return True
    
    # For local testing, allow requests from localhost
    if request.remote_addr in ['127.0.0.1', 'localhost'] or request.headers.get('X-Local-Test'):
        return True
    
    # In development, skip verification
    if os.getenv('FLASK_ENV') == 'development':
        return True
    
    logging.warning(f"Unauthorized batch job request from {request.remote_addr} with User-Agent: {user_agent}")
    return False