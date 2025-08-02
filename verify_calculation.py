#!/usr/bin/env python3
"""
Portfolio Return Calculation Verification Tool
Run this to manually verify your portfolio return calculation
"""

import sqlite3
import pandas as pd
import sys
import os

# Add the backend directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from services.currency_converter import CurrencyConverter

def verify_portfolio_return():
    """Verify portfolio return calculation step by step"""
    
    # Connect to database
    db_path = os.path.join('backend', 'data', 'portfolio.db')
    if not os.path.exists(db_path):
        # Try alternative path
        db_path = os.path.join('data', 'portfolio.db')
        if not os.path.exists(db_path):
            print("ERROR: Database not found. Make sure you have portfolio data.")
            print(f"Looking for: {os.path.abspath(db_path)}")
            return
    
    conn = sqlite3.connect(db_path)
    
    # Get holdings (same query as the app)
    holdings_df = pd.read_sql_query(
        "SELECT * FROM holdings WHERE end_value > 0 ORDER BY end_value DESC", 
        conn
    )
    conn.close()
    
    if holdings_df.empty:
        print("ERROR: No holdings found in database")
        return
    
    print("PORTFOLIO RETURN CALCULATION VERIFICATION")
    print("=" * 50)
    
    # Initialize currency converter
    currency_converter = CurrencyConverter()
    
    total_start_usd = 0
    total_end_usd = 0
    
    print(f"Found {len(holdings_df)} holdings:")
    print()
    
    for i, holding in holdings_df.iterrows():
        ticker = holding['ticker']
        currency = holding.get('currency', 'USD')
        start_value = holding['start_value']
        end_value = holding['end_value']
        
        # Convert to USD
        if currency != 'USD':
            start_usd = currency_converter.convert_to_usd(start_value, currency)
            end_usd = currency_converter.convert_to_usd(end_value, currency)
            conversion_rate = currency_converter.convert(1, currency, 'USD')['exchange_rate']
        else:
            start_usd = start_value
            end_usd = end_value
            conversion_rate = 1.0
        
        # Individual return
        individual_return = ((end_value - start_value) / start_value * 100) if start_value > 0 else 0
        individual_return_usd = ((end_usd - start_usd) / start_usd * 100) if start_usd > 0 else 0
        
        print(f"  {ticker}:")
        print(f"    Original: {currency}{start_value:,.2f} -> {currency}{end_value:,.2f}")
        if currency != 'USD':
            print(f"    USD (rate: {conversion_rate:.4f}): ${start_usd:,.2f} -> ${end_usd:,.2f}")
        print(f"    Individual Return: {individual_return:.2f}% ({currency}) / {individual_return_usd:.2f}% (USD)")
        print()
        
        total_start_usd += start_usd
        total_end_usd += end_usd
    
    # Portfolio calculation
    total_return_usd = total_end_usd - total_start_usd
    portfolio_return_pct = (total_return_usd / total_start_usd * 100) if total_start_usd > 0 else 0
    
    print("PORTFOLIO TOTALS:")
    print(f"  Total Initial Investment (USD): ${total_start_usd:,.2f}")
    print(f"  Total Current Value (USD): ${total_end_usd:,.2f}")
    print(f"  Total Return (USD): ${total_return_usd:,.2f}")
    print(f"  Portfolio Return: {portfolio_return_pct:.2f}%")
    print()
    
    print("MANUAL VERIFICATION:")
    print(f"  Formula: ({total_end_usd:,.2f} - {total_start_usd:,.2f}) / {total_start_usd:,.2f} * 100")
    print(f"  Result: {total_return_usd:,.2f} / {total_start_usd:,.2f} * 100 = {portfolio_return_pct:.2f}%")
    
    # Check if this matches the displayed 32.48%
    if abs(portfolio_return_pct - 32.48) < 0.01:
        print("RESULT: The 32.48% calculation appears to be CORRECT!")
    else:
        print(f"WARNING: Expected 32.48% but calculated {portfolio_return_pct:.2f}%")
        print("   There might be a discrepancy in the calculation.")

if __name__ == "__main__":
    verify_portfolio_return()