#!/usr/bin/env python3
"""
Multi-User CSV Upload Service
Handles CSV transaction upload and portfolio aggregation per user
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime
from .database_service import DatabaseService

class CSVUploadService:
    """Handle CSV uploads for multi-user portfolio system"""
    
    def __init__(self, database_service: DatabaseService):
        self.db = database_service
    
    def process_transaction_csv(self, user_id: int, csv_content: str) -> Dict:
        """Process uploaded transaction CSV for specific user"""
        try:
            # Parse CSV content
            df = pd.read_csv(pd.io.common.StringIO(csv_content))
            
            print(f"📊 Processing CSV for user {user_id}: {df.shape[0]} rows, {df.shape[1]} columns")
            print(f"📋 CSV columns: {list(df.columns)}")
            
            # Process transactions and aggregate by ticker
            result = self._process_transactions(user_id, df)
            
            return result
            
        except Exception as e:
            print(f"❌ CSV processing error: {e}")
            return {
                'success': False,
                'error': str(e),
                'holdings_created': 0
            }
    
    def _process_transactions(self, user_id: int, df: pd.DataFrame) -> Dict:
        """Process transaction data and aggregate by ticker"""
        
        transactions_data = {}
        errors = []
        processed_count = 0
        
        for idx, row in df.iterrows():
            try:
                # Extract transaction data
                ticker = str(row.get('Instrument code', '')).upper().strip()
                quantity = float(row.get('Quantity', 0))
                price = float(row.get('Price', 0))
                currency = str(row.get('Currency', 'USD')).upper()
                transaction_type = str(row.get('Transaction method', '')).upper()
                exchange = str(row.get('Market code', '')).upper()
                
                # Validate data
                if not ticker or quantity == 0 or price <= 0:
                    errors.append(f"Row {idx}: Invalid data - ticker='{ticker}', quantity={quantity}, price={price}")
                    continue
                
                # Create unique key for ticker + currency combination
                ticker_key = f"{ticker}_{currency}" if currency != 'USD' else ticker
                display_ticker = f"{ticker} ({currency})" if currency != 'USD' else ticker
                
                if ticker_key not in transactions_data:
                    transactions_data[ticker_key] = {
                        'ticker': ticker,
                        'display_ticker': display_ticker,
                        'currency': currency,
                        'exchange': exchange,
                        'total_quantity': 0,
                        'total_cost': 0,
                        'transactions': 0
                    }
                
                # Handle different transaction types
                if transaction_type in ['BUY', 'PURCHASE', 'B']:
                    transactions_data[ticker_key]['total_quantity'] += quantity
                    transactions_data[ticker_key]['total_cost'] += (quantity * price)
                elif transaction_type in ['SELL', 'SALE', 'S']:
                    transactions_data[ticker_key]['total_quantity'] -= quantity
                    # For sells, reduce cost basis proportionally
                    if transactions_data[ticker_key]['total_quantity'] > 0:
                        # Keep cost basis calculation simple for now
                        pass
                elif transaction_type in ['DIVIDEND', 'DIV']:
                    # Dividends don't affect position size but could be tracked separately
                    pass
                
                transactions_data[ticker_key]['transactions'] += 1
                processed_count += 1
                
            except Exception as e:
                errors.append(f"Row {idx}: Error processing - {str(e)}")
                continue
        
        # Clear user's existing portfolio first
        self.db.clear_user_portfolio(user_id)
        
        # Create new portfolio positions
        holdings_created = 0
        portfolio_summary = []
        
        for ticker_key, data in transactions_data.items():
            if data['total_quantity'] > 0 and data['total_cost'] > 0:
                average_cost = data['total_cost'] / data['total_quantity']
                
                # Add position to user's portfolio
                success = self.db.add_portfolio_position(
                    user_id=user_id,
                    ticker_symbol=data['display_ticker'],
                    quantity=data['total_quantity'],
                    average_cost=average_cost,
                    exchange=data.get('exchange')
                )
                
                if success:
                    holdings_created += 1
                    portfolio_summary.append({
                        'ticker': data['display_ticker'],
                        'quantity': data['total_quantity'],
                        'average_cost': average_cost,
                        'total_cost': data['total_cost'],
                        'transactions': data['transactions']
                    })
                    
                    print(f"✅ Created position: {data['display_ticker']} - {data['total_quantity']:.6f} @ ${average_cost:.2f}")
        
        # Calculate totals
        total_investment = sum(pos['total_cost'] for pos in portfolio_summary)
        
        return {
            'success': True,
            'message': f'Successfully processed {processed_count} transactions',
            'holdings_created': holdings_created,
            'total_investment': total_investment,
            'errors': errors[:10],  # Limit errors shown
            'debug_info': {
                'csv_rows': len(df),
                'transactions_processed': processed_count,
                'unique_tickers': holdings_created,
                'error_count': len(errors)
            },
            'portfolio_summary': portfolio_summary
        }
    
    def get_user_portfolio_data(self, user_id: int) -> Dict:
        """Get formatted portfolio data for user"""
        try:
            holdings = self.db.get_user_portfolio(user_id)
            
            if not holdings:
                return {
                    'success': False,
                    'error': 'No portfolio data found',
                    'holdings': [],
                    'summary': {
                        'total_holdings': 0,
                        'total_investment': 0,
                        'holdings_with_prices': 0
                    }
                }
            
            # Filter out negligible positions
            valid_holdings = [h for h in holdings if h['quantity'] > 0 and h['total_cost'] > 0.01]
            
            # Calculate summary
            total_investment = sum(h['total_cost'] for h in valid_holdings)
            total_current_value = sum(h['current_value'] for h in valid_holdings if h['current_value'])
            holdings_with_prices = sum(1 for h in valid_holdings if h['has_price'])
            
            # Format holdings for frontend
            formatted_holdings = []
            for holding in valid_holdings:
                formatted_holdings.append({
                    'ticker': holding['ticker'],
                    'quantity': holding['quantity'],
                    'avg_cost_basis': holding['average_cost'],
                    'total_investment_value': holding['total_cost'],
                    'current_price': holding['current_price'],
                    'current_value': holding['current_value'],
                    'return_amount': holding['unrealized_pnl'],
                    'return_pct': holding['return_percentage'],
                    'price_source': holding['price_source'],
                    'price_timestamp': holding['price_updated_at'],
                    'has_price': holding['has_price']
                })
            
            return {
                'success': True,
                'holdings': formatted_holdings,
                'summary': {
                    'total_holdings': len(valid_holdings),
                    'total_investment_value': total_investment,
                    'total_current_value': total_current_value if holdings_with_prices > 0 else None,
                    'total_return': (total_current_value - total_investment) if total_current_value else None,
                    'total_return_pct': ((total_current_value - total_investment) / total_investment * 100) if total_current_value and total_investment > 0 else None,
                    'holdings_with_prices': holdings_with_prices
                },
                'workflow_step': 'batch_job_ready' if len(valid_holdings) > 0 else 'upload_needed'
            }
            
        except Exception as e:
            print(f"❌ Error getting portfolio data for user {user_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'holdings': [],
                'summary': {'total_holdings': 0, 'total_investment': 0}
            }