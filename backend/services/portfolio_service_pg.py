"""
PostgreSQL-Based Portfolio Service
High-performance portfolio management with optimized database operations
"""
import asyncio
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
import logging
import pandas as pd
import uuid
import json

from config.database import get_db_manager
from services.price_fetcher import get_price_fetcher

class PostgreSQLPortfolioService:
    """
    Production-ready portfolio service using PostgreSQL
    Features:
    - User-specific portfolio management
    - Optimized price fetching for user's tickers only
    - Real-time return calculations via database functions
    - Proper transaction handling
    - Comprehensive error handling
    """
    
    def __init__(self):
        self.db_manager = get_db_manager()
        self.price_fetcher = get_price_fetcher()
    
    def create_user_account(self, username: str, email: str, password_hash: str) -> str:
        """Create a new user account and return user_id"""
        try:
            query = """
                INSERT INTO users (username, email, password_hash)
                VALUES (%s, %s, %s)
                RETURNING user_id
            """
            
            results = self.db_manager.execute_query(query, (username, email, password_hash))
            if results:
                user_id = str(results[0]['user_id'])
                logging.info(f"Created user account: {username} ({user_id})")
                return user_id
            
            raise Exception("Failed to create user account")
            
        except Exception as e:
            logging.error(f"Error creating user account: {e}")
            raise
    
    def upload_transactions_csv(self, user_id: str, csv_content: str) -> Dict:
        """
        Process CSV upload and create/update portfolio holdings
        Much more efficient than the old approach
        """
        try:
            # Parse CSV content
            import io
            df = pd.read_csv(io.StringIO(csv_content))
            
            # Validate CSV format
            required_columns = ['ticker', 'transaction_type', 'quantity', 'price', 'trade_date']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                return {'error': f'Missing required columns: {missing_columns}'}
            
            # Process transactions
            processed_transactions = []
            portfolio_updates = {}
            
            for _, row in df.iterrows():
                ticker = str(row['ticker']).upper().strip()
                transaction_type = str(row['transaction_type']).upper().strip()
                quantity = float(row['quantity'])
                price = float(row['price'])
                trade_date = pd.to_datetime(row['trade_date']).date()
                fees = float(row.get('fees', 0))
                exchange = str(row.get('exchange', 'NASDAQ')).upper()
                currency = str(row.get('currency', 'USD')).upper()
                
                # Store transaction
                transaction_id = str(uuid.uuid4())
                processed_transactions.append({
                    'transaction_id': transaction_id,
                    'user_id': user_id,
                    'ticker': ticker,
                    'transaction_type': transaction_type,
                    'quantity': quantity,
                    'price': price,
                    'trade_date': trade_date,
                    'fees': fees,
                    'exchange': exchange,
                    'currency': currency,
                    'notes': row.get('notes', '')
                })
                
                # Update portfolio position
                if ticker not in portfolio_updates:
                    portfolio_updates[ticker] = {
                        'ticker': ticker,
                        'exchange': exchange,
                        'currency': currency,
                        'total_quantity': 0,
                        'total_investment': 0,
                        'transactions': []
                    }
                
                if transaction_type in ['BUY', 'SELL']:
                    signed_quantity = quantity if transaction_type == 'BUY' else -quantity
                    portfolio_updates[ticker]['total_quantity'] += signed_quantity
                    portfolio_updates[ticker]['total_investment'] += signed_quantity * price + fees
                
                portfolio_updates[ticker]['transactions'].append({
                    'type': transaction_type,
                    'quantity': quantity,
                    'price': price,
                    'date': trade_date
                })
            
            # Save to database in transaction
            result = self._save_transactions_and_portfolio(user_id, processed_transactions, portfolio_updates)
            
            if result['success']:
                return {
                    'success': True,
                    'message': f'Successfully processed {len(processed_transactions)} transactions',
                    'transactions_processed': len(processed_transactions),
                    'unique_tickers': len(portfolio_updates),
                    'portfolio_summary': result['portfolio_summary']
                }
            else:
                return {'error': result['error']}
                
        except Exception as e:
            logging.error(f"Error uploading transactions: {e}")
            return {'error': f'Failed to process CSV: {str(e)}'}
    
    def _save_transactions_and_portfolio(self, user_id: str, transactions: List[Dict], portfolio_updates: Dict) -> Dict:
        """Save transactions and portfolio holdings in a database transaction"""
        try:
            queries = []
            
            # Clear existing data for this user (if re-uploading)
            queries.extend([
                {
                    'query': "DELETE FROM transactions WHERE user_id = %s",
                    'params': (user_id,)
                },
                {
                    'query': "DELETE FROM portfolio_holdings WHERE user_id = %s",
                    'params': (user_id,)
                }
            ])
            
            # Insert transactions
            for transaction in transactions:
                queries.append({
                    'query': """
                        INSERT INTO transactions (
                            transaction_id, user_id, ticker, transaction_type, 
                            quantity, price, total_amount, fees, currency, 
                            trade_date, exchange, notes
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    'params': (
                        transaction.get('transaction_id', str(uuid.uuid4())),
                        user_id,
                        transaction['ticker'],
                        transaction['transaction_type'],
                        transaction['quantity'],
                        transaction['price'],
                        abs(transaction['quantity'] * transaction['price']),
                        transaction.get('fees', 0),
                        transaction.get('currency', 'USD'),
                        transaction['trade_date'],
                        transaction.get('exchange', 'NASDAQ'),
                        transaction.get('notes', '')
                    )
                })
            
            # Insert/update portfolio holdings
            for ticker_data in portfolio_updates.values():
                if ticker_data['total_quantity'] > 0.0001:  # Only create holdings for positive positions
                    avg_cost_basis = abs(ticker_data['total_investment'] / ticker_data['total_quantity'])
                    
                    queries.append({
                        'query': """
                            INSERT INTO portfolio_holdings (
                                user_id, ticker, exchange, currency, quantity, 
                                avg_cost_basis, price_source, created_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        'params': (
                            user_id,
                            ticker_data['ticker'],
                            ticker_data['exchange'],
                            ticker_data['currency'],
                            ticker_data['total_quantity'],
                            avg_cost_basis,
                            'manual',
                            datetime.now()
                        )
                    })
            
            # Execute all queries in transaction
            if self.db_manager.execute_transaction(queries):
                # Get portfolio summary
                summary = self.get_portfolio_summary(user_id)
                
                return {
                    'success': True,
                    'portfolio_summary': summary
                }
            else:
                return {'success': False, 'error': 'Database transaction failed'}
                
        except Exception as e:
            logging.error(f"Error saving transactions and portfolio: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_portfolio_holdings(self, user_id: str, include_prices: bool = True) -> List[Dict]:
        """Get user's portfolio holdings with optional price data"""
        try:
            holdings = self.db_manager.get_portfolio_holdings(user_id, include_stale=True)
            
            if not holdings:
                return []
            
            # Convert to standard format
            result = []
            for holding in holdings:
                holding_dict = {
                    'holding_id': str(holding['holding_id']),
                    'ticker': holding['ticker'],
                    'exchange': holding['exchange'],
                    'currency': holding['currency'],
                    'quantity': float(holding['quantity']),
                    'avg_cost_basis': float(holding['avg_cost_basis']),
                    'total_investment_value': float(holding['total_investment_value']),
                    'current_price': float(holding['current_price']) if holding['current_price'] else None,
                    'current_value': float(holding['current_value']) if holding['current_value'] else None,
                    'total_return': float(holding['total_return']) if holding['total_return'] else None,
                    'return_percentage': float(holding['return_percentage']) if holding['return_percentage'] else None,
                    'price_last_updated': holding['price_last_updated'],
                    'price_source': holding['price_source'],
                    'created_at': holding['created_at']
                }
                
                # Add effective price (considering manual overrides)
                if 'effective_price' in holding:
                    holding_dict['effective_price'] = float(holding['effective_price']) if holding['effective_price'] else None
                    holding_dict['effective_source'] = holding['effective_source']
                    holding_dict['effective_updated_at'] = holding['effective_updated_at']
                
                result.append(holding_dict)
            
            return result
            
        except Exception as e:
            logging.error(f"Error getting portfolio holdings for user {user_id}: {e}")
            return []
    
    async def fetch_live_prices_for_user(self, user_id: str, force_refresh: bool = False) -> Dict:
        """
        Fetch live prices for user's holdings only (optimized!)
        Only calls APIs for tickers this user actually owns
        """
        try:
            # This is the key optimization - only fetch prices for user's tickers
            result = await self.price_fetcher.fetch_prices_for_user(user_id, force_refresh)
            
            if 'error' not in result:
                logging.info(f"Price fetch for user {user_id}: {result['success']} successful, {result['failed']} failed")
            
            return result
            
        except Exception as e:
            logging.error(f"Error fetching live prices for user {user_id}: {e}")
            return {'error': str(e)}
    
    def set_manual_price(self, user_id: str, ticker: str, price: float, currency: str = 'USD', notes: str = None) -> bool:
        """Set manual price override for a specific ticker"""
        try:
            query = """
                INSERT INTO manual_price_overrides (user_id, ticker, manual_price, currency, notes)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id, ticker) WHERE is_active = true
                DO UPDATE SET 
                    manual_price = EXCLUDED.manual_price,
                    currency = EXCLUDED.currency,
                    notes = EXCLUDED.notes,
                    set_date = CURRENT_DATE,
                    created_at = CURRENT_TIMESTAMP
            """
            
            self.db_manager.execute_query(query, (user_id, ticker.upper(), price, currency.upper(), notes), fetch_results=False)
            
            logging.info(f"Manual price set for user {user_id}, ticker {ticker}: ${price}")
            return True
            
        except Exception as e:
            logging.error(f"Error setting manual price: {e}")
            return False
    
    def remove_manual_price(self, user_id: str, ticker: str) -> bool:
        """Remove manual price override"""
        try:
            query = """
                UPDATE manual_price_overrides 
                SET is_active = false 
                WHERE user_id = %s AND ticker = %s AND is_active = true
            """
            
            self.db_manager.execute_query(query, (user_id, ticker.upper()), fetch_results=False)
            
            logging.info(f"Manual price removed for user {user_id}, ticker {ticker}")
            return True
            
        except Exception as e:
            logging.error(f"Error removing manual price: {e}")
            return False
    
    def get_manual_price_overrides(self, user_id: str) -> List[Dict]:
        """Get all manual price overrides for a user"""
        try:
            query = """
                SELECT ticker, manual_price, currency, set_date, notes, created_at
                FROM manual_price_overrides
                WHERE user_id = %s AND is_active = true
                  AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                ORDER BY ticker
            """
            
            results = self.db_manager.execute_query(query, (user_id,))
            
            return [{
                'ticker': row['ticker'],
                'manual_price': float(row['manual_price']),
                'currency': row['currency'],
                'set_date': row['set_date'],
                'notes': row['notes'],
                'created_at': row['created_at']
            } for row in results]
            
        except Exception as e:
            logging.error(f"Error getting manual price overrides: {e}")
            return []
    
    def get_portfolio_summary(self, user_id: str) -> Dict:
        """Get portfolio summary with real-time calculations"""
        try:
            summary = self.db_manager.get_portfolio_summary(user_id)
            
            if not summary:
                return {
                    'total_holdings': 0,
                    'total_investment': 0,
                    'total_current_value': 0,
                    'total_return': 0,
                    'avg_return_percentage': 0,
                    'holdings_with_prices': 0,
                    'holdings_updated_today': 0
                }
            
            return {
                'total_holdings': summary.get('total_holdings', 0),
                'total_investment': float(summary.get('total_investment', 0)),
                'total_current_value': float(summary.get('total_current_value', 0)),
                'total_return': float(summary.get('total_return', 0)),
                'avg_return_percentage': float(summary.get('avg_return_percentage', 0)),
                'holdings_with_prices': summary.get('holdings_with_prices', 0),
                'holdings_updated_today': summary.get('holdings_updated_today', 0),
                'price_coverage': (summary.get('holdings_with_prices', 0) / max(1, summary.get('total_holdings', 1))) * 100
            }
            
        except Exception as e:
            logging.error(f"Error getting portfolio summary: {e}")
            return {}
    
    def get_stale_tickers_for_user(self, user_id: str, hours_stale: int = 24) -> List[str]:
        """Get tickers that need price updates for a specific user"""
        return self.price_fetcher.get_stale_tickers_for_user(user_id, hours_stale)
    
    def delete_holding(self, user_id: str, ticker: str) -> bool:
        """Delete a holding from portfolio"""
        try:
            query = """
                UPDATE portfolio_holdings 
                SET is_active = false 
                WHERE user_id = %s AND ticker = %s
            """
            
            self.db_manager.execute_query(query, (user_id, ticker.upper()), fetch_results=False)
            
            logging.info(f"Holding deleted for user {user_id}: {ticker}")
            return True
            
        except Exception as e:
            logging.error(f"Error deleting holding: {e}")
            return False
    
    def add_manual_holding(self, user_id: str, ticker: str, quantity: float, avg_cost: float, 
                          exchange: str = 'NASDAQ', currency: str = 'USD') -> bool:
        """Add a manual holding to portfolio"""
        try:
            query = """
                INSERT INTO portfolio_holdings (
                    user_id, ticker, exchange, currency, quantity, avg_cost_basis, price_source
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, ticker) DO UPDATE SET
                    quantity = EXCLUDED.quantity,
                    avg_cost_basis = EXCLUDED.avg_cost_basis,
                    exchange = EXCLUDED.exchange,
                    currency = EXCLUDED.currency,
                    updated_at = CURRENT_TIMESTAMP,
                    is_active = true
            """
            
            self.db_manager.execute_query(
                query, 
                (user_id, ticker.upper(), exchange.upper(), currency.upper(), quantity, avg_cost, 'manual'),
                fetch_results=False
            )
            
            logging.info(f"Manual holding added for user {user_id}: {ticker} ({quantity} @ ${avg_cost})")
            return True
            
        except Exception as e:
            logging.error(f"Error adding manual holding: {e}")
            return False
    
    def get_user_transactions(self, user_id: str, ticker: Optional[str] = None) -> List[Dict]:
        """Get transaction history for user"""
        try:
            where_clause = "WHERE user_id = %s"
            params = [user_id]
            
            if ticker:
                where_clause += " AND ticker = %s"
                params.append(ticker.upper())
            
            query = f"""
                SELECT transaction_id, ticker, transaction_type, quantity, price, 
                       total_amount, fees, currency, trade_date, exchange, notes, created_at
                FROM transactions
                {where_clause}
                ORDER BY trade_date DESC, created_at DESC
            """
            
            results = self.db_manager.execute_query(query, tuple(params))
            
            return [{
                'transaction_id': str(row['transaction_id']),
                'ticker': row['ticker'],
                'transaction_type': row['transaction_type'],
                'quantity': float(row['quantity']),
                'price': float(row['price']),
                'total_amount': float(row['total_amount']),
                'fees': float(row['fees']),
                'currency': row['currency'],
                'trade_date': row['trade_date'],
                'exchange': row['exchange'],
                'notes': row['notes'],
                'created_at': row['created_at']
            } for row in results]
            
        except Exception as e:
            logging.error(f"Error getting user transactions: {e}")
            return []

# Global portfolio service instance
portfolio_service: Optional[PostgreSQLPortfolioService] = None

def get_portfolio_service() -> PostgreSQLPortfolioService:
    """Get or create portfolio service singleton"""
    global portfolio_service
    if portfolio_service is None:
        portfolio_service = PostgreSQLPortfolioService()
    return portfolio_service