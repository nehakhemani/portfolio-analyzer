"""
PostgreSQL Database Configuration and Connection Management
High-performance, production-ready database setup
"""
import os
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor, Json
import logging
from contextlib import contextmanager
from typing import Dict, Any, Optional, List
import time

class DatabaseConfig:
    """Database configuration management"""
    
    def __init__(self):
        # Database connection parameters
        self.host = os.getenv('DB_HOST', 'localhost')
        self.port = int(os.getenv('DB_PORT', '5432'))
        self.database = os.getenv('DB_NAME', 'portfolio_analyzer')
        self.username = os.getenv('DB_USER', 'portfolio_user')
        self.password = os.getenv('DB_PASSWORD', 'portfolio_pass')
        
        # Connection pool settings
        self.min_connections = int(os.getenv('DB_MIN_CONNECTIONS', '5'))
        self.max_connections = int(os.getenv('DB_MAX_CONNECTIONS', '20'))
        
        # Performance settings
        self.connection_timeout = int(os.getenv('DB_CONNECTION_TIMEOUT', '30'))
        self.query_timeout = int(os.getenv('DB_QUERY_TIMEOUT', '60'))
        
        # Create connection string
        self.connection_string = (
            f"host={self.host} port={self.port} dbname={self.database} "
            f"user={self.username} password={self.password} "
            f"connect_timeout={self.connection_timeout}"
        )
        
        logging.info(f"Database config: {self.host}:{self.port}/{self.database}")

class DatabaseManager:
    """Production-grade database connection and query management"""
    
    def __init__(self):
        self.config = DatabaseConfig()
        self.pool: Optional[ThreadedConnectionPool] = None
        self._initialize_connection_pool()
    
    def _initialize_connection_pool(self):
        """Initialize PostgreSQL connection pool"""
        try:
            self.pool = ThreadedConnectionPool(
                minconn=self.config.min_connections,
                maxconn=self.config.max_connections,
                dsn=self.config.connection_string,
                cursor_factory=RealDictCursor  # Return dict-like results
            )
            logging.info(f"Database connection pool initialized: {self.config.min_connections}-{self.config.max_connections} connections")
            
            # Test connection
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT version();")
                    version = cursor.fetchone()
                    logging.info(f"PostgreSQL version: {version['version']}")
                    
        except Exception as e:
            logging.error(f"Failed to initialize database connection pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections with automatic cleanup"""
        connection = None
        try:
            connection = self.pool.getconn()
            yield connection
        except Exception as e:
            if connection:
                connection.rollback()
            logging.error(f"Database connection error: {e}")
            raise
        finally:
            if connection:
                self.pool.putconn(connection)
    
    @contextmanager
    def get_transaction(self):
        """Context manager for database transactions with automatic commit/rollback"""
        with self.get_connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                logging.error(f"Transaction rolled back: {e}")
                raise
    
    def execute_query(self, query: str, params: tuple = None, fetch_results: bool = True) -> Optional[List[Dict]]:
        """Execute a query and return results"""
        start_time = time.time()
        
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                
                if fetch_results:
                    results = cursor.fetchall()
                    # Convert RealDictRow to regular dict
                    results = [dict(row) for row in results]
                else:
                    results = None
                    
                duration = (time.time() - start_time) * 1000
                logging.debug(f"Query executed in {duration:.2f}ms: {query[:100]}...")
                
                return results
    
    def execute_transaction(self, queries: List[Dict[str, Any]]) -> bool:
        """Execute multiple queries in a single transaction"""
        start_time = time.time()
        
        try:
            with self.get_transaction() as conn:
                with conn.cursor() as cursor:
                    for query_info in queries:
                        query = query_info['query']
                        params = query_info.get('params')
                        cursor.execute(query, params)
                    
                    duration = (time.time() - start_time) * 1000
                    logging.info(f"Transaction completed in {duration:.2f}ms ({len(queries)} queries)")
                    return True
                    
        except Exception as e:
            logging.error(f"Transaction failed: {e}")
            return False
    
    def get_portfolio_holdings(self, user_id: str, include_stale: bool = True) -> List[Dict]:
        """Get all portfolio holdings for a user"""
        where_clause = "WHERE ph.user_id = %s AND ph.is_active = true"
        if not include_stale:
            where_clause += " AND ph.price_last_updated >= CURRENT_DATE - INTERVAL '1 day'"
        
        query = f"""
            SELECT 
                ph.holding_id,
                ph.ticker,
                ph.exchange,
                ph.currency,
                ph.quantity,
                ph.avg_cost_basis,
                ph.total_investment_value,
                ph.current_price,
                ph.current_value,
                ph.total_return,
                ph.return_percentage,
                ph.price_last_updated,
                ph.price_source,
                ph.created_at,
                -- Check for manual override
                CASE WHEN mpo.manual_price IS NOT NULL THEN mpo.manual_price ELSE ph.current_price END as effective_price,
                CASE WHEN mpo.manual_price IS NOT NULL THEN 'manual_override' ELSE ph.price_source END as effective_source,
                CASE WHEN mpo.manual_price IS NOT NULL THEN mpo.created_at ELSE ph.price_last_updated END as effective_updated_at
            FROM portfolio_holdings ph
            LEFT JOIN manual_price_overrides mpo ON (
                ph.user_id = mpo.user_id 
                AND ph.ticker = mpo.ticker 
                AND mpo.is_active = true
                AND (mpo.expires_at IS NULL OR mpo.expires_at > CURRENT_TIMESTAMP)
            )
            {where_clause}
            ORDER BY ph.current_value DESC NULLS LAST
        """
        
        return self.execute_query(query, (user_id,))
    
    def update_portfolio_prices(self, user_id: str, price_updates: List[Dict]) -> Dict[str, int]:
        """Batch update portfolio prices"""
        queries = []
        success_count = 0
        error_count = 0
        
        for update in price_updates:
            ticker = update['ticker']
            price = update['price']
            source = update.get('source', 'api')
            
            queries.append({
                'query': """
                    UPDATE portfolio_holdings 
                    SET current_price = %s, 
                        price_last_updated = CURRENT_TIMESTAMP,
                        price_source = %s
                    WHERE user_id = %s AND ticker = %s AND is_active = true
                """,
                'params': (price, source, user_id, ticker)
            })
        
        # Execute in transaction
        if self.execute_transaction(queries):
            success_count = len(queries)
        else:
            error_count = len(queries)
        
        return {'success_count': success_count, 'error_count': error_count}
    
    def get_stale_tickers(self, user_id: Optional[str] = None, hours_stale: int = 24) -> List[str]:
        """Get tickers that need price updates"""
        where_clause = "WHERE ph.is_active = true"
        params = []
        
        if user_id:
            where_clause += " AND ph.user_id = %s"
            params.append(user_id)
        
        where_clause += " AND (ph.price_last_updated < CURRENT_TIMESTAMP - INTERVAL '%s hours' OR ph.price_last_updated IS NULL)"
        params.append(hours_stale)
        
        query = f"""
            SELECT DISTINCT ph.ticker
            FROM portfolio_holdings ph
            {where_clause}
            ORDER BY ph.ticker
        """
        
        results = self.execute_query(query, params)
        return [row['ticker'] for row in results]
    
    def log_batch_job(self, job_name: str, job_type: str, status: str, **kwargs) -> str:
        """Log batch job execution"""
        query = """
            INSERT INTO batch_job_logs (
                job_name, job_type, start_time, end_time, status,
                tickers_processed, tickers_succeeded, tickers_failed,
                error_message, execution_details
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING log_id
        """
        
        params = (
            job_name,
            job_type,
            kwargs.get('start_time'),
            kwargs.get('end_time'),
            status,
            kwargs.get('tickers_processed', 0),
            kwargs.get('tickers_succeeded', 0),
            kwargs.get('tickers_failed', 0),
            kwargs.get('error_message'),
            Json(kwargs.get('execution_details', {}))
        )
        
        results = self.execute_query(query, params)
        return results[0]['log_id'] if results else None
    
    def record_api_usage(self, api_source: str, endpoint_type: str, **kwargs):
        """Record API usage for monitoring"""
        query = """
            INSERT INTO api_usage_tracking (
                api_source, endpoint_type, request_count, response_status,
                response_time_ms, tickers_requested, success_count, 
                error_count, rate_limited
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        params = (
            api_source,
            endpoint_type,
            kwargs.get('request_count', 1),
            kwargs.get('response_status'),
            kwargs.get('response_time_ms'),
            kwargs.get('tickers_requested', []),
            kwargs.get('success_count', 0),
            kwargs.get('error_count', 0),
            kwargs.get('rate_limited', False)
        )
        
        self.execute_query(query, params, fetch_results=False)
    
    def cleanup_old_data(self, days_to_keep: int = 90):
        """Clean up old data to maintain performance"""
        queries = [
            {
                'query': "DELETE FROM price_history WHERE price_date < CURRENT_DATE - INTERVAL '%s days'",
                'params': (days_to_keep,)
            },
            {
                'query': "DELETE FROM batch_job_logs WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '%s days'",
                'params': (days_to_keep,)
            },
            {
                'query': "DELETE FROM api_usage_tracking WHERE created_date < CURRENT_DATE - INTERVAL '%s days'",
                'params': (days_to_keep,)
            }
        ]
        
        return self.execute_transaction(queries)
    
    def get_portfolio_summary(self, user_id: str) -> Dict:
        """Get portfolio summary statistics"""
        query = """
            SELECT * FROM portfolio_summary WHERE user_id = %s
        """
        
        results = self.execute_query(query, (user_id,))
        return results[0] if results else {}
    
    def close_pool(self):
        """Close database connection pool"""
        if self.pool:
            self.pool.closeall()
            logging.info("Database connection pool closed")

# Global database manager instance
db_manager: Optional[DatabaseManager] = None

def get_db_manager() -> DatabaseManager:
    """Get or create database manager singleton"""
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
    return db_manager

def init_database():
    """Initialize database with schema"""
    try:
        # Read and execute schema
        schema_path = os.path.join(os.path.dirname(__file__), '..', '..', 'database', 'schema.sql')
        
        if os.path.exists(schema_path):
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
            
            manager = get_db_manager()
            with manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(schema_sql)
                    conn.commit()
            
            logging.info("Database schema initialized successfully")
        else:
            logging.warning(f"Schema file not found: {schema_path}")
            
    except Exception as e:
        logging.error(f"Failed to initialize database schema: {e}")
        raise