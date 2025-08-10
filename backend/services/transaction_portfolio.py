#!/usr/bin/env python3
"""
Transaction-based portfolio calculation service
This calculates the actual portfolio based on transaction history and current market prices
"""

import pandas as pd
import sqlite3
from datetime import datetime
from services.stable_market_data import StableMarketDataService as MarketDataService

class TransactionPortfolioService:
    def __init__(self):
        self.market_service = MarketDataService()
    
    def calculate_portfolio_from_transactions(self, db_path, fetch_prices=False):
        """Calculate the actual portfolio based on transaction history"""
        
        try:
            # First check if we have a transactions table
            conn = sqlite3.connect(db_path)
            
            # Check if transactions table exists
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'")
            transactions_table_exists = cursor.fetchone() is not None
            
            if not transactions_table_exists:
                conn.close()
                return {'holdings': [], 'summary': self._empty_summary(), 'error': 'No transactions table found. Please upload a transaction CSV file.'}
            
            # Read all transactions
            transactions_df = pd.read_sql_query("""
                SELECT ticker, exchange, transaction_type, quantity, price, fees, trade_date, currency
                FROM transactions 
                ORDER BY trade_date ASC
            """, conn)
            
            conn.close()
            
            if transactions_df.empty:
                return {'holdings': [], 'summary': self._empty_summary(), 'error': 'No transactions found. Please upload a transaction CSV file.'}
            
            # Calculate current positions from transactions
            current_positions = self._calculate_positions_from_transactions(transactions_df)
            
            # Filter out zero positions
            active_positions = {ticker: pos for ticker, pos in current_positions.items() 
                              if pos['quantity'] > 1e-8}
            
            if not active_positions:
                return {'holdings': [], 'summary': self._empty_summary()}
            
            # Calculate portfolio with pricing strategy
            holdings = []
            total_cost_basis = 0
            total_current_value = 0
            market_data = {}
            
            # Only fetch prices if explicitly requested
            if fetch_prices:
                print(f"Fetching prices for {len(active_positions)} holdings...")
                ticker_exchange_map = {ticker: pos['exchange'] for ticker, pos in active_positions.items()}
                
                # Try batch fetch with retries and timeout
                try:
                    market_data = self._fetch_prices_with_retry(ticker_exchange_map, max_retries=50)
                    print(f"✓ Batch market data: {len(market_data)} successful out of {len(ticker_exchange_map)}")
                except Exception as e:
                    print(f"⚠ Batch fetch failed: {e}")
                    market_data = {}
            else:
                print(f"Using cached/fallback pricing for {len(active_positions)} holdings...")
            
            for ticker, position in active_positions.items():
                # Handle price fetch results
                price_error = False
                error_message = None
                
                if ticker in market_data:
                    ticker_data = market_data[ticker]
                    
                    if ticker_data.get('has_error', False):
                        # Price fetch failed - use avg_cost for calculations but mark as error
                        current_price = position['avg_cost']
                        price_error = True
                        error_message = ticker_data.get('error', 'Price fetch failed')
                        print(f"❌ Price error for {ticker}: {error_message} - using avg_cost ${current_price:.2f}")
                        
                    elif ticker_data.get('price', 0) > 0:
                        # Success - valid price
                        current_price = float(ticker_data['price'])
                        print(f"✓ Live price for {ticker}: ${current_price:.2f}")
                        
                    else:
                        # No valid price - use avg_cost but mark as error
                        current_price = position['avg_cost']
                        price_error = True
                        error_message = "No valid price data available"
                        print(f"⚠️  No valid price for {ticker}: using avg_cost ${current_price:.2f}")
                else:
                    # No market data at all - use avg_cost but mark as error if prices were requested
                    current_price = position['avg_cost']
                    if fetch_prices:
                        price_error = True
                        error_message = "No market data available"
                        print(f"⚠️  No data for {ticker}: using avg_cost ${current_price:.2f}")
                
                # Calculate values
                cost_basis = position['total_cost']
                current_value = position['quantity'] * current_price
                total_return = current_value - cost_basis
                return_pct = (total_return / cost_basis * 100) if cost_basis > 0 else 0
                
                holding = {
                    'ticker': ticker,
                    'quantity': position['quantity'],
                    'avg_cost': position['avg_cost'],
                    'cost_basis': cost_basis,
                    'current_price': current_price,
                    'current_value': current_value,
                    'total_return': total_return,
                    'return_percentage': return_pct,
                    'currency': position['currency'],
                    'exchange': position.get('exchange', 'UNKNOWN'),
                    'price_error': price_error,
                    'error_message': error_message
                }
                
                holdings.append(holding)
                total_cost_basis += cost_basis
                total_current_value += current_value
            
            # Sort by current value descending
            holdings.sort(key=lambda x: x['current_value'], reverse=True)
            
            # Calculate portfolio summary
            portfolio_return = total_current_value - total_cost_basis
            portfolio_return_pct = (portfolio_return / total_cost_basis * 100) if total_cost_basis > 0 else 0
            
            summary = {
                'total_cost_basis': round(total_cost_basis, 2),
                'total_current_value': round(total_current_value, 2),
                'total_return': round(portfolio_return, 2),
                'return_percentage': round(portfolio_return_pct, 2),
                'holdings_count': len(holdings),
                'last_updated': datetime.now().isoformat()
            }
            
            return {
                'holdings': holdings,
                'summary': summary,
                'calculation_method': 'transaction_based'
            }
            
        except Exception as e:
            print(f"Error calculating transaction-based portfolio: {e}")
            return {'holdings': [], 'summary': self._empty_summary(), 'error': f'Error calculating portfolio: {str(e)}'}
    
    def _calculate_positions_from_transactions(self, transactions_df):
        """Calculate current positions using FIFO accounting"""
        
        positions = {}
        
        # Group by ticker
        for ticker, group in transactions_df.groupby('ticker'):
            # Sort by date
            group = group.sort_values('trade_date')
            
            # Track lots for FIFO
            lots = []  # [(quantity, cost_per_share)]
            total_fees = 0
            currency = group['currency'].iloc[0] if 'currency' in group.columns else 'USD'
            exchange = group['exchange'].iloc[0] if 'exchange' in group.columns else 'UNKNOWN'
            
            for _, transaction in group.iterrows():
                trans_type = str(transaction['transaction_type']).upper()
                quantity = abs(float(transaction['quantity']))
                price = float(transaction['price'])
                fees = float(transaction.get('fees', 0))
                
                total_fees += fees
                
                if trans_type in ['BUY', 'PURCHASE']:
                    # Add to position
                    cost_per_share = price + (fees / quantity if quantity > 0 else 0)
                    lots.append([quantity, cost_per_share])
                    
                elif trans_type in ['SELL', 'SALE']:
                    # Remove from position using FIFO
                    remaining_to_sell = quantity
                    
                    while remaining_to_sell > 0 and lots:
                        lot_quantity, lot_cost = lots[0]
                        
                        if lot_quantity <= remaining_to_sell:
                            # Sell entire lot
                            remaining_to_sell -= lot_quantity
                            lots.pop(0)
                        else:
                            # Partially sell lot
                            lots[0][0] -= remaining_to_sell
                            remaining_to_sell = 0
            
            # Calculate final position
            total_quantity = sum(lot[0] for lot in lots)
            
            if total_quantity > 1e-8:  # Only include if we have shares
                total_cost = sum(lot[0] * lot[1] for lot in lots)
                avg_cost = total_cost / total_quantity if total_quantity > 0 else 0
                
                positions[ticker] = {
                    'quantity': total_quantity,
                    'total_cost': total_cost,
                    'avg_cost': avg_cost,
                    'currency': currency,
                    'exchange': exchange,
                    'lots': lots
                }
        
        return positions
    
    def _empty_summary(self):
        """Return empty portfolio summary"""
        return {
            'total_cost_basis': 0,
            'total_current_value': 0,
            'total_return': 0,
            'return_percentage': 0,
            'holdings_count': 0,
            'last_updated': datetime.now().isoformat()
        }
    
    def _fetch_prices_with_retry(self, ticker_exchange_map, max_retries=50):
        """Fetch prices with limited retries per ticker"""
        market_data = {}
        failed_tickers = list(ticker_exchange_map.keys())
        
        for retry in range(max_retries):
            if not failed_tickers:
                break
                
            print(f"Price fetch attempt {retry + 1}/{max_retries} for {len(failed_tickers)} tickers")
            
            # Try to fetch remaining failed tickers
            retry_map = {ticker: ticker_exchange_map[ticker] for ticker in failed_tickers}
            
            try:
                batch_result = self.market_service.fetch_batch_quotes_with_exchange(retry_map)
                
                # Check which ones succeeded
                new_failed = []
                for ticker in failed_tickers:
                    if ticker in batch_result:
                        ticker_data = batch_result[ticker]
                        if ticker_data.get('has_error', False):
                            # Price fetch failed - record the error
                            market_data[ticker] = ticker_data
                            print(f"❌ Price error: {ticker} - {ticker_data.get('error', 'Unknown error')}")
                        elif ticker_data.get('price', 0) > 0:
                            # Success - valid price
                            market_data[ticker] = ticker_data
                            print(f"✓ Retry success: {ticker}")
                        else:
                            new_failed.append(ticker)
                    else:
                        new_failed.append(ticker)
                
                failed_tickers = new_failed
                
                # If we got most of them, stop retrying
                if len(failed_tickers) <= len(ticker_exchange_map) * 0.2:  # 80% success rate
                    print(f"Good success rate achieved, stopping retries. Failed: {failed_tickers}")
                    break
                    
            except Exception as e:
                print(f"Retry {retry + 1} failed: {e}")
                
            # Short delay between retries
            if failed_tickers and retry < max_retries - 1:
                import time
                time.sleep(0.5)
        
        if failed_tickers:
            print(f"Final failed tickers after {max_retries} retries: {failed_tickers}")
            
        return market_data