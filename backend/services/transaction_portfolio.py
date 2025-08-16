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
        from services.stable_market_data import StableMarketDataService
        self.market_service = StableMarketDataService()
    
    def load_portfolio_positions_only(self, db_path):
        """STEP 1: Load portfolio positions without any price fetching - cost basis only"""
        try:
            conn = sqlite3.connect(db_path)
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
            
            # Create holdings with ONLY cost basis info (no prices, no returns)
            holdings = []
            total_cost_basis = 0
            
            for ticker, position in active_positions.items():
                cost_basis = position['total_cost']
                
                holding = {
                    'ticker': ticker,
                    'quantity': position['quantity'],
                    'avg_cost': position['avg_cost'],
                    'cost_basis': cost_basis,
                    'currency': position['currency'],
                    'exchange': position.get('exchange', 'UNKNOWN'),
                    # NO price or return data - will be added in step 2
                    'current_price': None,
                    'current_value': None,
                    'total_return': None,
                    'return_percentage': None,
                    'needs_price': True,  # Flag to show this needs price fetching
                    'step': 'positions_loaded'  # Workflow step indicator
                }
                
                holdings.append(holding)
                total_cost_basis += cost_basis
            
            # Sort by cost basis (investment amount) descending
            holdings.sort(key=lambda x: x['cost_basis'], reverse=True)
            
            summary = {
                'total_cost_basis': round(total_cost_basis, 2),
                'total_current_value': None,  # Will be calculated after price fetching
                'total_return': None,         # Will be calculated after price fetching
                'return_percentage': None,    # Will be calculated after price fetching
                'holdings_count': len(holdings),
                'last_updated': datetime.now().isoformat(),
                'workflow_step': 'positions_loaded'  # Workflow indicator
            }
            
            return {
                'holdings': holdings,
                'summary': summary,
                'workflow_step': 'positions_loaded',
                'next_action': 'Fetch live prices to calculate returns'
            }
            
        except Exception as e:
            print(f"Error loading portfolio positions: {e}")
            return {'holdings': [], 'summary': self._empty_summary(), 'error': f'Failed to load positions: {str(e)}'}

    def add_live_prices_to_portfolio(self, db_path):
        """STEP 2: Fetch live prices and add to existing portfolio positions"""
        try:
            # First get the positions (without prices)
            positions_data = self.load_portfolio_positions_only(db_path)
            
            if 'error' in positions_data or not positions_data.get('holdings'):
                return positions_data
            
            holdings = positions_data['holdings']
            tickers = [h['ticker'] for h in holdings]
            
            print(f"STEP 2: Fetching live prices for {len(tickers)} tickers...")
            
            # Get ticker-exchange mapping
            ticker_exchange_map = {h['ticker']: h['exchange'] for h in holdings}
            
            # Fetch live prices using database-first approach
            market_data = self.market_service.fetch_batch_quotes_with_exchange(ticker_exchange_map)
            
            # Update holdings with price data and calculate returns
            total_cost_basis = 0
            total_current_value = 0
            
            for holding in holdings:
                ticker = holding['ticker']
                cost_basis = holding['cost_basis']
                quantity = holding['quantity']
                
                total_cost_basis += cost_basis
                
                # Check if we got price data
                if ticker in market_data:
                    ticker_data = market_data[ticker]
                    
                    if not ticker_data.get('has_error', False) and ticker_data.get('price', 0) > 0:
                        # Success - we have a real price
                        current_price = float(ticker_data['price'])
                        current_value = quantity * current_price
                        total_return = current_value - cost_basis
                        return_pct = (total_return / cost_basis * 100) if cost_basis > 0 else 0
                        
                        # Update holding with price data
                        holding.update({
                            'current_price': current_price,
                            'current_value': current_value,
                            'total_return': total_return,
                            'return_percentage': return_pct,
                            'needs_price': False,
                            'step': 'prices_fetched',
                            'price_source': ticker_data.get('source', 'unknown')
                        })
                        
                        total_current_value += current_value
                        print(f"SUCCESS {ticker}: ${current_price:.2f} (Return: {return_pct:+.1f}%)")
                        
                    else:
                        # Price fetch failed - leave as None
                        holding.update({
                            'step': 'price_fetch_failed',
                            'price_error': ticker_data.get('error', 'Price fetch failed')
                        })
                        print(f"FAILED {ticker}: {ticker_data.get('error', 'Price fetch failed')}")
                else:
                    # No data returned
                    holding.update({
                        'step': 'price_fetch_failed',
                        'price_error': 'No market data available'
                    })
                    print(f"FAILED {ticker}: No market data available")
            
            # Calculate portfolio summary
            portfolio_return = total_current_value - total_cost_basis
            portfolio_return_pct = (portfolio_return / total_cost_basis * 100) if total_cost_basis > 0 else 0
            
            # Count successful vs failed price fetches
            successful_prices = len([h for h in holdings if h.get('current_price') is not None])
            failed_prices = len(holdings) - successful_prices
            
            summary = {
                'total_cost_basis': round(total_cost_basis, 2),
                'total_current_value': round(total_current_value, 2),
                'total_return': round(portfolio_return, 2),
                'return_percentage': round(portfolio_return_pct, 2),
                'holdings_count': len(holdings),
                'successful_prices': successful_prices,
                'failed_prices': failed_prices,
                'last_updated': datetime.now().isoformat(),
                'workflow_step': 'prices_fetched'
            }
            
            next_action = "Set manual prices for failed tickers" if failed_prices > 0 else "Ready for analysis"
            
            return {
                'holdings': holdings,
                'summary': summary,
                'workflow_step': 'prices_fetched',
                'price_fetch_results': {
                    'successful': successful_prices,
                    'failed': failed_prices,
                    'success_rate': f"{successful_prices}/{len(holdings)} ({successful_prices/len(holdings)*100:.1f}%)"
                },
                'next_action': next_action
            }
            
        except Exception as e:
            print(f"Error adding live prices: {e}")
            return {'error': f'Failed to fetch live prices: {str(e)}'}

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
                    print(f"SUCCESS Batch market data: {len(market_data)} successful out of {len(ticker_exchange_map)}")
                except Exception as e:
                    print(f"⚠ Batch fetch failed: {e}")
                    market_data = {}
            else:
                print(f"Using cached/fallback pricing for {len(active_positions)} holdings...")
            
            for ticker, position in active_positions.items():
                # STRICT RULE: Only calculate returns with REAL price data
                # NO automatic fallbacks - user must provide manual prices
                
                current_price = None
                price_error = False
                error_message = None
                
                if ticker in market_data:
                    ticker_data = market_data[ticker]
                    
                    if ticker_data.get('has_error', False):
                        # Price fetch failed - NO FALLBACK, require manual price
                        price_error = True
                        error_message = ticker_data.get('error', 'Price fetch failed')
                        print(f"ERROR PRICE {ticker}: {error_message} - manual price required")
                        
                    elif ticker_data.get('price', 0) > 0:
                        # Success - REAL price data available
                        current_price = float(ticker_data['price'])
                        print(f"REAL PRICE {ticker}: ${current_price:.2f}")
                        
                    else:
                        # No valid price - NO FALLBACK, require manual price
                        price_error = True
                        error_message = "No valid price data available"
                        print(f"NO PRICE {ticker}: {error_message} - manual price required")
                else:
                    # No market data - NO FALLBACK, require manual price
                    price_error = True
                    error_message = "No market data available"
                    print(f"NO DATA {ticker}: {error_message} - manual price required")
                
                # Only calculate returns when we have REAL price data
                if current_price is not None and current_price > 0:
                    # Calculate with real price
                    cost_basis = position['total_cost']
                    current_value = position['quantity'] * current_price
                    total_return = current_value - cost_basis
                    return_pct = (total_return / cost_basis * 100) if cost_basis > 0 else 0
                else:
                    # NO REAL PRICE = NO CALCULATION
                    # Show user they need to set manual price
                    cost_basis = position['total_cost']
                    current_value = None  # Cannot calculate without real price
                    total_return = None   # Cannot calculate without real price
                    return_pct = None     # Cannot calculate without real price
                
                holding = {
                    'ticker': ticker,
                    'quantity': position['quantity'],
                    'avg_cost': position['avg_cost'],
                    'cost_basis': cost_basis,
                    'current_price': current_price,  # Can be None
                    'current_value': current_value,  # Can be None
                    'total_return': total_return,    # Can be None
                    'return_percentage': return_pct, # Can be None
                    'currency': position['currency'],
                    'exchange': position.get('exchange', 'UNKNOWN'),
                    'price_error': price_error,
                    'error_message': error_message,
                    'needs_manual_price': price_error  # Flag to show manual price button
                }
                
                holdings.append(holding)
                total_cost_basis += cost_basis
                
                # Only add to total if we have real price data
                if current_value is not None:
                    total_current_value += current_value
            
            # Sort by current value descending (handle None values)
            holdings.sort(key=lambda x: x['current_value'] or 0, reverse=True)
            
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
                            print(f"ERROR Price error: {ticker} - {ticker_data.get('error', 'Unknown error')}")
                        elif ticker_data.get('price', 0) > 0:
                            # Success - valid price
                            market_data[ticker] = ticker_data
                            print(f"SUCCESS Retry success: {ticker}")
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