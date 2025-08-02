import pandas as pd
import io
from datetime import datetime

class CSVParser:
    def detect_and_parse_csv(self, file):
        """Detect CSV format and use appropriate parser"""
        try:
            # Read first few lines to detect format
            file.seek(0)  # Reset file pointer
            content = file.read().decode('utf-8')
            file.seek(0)  # Reset again for actual parsing
            
            # Check if it contains transaction columns
            transaction_indicators = ['Trade date', 'Instrument code', 'Transaction type', 'Quantity']
            portfolio_indicators = ['Investment ticker symbol', 'Starting investment', 'Ending investment']
            
            transaction_score = sum(1 for indicator in transaction_indicators if indicator in content)
            portfolio_score = sum(1 for indicator in portfolio_indicators if indicator in content)
            
            print(f"Transaction indicators found: {transaction_score}")
            print(f"Portfolio indicators found: {portfolio_score}")
            
            if transaction_score >= 3:
                print("Detected transaction format CSV")
                return self.parse_transaction_csv(file)
            else:
                print("Detected portfolio format CSV")
                return self.parse_portfolio_csv(file)
                
        except Exception as e:
            print(f"Error detecting CSV format: {e}")
            # Default to portfolio format
            file.seek(0)
            return self.parse_portfolio_csv(file)

    def parse_portfolio_csv(self, file):
        """Parse portfolio CSV file"""
        try:
            print("Starting CSV parsing...")
            
            # Read CSV content
            content = file.read().decode('utf-8')
            print(f"CSV content length: {len(content)} characters")
            
            # Read CSV
            df = pd.read_csv(io.StringIO(content))
            print(f"CSV loaded with {len(df)} rows and columns: {list(df.columns)}")
            
            # Map columns to standard names
            column_mapping = {
                'Investment ticker symbol': 'ticker',
                'Exchange': 'exchange', 
                'Currency': 'currency',
                'Starting investment dollar value': 'start_value',
                'Ending investment dollar value': 'end_value',
                'Starting share price': 'start_price',
                'Ending share price': 'end_price',
                'Dividends and distributions': 'dividends',
                'Transaction fees': 'fees'
            }
            
            print("Available columns:", list(df.columns))
            print("Expected columns:", list(column_mapping.keys()))
            
            # Check for missing columns
            missing_columns = []
            for expected_col in column_mapping.keys():
                if expected_col not in df.columns:
                    missing_columns.append(expected_col)
            
            if missing_columns:
                print(f"Missing columns: {missing_columns}")
                # Try flexible column matching
                flexible_mapping = self._create_flexible_mapping(df.columns)
                if flexible_mapping:
                    print(f"Using flexible mapping: {flexible_mapping}")
                    df = df.rename(columns=flexible_mapping)
                else:
                    raise ValueError(f"Missing required columns: {missing_columns}")
            else:
                # Rename columns
                df = df.rename(columns=column_mapping)
            
            # Fill missing values with defaults
            required_columns = ['ticker', 'exchange', 'currency', 'start_value', 'end_value', 
                              'start_price', 'end_price', 'dividends', 'fees']
            
            for col in required_columns:
                if col not in df.columns:
                    if col == 'exchange':
                        df[col] = 'NASDAQ'
                    elif col == 'currency':
                        df[col] = 'USD'
                    else:
                        df[col] = 0
            
            # Select only needed columns
            df = df[required_columns]
            
            # Clean data
            df = df.fillna(0)
            
            # Convert to list of dicts
            result = df.to_dict('records')
            print(f"Successfully parsed {len(result)} holdings")
            
            return result
            
        except Exception as e:
            print(f"Error parsing CSV: {e}")
            raise e
    
    def _create_flexible_mapping(self, columns):
        """Create flexible column mapping for different CSV formats"""
        flexible_mapping = {}
        
        for col in columns:
            col_lower = col.lower().strip()
            
            if 'ticker' in col_lower or 'symbol' in col_lower:
                flexible_mapping[col] = 'ticker'
            elif 'exchange' in col_lower:
                flexible_mapping[col] = 'exchange'
            elif 'currency' in col_lower:
                flexible_mapping[col] = 'currency'
            elif 'starting' in col_lower and ('value' in col_lower or 'investment' in col_lower):
                flexible_mapping[col] = 'start_value'
            elif 'ending' in col_lower and ('value' in col_lower or 'investment' in col_lower):
                flexible_mapping[col] = 'end_value'
            elif 'starting' in col_lower and 'price' in col_lower:
                flexible_mapping[col] = 'start_price'
            elif 'ending' in col_lower and 'price' in col_lower:
                flexible_mapping[col] = 'end_price'
            elif 'dividend' in col_lower:
                flexible_mapping[col] = 'dividends'
            elif 'fee' in col_lower:
                flexible_mapping[col] = 'fees'
        
        return flexible_mapping if len(flexible_mapping) >= 3 else None

    def parse_transaction_csv(self, file):
        """Parse transaction CSV file with columns: Trade date, Instrument code, Market code, Quantity, Price, Transaction type, Currency, Amount, Transaction fee, Transaction method"""
        try:
            print("Starting transaction CSV parsing...")
            
            # Read CSV content
            content = file.read().decode('utf-8')
            print(f"CSV content length: {len(content)} characters")
            
            # Read CSV
            df = pd.read_csv(io.StringIO(content))
            print(f"CSV loaded with {len(df)} rows and columns: {list(df.columns)}")
            
            # Expected transaction columns mapping
            transaction_column_mapping = {
                'Trade date': 'trade_date',
                'Instrument code': 'ticker',
                'Market code': 'exchange',
                'Quantity': 'quantity',
                'Price': 'price',
                'Transaction type': 'transaction_type',
                'Currency': 'currency',
                'Amount': 'amount',
                'Transaction fee': 'fees',
                'Transaction method': 'transaction_method'
            }
            
            print("Available columns:", list(df.columns))
            print("Expected columns:", list(transaction_column_mapping.keys()))
            
            # Check for missing columns and try flexible matching
            missing_columns = []
            for expected_col in transaction_column_mapping.keys():
                if expected_col not in df.columns:
                    missing_columns.append(expected_col)
            
            if missing_columns:
                print(f"Missing columns: {missing_columns}")
                # Try flexible column matching for transactions
                flexible_mapping = self._create_flexible_transaction_mapping(df.columns)
                if flexible_mapping:
                    print(f"Using flexible mapping: {flexible_mapping}")
                    df = df.rename(columns=flexible_mapping)
                else:
                    raise ValueError(f"Missing required transaction columns: {missing_columns}")
            else:
                # Rename columns
                df = df.rename(columns=transaction_column_mapping)
            
            # Clean and process transaction data
            df = df.fillna(0)
            
            # Convert trade_date to datetime if it exists
            if 'trade_date' in df.columns:
                df['trade_date'] = pd.to_datetime(df['trade_date'], errors='coerce')
            
            # Process transactions to create portfolio holdings
            holdings = self._aggregate_transactions_to_holdings(df)
            
            print(f"Successfully processed {len(df)} transactions into {len(holdings)} holdings")
            return holdings
            
        except Exception as e:
            print(f"Error parsing transaction CSV: {e}")
            raise e
    
    def _create_flexible_transaction_mapping(self, columns):
        """Create flexible column mapping for transaction CSV formats"""
        flexible_mapping = {}
        
        for col in columns:
            col_lower = col.lower().strip()
            
            if 'date' in col_lower and ('trade' in col_lower or 'transaction' in col_lower):
                flexible_mapping[col] = 'trade_date'
            elif 'instrument' in col_lower or 'symbol' in col_lower or 'ticker' in col_lower:
                flexible_mapping[col] = 'ticker'
            elif 'market' in col_lower or 'exchange' in col_lower:
                flexible_mapping[col] = 'exchange'
            elif 'quantity' in col_lower or 'shares' in col_lower:
                flexible_mapping[col] = 'quantity'
            elif 'price' in col_lower and 'transaction' not in col_lower:
                flexible_mapping[col] = 'price'
            elif 'type' in col_lower and 'transaction' in col_lower:
                flexible_mapping[col] = 'transaction_type'
            elif 'currency' in col_lower:
                flexible_mapping[col] = 'currency'
            elif 'amount' in col_lower and 'fee' not in col_lower:
                flexible_mapping[col] = 'amount'
            elif 'fee' in col_lower or ('transaction' in col_lower and 'fee' in col_lower):
                flexible_mapping[col] = 'fees'
            elif 'method' in col_lower and 'transaction' in col_lower:
                flexible_mapping[col] = 'transaction_method'
        
        return flexible_mapping if len(flexible_mapping) >= 5 else None
    
    def _aggregate_transactions_to_holdings(self, transactions_df):
        """Aggregate transaction data into portfolio holdings format with proper cost basis calculation"""
        holdings = []
        
        # Group by ticker and currency
        grouped = transactions_df.groupby(['ticker', 'currency'])
        
        for (ticker, currency), group in grouped:
            # Sort by date if available
            if 'trade_date' in group.columns:
                group = group.sort_values('trade_date')
            
            # Track position with FIFO cost basis
            position_tracker = CSVParser._PositionTracker()
            total_dividends = 0
            total_fees = 0
            exchange = group['exchange'].iloc[0] if 'exchange' in group.columns else 'UNKNOWN'
            
            for _, transaction in group.iterrows():
                trans_type = str(transaction.get('transaction_type', '')).upper()
                quantity = abs(float(transaction.get('quantity', 0)))
                price = float(transaction.get('price', 0))
                amount = abs(float(transaction.get('amount', 0)))
                fees = float(transaction.get('fees', 0))
                
                # Handle different transaction types
                if trans_type in ['BUY', 'PURCHASE', 'B']:
                    # Add to position
                    cost_per_share = amount / quantity if quantity > 0 else price
                    position_tracker.add_purchase(quantity, cost_per_share, fees)
                    
                elif trans_type in ['SELL', 'SALE', 'S']:
                    # Remove from position using FIFO
                    position_tracker.sell_shares(quantity, price, fees)
                    
                elif trans_type in ['DIVIDEND', 'DIV', 'DISTRIBUTION']:
                    total_dividends += amount
                
                total_fees += fees
            
            # Only create holding if we have a positive position
            current_position = position_tracker.get_current_position()
            if current_position['quantity'] > 0:
                # Get current market price - use the last transaction price as proxy
                # In a real system, you'd fetch this from market data
                last_market_price = None
                for _, transaction in group.tail(5).iterrows():  # Look at last few transactions
                    trans_type = str(transaction.get('transaction_type', '')).upper()
                    if trans_type in ['BUY', 'PURCHASE', 'B', 'SELL', 'SALE', 'S']:
                        last_market_price = float(transaction.get('price', 0))
                
                if last_market_price is None:
                    last_market_price = current_position['avg_cost']
                
                current_value = current_position['quantity'] * last_market_price
                total_cost_basis = current_position['total_cost']
                
                holding = {
                    'ticker': ticker.upper(),
                    'exchange': exchange,
                    'currency': currency,
                    'start_value': total_cost_basis,  # Actual cost basis
                    'end_value': current_value,      # Current market value
                    'start_price': current_position['avg_cost'],  # Average cost per share
                    'end_price': last_market_price,  # Current price per share
                    'dividends': total_dividends,
                    'fees': total_fees,
                    # Additional transaction-based metrics
                    'quantity': current_position['quantity'],
                    'avg_cost_basis': current_position['avg_cost'],
                    'total_return': current_value - total_cost_basis + total_dividends,
                    'return_percentage': ((current_value - total_cost_basis + total_dividends) / total_cost_basis * 100) if total_cost_basis > 0 else 0,
                    'unrealized_gain_loss': current_value - total_cost_basis,
                    'realized_gain_loss': position_tracker.realized_gains
                }
                
                holdings.append(holding)
                print(f"Created holding for {ticker}: {current_position['quantity']:.0f} shares @ avg ${current_position['avg_cost']:.2f}")
                print(f"  Cost basis: ${total_cost_basis:.2f}, Current value: ${current_value:.2f}")
                print(f"  Total return: ${holding['total_return']:.2f} ({holding['return_percentage']:.1f}%)")
        
        return holdings
    
    class _PositionTracker:
        """Helper class to track positions with FIFO cost basis"""
        
        def __init__(self):
            self.lots = []  # List of (quantity, cost_per_share, fees) tuples
            self.realized_gains = 0
            
        def add_purchase(self, quantity, cost_per_share, fees):
            """Add a purchase to the position"""
            fees_per_share = fees / quantity if quantity > 0 else 0
            adjusted_cost = cost_per_share + fees_per_share
            self.lots.append([quantity, adjusted_cost])
            
        def sell_shares(self, sell_quantity, sell_price, fees):
            """Sell shares using FIFO method"""
            remaining_to_sell = sell_quantity
            fees_per_share = fees / sell_quantity if sell_quantity > 0 else 0
            net_sell_price = sell_price - fees_per_share
            
            while remaining_to_sell > 0 and self.lots:
                lot_quantity, lot_cost = self.lots[0]
                
                if lot_quantity <= remaining_to_sell:
                    # Sell entire lot
                    gain_loss = (net_sell_price - lot_cost) * lot_quantity
                    self.realized_gains += gain_loss
                    remaining_to_sell -= lot_quantity
                    self.lots.pop(0)
                else:
                    # Partially sell lot
                    gain_loss = (net_sell_price - lot_cost) * remaining_to_sell
                    self.realized_gains += gain_loss
                    self.lots[0][0] -= remaining_to_sell
                    remaining_to_sell = 0
                    
        def get_current_position(self):
            """Get current position summary"""
            total_quantity = sum(lot[0] for lot in self.lots)
            if total_quantity == 0:
                return {'quantity': 0, 'total_cost': 0, 'avg_cost': 0}
                
            total_cost = sum(lot[0] * lot[1] for lot in self.lots)
            avg_cost = total_cost / total_quantity
            
            return {
                'quantity': total_quantity,
                'total_cost': total_cost,
                'avg_cost': avg_cost
            }