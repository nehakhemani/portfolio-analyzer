#!/usr/bin/env python3
"""
Portfolio Upload & Analysis Workflow Service
Complete pipeline from CSV upload to statistical analysis
"""

import pandas as pd
import sqlite3
import time
from datetime import datetime
from typing import Dict, List, Set, Tuple
from services.stable_market_data import StableMarketDataService

class PortfolioWorkflowService:
    """Complete workflow: CSV -> Tickers -> Prices -> Analysis"""
    
    def __init__(self, db_path='data/portfolio.db'):
        self.db_path = db_path
        self.market_service = StableMarketDataService(db_path)
    
    def process_csv_upload(self, csv_content: str, fetch_prices: bool = False) -> Dict:
        """
        STEP 1-6: Complete CSV processing workflow
        1. Upload CSV transactions
        2. Extract unique tickers
        3. Add tickers to DB
        4. Optionally fetch prices (can be done later to avoid timeouts)
        5. Calculate returns where possible
        6. Return analysis-ready data
        """
        try:
            print("=== PORTFOLIO WORKFLOW STARTED ===")
            
            # Step 1: Parse and validate CSV
            result = self._step1_parse_csv(csv_content)
            if 'error' in result:
                return result
                
            transactions_df = result['transactions_df']
            print(f"STEP 1 COMPLETE: {len(transactions_df)} transactions parsed")
            
            # Step 2: Extract unique tickers
            unique_tickers = self._step2_extract_tickers(transactions_df)
            print(f"STEP 2 COMPLETE: {len(unique_tickers)} unique tickers found")
            print(f"Tickers: {', '.join(sorted(unique_tickers))}")
            
            # Step 3: Store transactions in database
            stored_count = self._step3_store_transactions(transactions_df)
            print(f"STEP 3 COMPLETE: {stored_count} transactions stored in database")
            
            # Step 4: Optionally fetch prices (can be skipped for fast upload)
            if fetch_prices:
                price_results = self._step4_fetch_prices_with_delays(unique_tickers)
                successful_prices = price_results['successful']
                failed_tickers = price_results['failed']
                print(f"STEP 4 COMPLETE: {len(successful_prices)}/{len(unique_tickers)} prices fetched")
            else:
                # Skip price fetching for fast upload - can be done later
                successful_prices = {}
                failed_tickers = list(unique_tickers)
                print(f"STEP 4 SKIPPED: Price fetching can be done separately via 'Sync Prices' button")
            
            # Step 5: Calculate returns and identify manual entry needs
            portfolio_analysis = self._step5_calculate_smart_returns()
            print(f"STEP 5 COMPLETE: Portfolio analysis ready")
            
            # Step 6: Prepare for statistical analysis
            analysis_summary = self._step6_prepare_analysis_data(portfolio_analysis, successful_prices, failed_tickers)
            print(f"STEP 6 COMPLETE: Ready for statistical analysis")
            
            print("=== PORTFOLIO WORKFLOW COMPLETED ===")
            
            return {
                'success': True,
                'workflow_complete': True,
                'steps_completed': 6,
                'summary': {
                    'transactions_processed': stored_count,
                    'unique_tickers': len(unique_tickers),
                    'prices_fetched': len(successful_prices),
                    'manual_entry_needed': len(failed_tickers),
                    'ready_for_analysis': True
                },
                'portfolio_data': portfolio_analysis,
                'price_status': {
                    'successful_tickers': list(successful_prices.keys()),
                    'failed_tickers': failed_tickers,
                    'success_rate': f"{len(successful_prices)}/{len(unique_tickers)} ({len(successful_prices)/len(unique_tickers)*100:.1f}%)"
                },
                'analysis_data': analysis_summary,
                'next_steps': {
                    'manual_prices_needed': failed_tickers,
                    'statistical_analysis_ready': len(successful_prices) > 0,
                    'recommendation': "Set manual prices for failed tickers, then proceed with statistical analysis"
                }
            }
            
        except Exception as e:
            print(f"WORKFLOW ERROR: {e}")
            return {
                'success': False,
                'error': f'Workflow failed: {str(e)}',
                'step_failed': 'unknown'
            }
    
    def _step1_parse_csv(self, csv_content: str) -> Dict:
        """Step 1: Parse and validate CSV transactions"""
        try:
            import io
            df = pd.read_csv(io.StringIO(csv_content))
            
            # Check required columns
            required_columns = ['Trade date', 'Instrument code', 'Transaction type', 'Quantity', 'Price']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                return {
                    'error': f'Missing required columns: {missing_columns}. Required: {required_columns}',
                    'step_failed': 'step1_validation'
                }
            
            return {'transactions_df': df}
            
        except Exception as e:
            return {
                'error': f'CSV parsing failed: {str(e)}',
                'step_failed': 'step1_parsing'
            }
    
    def _step2_extract_tickers(self, transactions_df: pd.DataFrame) -> Set[str]:
        """Step 2: Extract unique tickers from transactions"""
        # Get unique instrument codes (tickers)
        tickers = set()
        for ticker in transactions_df['Instrument code'].dropna().unique():
            ticker_clean = str(ticker).strip().upper()
            if ticker_clean and ticker_clean != 'NAN':
                tickers.add(ticker_clean)
        
        return tickers
    
    def _step3_store_transactions(self, transactions_df: pd.DataFrame) -> int:
        """Step 3: Store transactions in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Clear existing transactions
        cursor.execute("DELETE FROM transactions")
        cursor.execute("DELETE FROM holdings")  # Clear old holdings too
        
        # Clean up dates
        transactions_df['Trade date'] = transactions_df['Trade date'].astype(str).str.replace(r'\s+\(UTC\)', '', regex=True)
        transactions_df['Trade date'] = pd.to_datetime(transactions_df['Trade date'], errors='coerce')
        transactions_df['Trade date'] = transactions_df['Trade date'].dt.strftime('%Y-%m-%d %H:%M:%S').fillna('1970-01-01 00:00:00')
        
        stored_count = 0
        for _, transaction in transactions_df.iterrows():
            try:
                cursor.execute('''
                    INSERT INTO transactions 
                    (ticker, exchange, currency, transaction_type, quantity, price, amount, fees, trade_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    str(transaction.get('Instrument code', '')).upper(),
                    str(transaction.get('Market code', 'NASDAQ')),
                    str(transaction.get('Currency', 'USD')).lower(),
                    str(transaction.get('Transaction type', '')).upper(),
                    float(transaction.get('Quantity', 0)),
                    float(transaction.get('Price', 0)),
                    float(transaction.get('Amount', 0)),
                    float(transaction.get('Transaction fee', 0)),
                    transaction.get('Trade date')
                ))
                stored_count += 1
            except Exception as e:
                print(f"Failed to store transaction: {e}")
                continue
        
        conn.commit()
        conn.close()
        return stored_count
    
    def _step4_fetch_prices_with_delays(self, tickers: Set[str]) -> Dict:
        """Step 4: Fetch prices with proper rate limiting and delays"""
        print(f"Starting price fetch for {len(tickers)} tickers with delays...")
        
        successful_prices = {}
        failed_tickers = []
        
        ticker_list = list(tickers)
        
        # Process in small batches with delays
        batch_size = 3  # Small batches to avoid rate limiting
        delay_between_batches = 5  # 5 seconds between batches
        delay_between_tickers = 2  # 2 seconds between individual tickers
        
        for i in range(0, len(ticker_list), batch_size):
            batch = ticker_list[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(ticker_list) + batch_size - 1) // batch_size
            
            print(f"Processing batch {batch_num}/{total_batches}: {', '.join(batch)}")
            
            for ticker in batch:
                try:
                    print(f"  Fetching {ticker}...")
                    
                    # Use background sync method (no Unicode characters)
                    result = self.market_service.sync_prices_background([ticker])
                    
                    if ticker in result and not result[ticker].get('has_error', True):
                        price = result[ticker].get('price', 0)
                        if price and price > 0:
                            successful_prices[ticker] = price
                            print(f"  SUCCESS {ticker}: ${price:.2f}")
                        else:
                            failed_tickers.append(ticker)
                            print(f"  FAILED {ticker}: No valid price data")
                    else:
                        failed_tickers.append(ticker)
                        error_msg = result.get(ticker, {}).get('error_message', 'Unknown error')
                        print(f"  FAILED {ticker}: {error_msg}")
                    
                    # Delay between individual tickers
                    if ticker != batch[-1]:  # No delay after last ticker in batch
                        time.sleep(delay_between_tickers)
                        
                except Exception as e:
                    failed_tickers.append(ticker)
                    print(f"  ERROR {ticker}: {str(e)}")
            
            # Delay between batches
            if batch_num < total_batches:
                print(f"  Waiting {delay_between_batches} seconds before next batch...")
                time.sleep(delay_between_batches)
        
        return {
            'successful': successful_prices,
            'failed': failed_tickers
        }
    
    def _step5_calculate_smart_returns(self) -> Dict:
        """Step 5: Calculate returns where prices available, show errors where not"""
        from services.transaction_portfolio import TransactionPortfolioService
        
        portfolio_service = TransactionPortfolioService()
        
        # Calculate portfolio using database-first approach (don't fetch new prices)
        portfolio_data = portfolio_service.calculate_portfolio_from_transactions(
            self.db_path, 
            fetch_prices=False  # Use database prices we just fetched
        )
        
        return portfolio_data
    
    def _step6_prepare_analysis_data(self, portfolio_data: Dict, successful_prices: Dict, failed_tickers: List[str]) -> Dict:
        """Step 6: Prepare data for statistical analysis"""
        
        holdings_with_prices = []
        holdings_needing_manual = []
        
        for holding in portfolio_data.get('holdings', []):
            ticker = holding['ticker']
            
            if holding.get('current_price') is not None and holding.get('current_value') is not None:
                # Has valid price and return data
                holdings_with_prices.append({
                    'ticker': ticker,
                    'quantity': holding['quantity'],
                    'cost_basis': holding['cost_basis'],
                    'current_value': holding['current_value'],
                    'total_return': holding['total_return'],
                    'return_percentage': holding['return_percentage'],
                    'current_price': holding['current_price']
                })
            else:
                # Needs manual price entry
                holdings_needing_manual.append({
                    'ticker': ticker,
                    'quantity': holding['quantity'],
                    'cost_basis': holding['cost_basis'],
                    'avg_cost': holding['avg_cost'],
                    'needs_manual_price': True
                })
        
        return {
            'holdings_ready_for_analysis': holdings_with_prices,
            'holdings_needing_manual_prices': holdings_needing_manual,
            'analysis_readiness': {
                'total_holdings': len(portfolio_data.get('holdings', [])),
                'with_prices': len(holdings_with_prices),
                'needing_manual': len(holdings_needing_manual),
                'analysis_possible': len(holdings_with_prices) > 0,
                'completion_percentage': f"{len(holdings_with_prices) / len(portfolio_data.get('holdings', [1])) * 100:.1f}%" if portfolio_data.get('holdings') else "0%"
            },
            'statistical_analysis_ready': len(holdings_with_prices) >= 3,  # Need at least 3 holdings for meaningful analysis
            'next_action': "Set manual prices for missing tickers" if holdings_needing_manual else "Proceed to statistical analysis"
        }