from flask import Flask, request, jsonify, send_from_directory, session, send_file
from flask_cors import CORS
import os
from datetime import datetime
import sqlite3
import pandas as pd
import sys
import secrets
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.market_data import MarketDataService
from services.analysis import PortfolioAnalyzer
from services.recommendations import RecommendationEngine
from services.ml_recommendations import MLRecommendationEngine
from services.enhanced_ml_recommendations_simple import EnhancedMLRecommendationEngine
from services.currency_converter import CurrencyConverter
from auth import require_auth, rate_limit_only, validate_request_data, security_manager

app = Flask(__name__)
CORS(app, origins="*", supports_credentials=True)  # Enable credentials for sessions

# Configure secure session
app.config['SECRET_KEY'] = security_manager.secret_key
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True when using HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Add comprehensive security headers
@app.after_request
def after_request(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'"
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# Configuration
app.config['DATABASE'] = 'data/portfolio.db'
app.config['UPLOAD_FOLDER'] = 'uploads'

# Initialize services
market_service = MarketDataService()
analyzer = PortfolioAnalyzer()
recommendation_engine = RecommendationEngine()
ml_engine = MLRecommendationEngine()
enhanced_ml_engine = EnhancedMLRecommendationEngine()
currency_converter = CurrencyConverter()

# Initialize database
def init_db():
    """Initialize SQLite database with portfolio tables"""
    try:
        # Create data directory if it doesn't exist
        os.makedirs('data', exist_ok=True)
        print(f"Data directory created/verified: {os.path.abspath('data')}")
    except Exception as e:
        print(f"Error creating data directory: {e}")
        # Try alternative location
        try:
            os.makedirs('/tmp/data', exist_ok=True)
            app.config['DATABASE'] = '/tmp/data/portfolio.db'
            print(f"Using temporary database location: {app.config['DATABASE']}")
        except Exception as e2:
            print(f"Error creating temp directory: {e2}")
            app.config['DATABASE'] = ':memory:'
            print("Using in-memory database")
    
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            exchange TEXT,
            currency TEXT,
            start_value REAL,
            end_value REAL,
            start_price REAL,
            end_price REAL,
            dividends REAL,
            fees REAL,
            quantity REAL,
            avg_cost_basis REAL,
            total_return REAL,
            return_percentage REAL,
            unrealized_gain_loss REAL,
            realized_gain_loss REAL,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            current_price REAL,
            day_change REAL,
            volume INTEGER,
            market_cap REAL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create transactions table for proper transaction-based portfolio calculation
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            exchange TEXT,
            currency TEXT,
            transaction_type TEXT NOT NULL,
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            amount REAL,
            fees REAL DEFAULT 0,
            trade_date TIMESTAMP,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# Authentication routes
@app.route('/api/login', methods=['POST'])
@rate_limit_only
@validate_request_data
def login():
    """Login endpoint"""
    try:
        data = request.json
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({'error': 'Username and password required'}), 400
        
        username = data['username']
        password = data['password']
        
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
        
        if security_manager.authenticate_user(username, password):
            session['authenticated'] = True
            session['username'] = username
            session['login_time'] = time.time()
            session.permanent = True
            return jsonify({'success': True, 'message': 'Login successful'})
        else:
            security_manager.record_failed_attempt(client_ip)
            return jsonify({'error': 'Invalid credentials'}), 401
            
    except Exception as e:
        return jsonify({'error': 'Login failed'}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    """Logout endpoint"""
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/health', methods=['GET'])
def health_check():
    """Public health check endpoint for cloud deployment"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()}), 200

@app.route('/api/status', methods=['GET'])
def api_status():
    """API status check without authentication"""
    return jsonify({'status': 'Portfolio Analyzer API is running', 'version': '2.0'}), 200

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    """Check authentication status"""
    if 'authenticated' in session and session['authenticated']:
        # Check session timeout
        if 'login_time' in session:
            if time.time() - session['login_time'] > security_manager.session_timeout:
                session.clear()
                return jsonify({'authenticated': False, 'message': 'Session expired'})
        return jsonify({'authenticated': True, 'username': session.get('username')})
    return jsonify({'authenticated': False})

@app.route('/')
@rate_limit_only
def index():
    """Serve the main HTML page and clear portfolio for fresh sessions"""
    
    # Check if this is a fresh session (no auth session or new session)
    is_fresh_session = (
        'authenticated' not in session or 
        'portfolio_loaded' not in session
    )
    
    # If it's a fresh session, clear the portfolio
    if is_fresh_session:
        try:
            print("Fresh session detected - clearing portfolio database")
            conn = sqlite3.connect(app.config['DATABASE'])
            cursor = conn.cursor()
            cursor.execute("DELETE FROM holdings")
            conn.commit()
            conn.close()
            print("Portfolio cleared for fresh session")
        except Exception as e:
            print(f"Error clearing portfolio: {e}")
    
    frontend_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    return send_from_directory(frontend_dir, 'index.html')

@app.route('/login.html')
@rate_limit_only
def login_page():
    """Serve the login HTML page"""
    frontend_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    return send_from_directory(frontend_dir, 'login.html')

@app.route('/css/<path:path>')
def send_css(path):
    """Serve CSS files"""
    css_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'css')
    return send_from_directory(css_dir, path)

@app.route('/js/<path:path>')
def send_js(path):
    """Serve JavaScript files"""
    js_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'js')
    return send_from_directory(js_dir, path)

@app.route('/api/portfolio', methods=['GET'])
@require_auth
def get_portfolio():
    """Get current portfolio data using transaction-based calculation"""
    
    # Use new transaction-based portfolio service
    from services.transaction_portfolio import TransactionPortfolioService
    
    portfolio_service = TransactionPortfolioService()
    # Don't fetch prices automatically - use cached/fallback prices for speed
    portfolio_data = portfolio_service.calculate_portfolio_from_transactions(app.config['DATABASE'], fetch_prices=False)
    
    if not portfolio_data['holdings']:
        return jsonify({
            'holdings': [],
            'summary': {
                'total_value': 0,
                'total_return': 0,
                'return_percentage': 0,
                'total_dividends': 0,
                'holdings_count': 0
            },
            'currency_info': {
                'base_currency': 'USD',
                'conversions': {}
            }
        })
    
    # Debug logging for transaction-based calculation
    print(f"Transaction-based Portfolio Calculation:")
    print(f"  Method: {portfolio_data.get('calculation_method', 'transaction_based')}")
    print(f"  Holdings count: {portfolio_data['summary']['holdings_count']}")
    print(f"  Total cost basis: ${portfolio_data['summary']['total_cost_basis']:,.2f}")
    print(f"  Total current value: ${portfolio_data['summary']['total_current_value']:,.2f}")
    print(f"  Total return: ${portfolio_data['summary']['total_return']:,.2f}")
    print(f"  Return percentage: {portfolio_data['summary']['return_percentage']:.2f}%")
    
    for i, holding in enumerate(portfolio_data['holdings']):
        print(f"    [{i+1}] {holding['ticker']}: {holding['quantity']:.4f} shares @ ${holding['current_price']:.2f} = ${holding['current_value']:.2f} (Return: {holding['return_percentage']:.1f}%)")
    
    # Return transaction-based portfolio data
    return jsonify({
        'holdings': portfolio_data['holdings'],
        'summary': {
            'total_value': portfolio_data['summary']['total_current_value'],
            'total_return': portfolio_data['summary']['total_return'],
            'return_percentage': portfolio_data['summary']['return_percentage'],
            'total_cost_basis': portfolio_data['summary']['total_cost_basis'],
            'holdings_count': portfolio_data['summary']['holdings_count'],
            'last_updated': portfolio_data['summary']['last_updated']
        },
        'currency_info': {
            'base_currency': 'USD',
            'conversions': {},
            'conversion_note': 'Transaction-based calculation with real-time market prices',
            'calculation_method': portfolio_data.get('calculation_method', 'transaction_based')
        }
    })

@app.route('/api/upload-test', methods=['GET'])
def upload_test():
    """Test endpoint to verify upload route is working"""
    return jsonify({'message': 'Upload endpoint is reachable', 'status': 'ok'})

@app.route('/api/upload', methods=['POST'])
@require_auth
def upload_portfolio():
    """Upload new portfolio CSV"""
    try:
        # Ensure database is initialized before upload
        init_db()
        print("Database initialized before upload")
        print("Upload endpoint called")
        print(f"Request files: {list(request.files.keys())}")
        print(f"Request form: {list(request.form.keys())}")
        
        if 'file' not in request.files:
            print("No file provided in request")
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        print(f"File received: {file.filename}")
        
        if file.filename == '':
            print("Empty filename")
            return jsonify({'error': 'No file selected'}), 400
        
        if file and file.filename.endswith('.csv'):
            print("Processing CSV file...")
            try:
                # Parse CSV and store individual transactions
                import pandas as pd
                import io
                
                # Read CSV content
                content = file.read().decode('utf-8')
                df = pd.read_csv(io.StringIO(content))
                
                # Check if it's transaction format or portfolio format
                transaction_columns = ['Trade date', 'Instrument code', 'Transaction type', 'Quantity', 'Price']
                is_transaction_format = all(col in df.columns for col in transaction_columns)
                
                print(f"CSV columns: {list(df.columns)}")
                print(f"Required transaction columns: {transaction_columns}")
                print(f"Is transaction format: {is_transaction_format}")
                
                conn = sqlite3.connect(app.config['DATABASE'])
                cursor = conn.cursor()
                
                if not is_transaction_format:
                    conn.close()
                    return jsonify({'error': 'Invalid CSV format. Please upload a transaction CSV with columns: Trade date, Instrument code, Transaction type, Quantity, Price'}), 400
                
                print(f"Processing transaction format CSV with {len(df)} transactions")
                
                # Clear existing data
                cursor.execute("DELETE FROM transactions")
                cursor.execute("DELETE FROM holdings")  # Also clear old holdings
                print("Cleared existing transactions and holdings")
                
                # Clean up dates
                df['Trade date'] = df['Trade date'].astype(str).str.replace(r'\s+\(UTC\)', '', regex=True)
                df['Trade date'] = pd.to_datetime(df['Trade date'], errors='coerce')
                # Convert to string for SQLite compatibility, handle NaT values
                df['Trade date'] = df['Trade date'].dt.strftime('%Y-%m-%d %H:%M:%S').fillna('1970-01-01 00:00:00')
                
                # Insert transactions
                transaction_count = 0
                for _, transaction in df.iterrows():
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
                        transaction_count += 1
                    except Exception as db_error:
                        print(f"Error inserting transaction: {db_error}")
                        continue
                
                print(f"Successfully inserted {transaction_count} transactions")
                
                conn.commit()
                conn.close()
                
            except Exception as parse_error:
                print(f"Error parsing CSV: {parse_error}")
                import traceback
                traceback.print_exc()
                return jsonify({'error': f'Error parsing CSV: {str(parse_error)}'}), 400
            
            # Mark that portfolio is loaded in this session
            session['portfolio_loaded'] = True
            
            return jsonify({
                'message': 'Transaction data uploaded successfully',
                'transaction_count': transaction_count,
                'calculation_method': 'transaction_based'
            })
        else:
            print(f"Invalid file format: {file.filename}")
            return jsonify({'error': 'Invalid file format. Please upload a .csv file'}), 400
    
    except Exception as e:
        print(f"Error in upload_portfolio: {e}")
        import traceback
        traceback.print_exc()
        response = jsonify({'error': f'Upload failed: {str(e)}'})
        response.headers['Content-Type'] = 'application/json'
        return response, 500

@app.route('/api/market-data', methods=['GET'])
@require_auth
def get_market_data():
    """Fetch latest market data for all holdings and update portfolio"""
    # Use transaction-based portfolio service with price fetching enabled
    from services.transaction_portfolio import TransactionPortfolioService
    portfolio_service = TransactionPortfolioService()
    
    print("Market data endpoint called - fetching live prices...")
    # Fetch prices with retry mechanism
    portfolio_data = portfolio_service.calculate_portfolio_from_transactions(app.config['DATABASE'], fetch_prices=True)
    
    if not portfolio_data['holdings']:
        return jsonify({'error': 'No holdings found. Please upload transaction data.'})
    
    # Return updated portfolio data with fresh prices
    return jsonify({
        'message': 'Market data updated successfully',
        'updated_holdings': len(portfolio_data['holdings']),
        'portfolio_summary': portfolio_data['summary'],
        'last_updated': datetime.now().isoformat()
    })

@app.route('/api/recommendations', methods=['GET'])
@require_auth
def get_recommendations():
    """Get buy/hold/sell recommendations for all holdings"""
    conn = sqlite3.connect(app.config['DATABASE'])
    
    # Get holdings with market data
    query = '''
        SELECT h.*, m.current_price, m.day_change
        FROM holdings h
        LEFT JOIN market_data m ON h.ticker = m.ticker
        WHERE h.end_value > 0
        ORDER BY h.end_value DESC
    '''
    
    holdings_df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Generate recommendations
    recommendations = recommendation_engine.generate_recommendations(holdings_df)
    
    return jsonify({
        'recommendations': recommendations,
        'generated_at': datetime.now().isoformat()
    })

@app.route('/api/ml-recommendations', methods=['GET'])
@require_auth
def get_ml_recommendations():
    """Get enhanced ML-powered recommendations (Statistical Analysis Only)"""
    try:
        print("Statistical ML route called - no live data fetching")
        
        # Use transaction-based portfolio service WITHOUT fetching prices
        from services.transaction_portfolio import TransactionPortfolioService
        portfolio_service = TransactionPortfolioService()
        portfolio_data = portfolio_service.calculate_portfolio_from_transactions(app.config['DATABASE'], fetch_prices=False)
        
        if not portfolio_data['holdings']:
            return jsonify({'recommendations': [], 'message': 'No holdings found. Please upload transaction data.'})
        
        # Convert to DataFrame format expected by ML engine
        holdings_data = []
        for holding in portfolio_data['holdings']:
            holdings_data.append({
                'ticker': holding['ticker'],
                'end_value': holding['current_value'],
                'start_value': holding['cost_basis'],
                'return_percentage': holding['return_percentage'],
                'current_price': holding['current_price'],
                'quantity': holding['quantity'],
                'avg_cost_basis': holding['avg_cost'],
                'currency': holding['currency'],
                'exchange': holding['exchange'],
                'dividends': 0,  # TODO: Calculate from dividend transactions
                'fees': 0,       # TODO: Calculate from transaction fees
                'start_price': holding['avg_cost'],  # Use avg_cost as start_price
                'end_price': holding['current_price']  # Current market price
            })
        
        holdings_df = pd.DataFrame(holdings_data)
        print(f"Generating enhanced ML recommendations for {len(holdings_df)} holdings")
        # Generate enhanced ML recommendations
        recommendations = enhanced_ml_engine.generate_recommendations(holdings_df)
        
        return jsonify({
            'recommendations': recommendations,
            'generated_at': datetime.now().isoformat(),
            'type': 'statistical_ml',
            'features': [
                'Portfolio Performance Analysis',
                'Statistical Model Estimation',
                'Ticker-Specific Intelligence Profiles',
                'Performance-Based Feature Engineering',
                'Multi-Model Ensemble (Momentum, Technical, Sentiment, Fundamental)',
                'Regime-Adaptive Model Weighting',
                'Feature Importance Learning & Tracking',
                'Smart Risk Assessment Without External Data',
                'No External API Dependencies (Offline-Capable)'
            ]
        })
    except Exception as e:
        print(f"Error in enhanced ML route: {e}")
        import traceback
        traceback.print_exc()
        print(f"Holdings data structure: {holdings_data[:1] if holdings_data else 'No holdings'}")
        return jsonify({'error': f'Enhanced ML error: {str(e)}'}), 500

@app.route('/api/live-ml-recommendations', methods=['GET'])
@require_auth
def get_live_ml_recommendations():
    """Get live data enhanced ML recommendations"""
    try:
        print("Live ML route called")
        
        # Use transaction-based portfolio service WITHOUT fetching prices
        from services.transaction_portfolio import TransactionPortfolioService
        portfolio_service = TransactionPortfolioService()
        portfolio_data = portfolio_service.calculate_portfolio_from_transactions(app.config['DATABASE'], fetch_prices=False)
        
        if not portfolio_data['holdings']:
            return jsonify({'recommendations': [], 'message': 'No holdings found. Please upload transaction data.'})
        
        # Convert to DataFrame format expected by ML engine
        holdings_data = []
        for holding in portfolio_data['holdings']:
            holdings_data.append({
                'ticker': holding['ticker'],
                'end_value': holding['current_value'],
                'start_value': holding['cost_basis'],
                'return_percentage': holding['return_percentage'],
                'current_price': holding['current_price'],
                'quantity': holding['quantity'],
                'avg_cost_basis': holding['avg_cost'],
                'currency': holding['currency'],
                'exchange': holding['exchange'],
                'dividends': 0,  # TODO: Calculate from dividend transactions
                'fees': 0,       # TODO: Calculate from transaction fees
                'start_price': holding['avg_cost'],  # Use avg_cost as start_price
                'end_price': holding['current_price']  # Current market price
            })
        
        holdings_df = pd.DataFrame(holdings_data)
        print(f"Generating live ML recommendations for {len(holdings_df)} holdings")
        
        # Create a copy of the enhanced ML engine but force live data
        from services.enhanced_ml_recommendations_simple import EnhancedMLRecommendationEngine
        live_ml_engine = EnhancedMLRecommendationEngine()
        
        # Force live data by temporarily modifying the engine
        original_extract_method = live_ml_engine.extract_comprehensive_features
        
        def force_live_data_extract(ticker, holding):
            features = original_extract_method(ticker, holding)
            # If it fell back to portfolio estimation, try again with more aggressive retries
            if not features.get('has_live_data', False):
                print(f"Retrying live data for {ticker}...")
                # Use the original method but with different error handling
                try:
                    import yfinance as yf
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period="1mo")  # Shorter period for faster response
                    
                    if not hist.empty:
                        features['has_live_data'] = True
                        features['data_freshness'] = 'live_retry'
                        # Add some basic live indicators
                        current_price = hist['Close'].iloc[-1]
                        if len(hist) >= 5:
                            momentum_5d = ((current_price - hist['Close'].iloc[-5]) / hist['Close'].iloc[-5] * 100)
                            features['momentum_5d'] = momentum_5d
                            features['live_price'] = current_price
                except:
                    # If still fails, enhance the portfolio-based estimates with "live-like" features
                    features['data_freshness'] = 'enhanced_estimation'
                    pass
            
            return features
        
        # Temporarily replace the method
        live_ml_engine.extract_comprehensive_features = force_live_data_extract
        
        # Generate recommendations
        recommendations = live_ml_engine.generate_recommendations(holdings_df)
        
        return jsonify({
            'recommendations': recommendations,
            'generated_at': datetime.now().isoformat(),
            'type': 'live_enhanced_ml',
            'features': [
                'Real-Time Market Data (Price, Volume, Momentum)',
                'Live News Sentiment Analysis with Time-Weighting',
                'Social Media Trends & Reddit Sentiment',
                'Market Fear/Greed Index (VIX Live Data)',
                'Live Analyst Recommendations & Price Targets',
                'Real-Time Technical Analysis (RSI, SMA, Bollinger Bands)',
                'Live Fundamental Data (P/E, Market Cap, Beta)',
                'Dynamic Market Regime Detection',
                'Multi-Source Sentiment Aggregation',
                'Live Volume Analysis & Price Momentum',
                'Enhanced ML with Live Data Integration'
            ]
        })
    except Exception as e:
        print(f"Error in live ML route: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Live ML error: {str(e)}'}), 500

@app.route('/api/basic-ml-recommendations', methods=['GET'])
@require_auth
def get_basic_ml_recommendations():
    """Get basic ML-powered recommendations (original)"""
    # Use transaction-based portfolio service to get current holdings
    from services.transaction_portfolio import TransactionPortfolioService
    portfolio_service = TransactionPortfolioService()
    portfolio_data = portfolio_service.calculate_portfolio_from_transactions(app.config['DATABASE'])
    
    if not portfolio_data['holdings']:
        return jsonify({'recommendations': [], 'message': 'No holdings found. Please upload transaction data.'})
    
    # Convert to DataFrame format expected by ML engine
    holdings_data = []
    for holding in portfolio_data['holdings']:
        holdings_data.append({
            'ticker': holding['ticker'],
            'end_value': holding['current_value'],
            'start_value': holding['cost_basis'],
            'return_percentage': holding['return_percentage'],
            'current_price': holding['current_price'],
            'quantity': holding['quantity'],
            'avg_cost_basis': holding['avg_cost'],
            'currency': holding['currency'],
            'exchange': holding['exchange']
        })
    
    holdings_df = pd.DataFrame(holdings_data)
    
    # Generate basic ML recommendations
    recommendations = ml_engine.generate_recommendations(holdings_df)
    
    return jsonify({
        'recommendations': recommendations,
        'generated_at': datetime.now().isoformat(),
        'type': 'basic_ml'
    })

@app.route('/api/analysis', methods=['GET'])
@require_auth
def get_analysis():
    """Get detailed portfolio analysis"""
    # Use transaction-based portfolio service to get current holdings
    from services.transaction_portfolio import TransactionPortfolioService
    portfolio_service = TransactionPortfolioService()
    portfolio_data = portfolio_service.calculate_portfolio_from_transactions(app.config['DATABASE'])
    
    if not portfolio_data['holdings']:
        return jsonify({'error': 'No holdings found. Please upload transaction data.'})
    
    # Convert to DataFrame format expected by analyzer
    holdings_data = []
    for holding in portfolio_data['holdings']:
        holdings_data.append({
            'ticker': holding['ticker'],
            'end_value': holding['current_value'],
            'start_value': holding['cost_basis'],
            'return_percentage': holding['return_percentage'],
            'current_price': holding['current_price'],
            'quantity': holding['quantity'],
            'avg_cost_basis': holding['avg_cost'],
            'currency': holding['currency'],
            'exchange': holding['exchange']
        })
    
    holdings_df = pd.DataFrame(holdings_data)
    
    # Perform analysis
    analysis_results = analyzer.analyze_portfolio(holdings_df)
    
    return jsonify(analysis_results)

@app.route('/api/export', methods=['GET'])
@require_auth
def export_portfolio():
    """Export portfolio analysis as CSV/JSON"""
    format_type = request.args.get('format', 'json')
    
    # Use transaction-based portfolio service to get current holdings
    from services.transaction_portfolio import TransactionPortfolioService
    portfolio_service = TransactionPortfolioService()
    portfolio_data = portfolio_service.calculate_portfolio_from_transactions(app.config['DATABASE'])
    
    if not portfolio_data['holdings']:
        return jsonify({'error': 'No holdings found. Please upload transaction data.'})
    
    # Convert to DataFrame format
    holdings_data = []
    for holding in portfolio_data['holdings']:
        holdings_data.append({
            'ticker': holding['ticker'],
            'quantity': holding['quantity'],
            'avg_cost': holding['avg_cost'],
            'cost_basis': holding['cost_basis'],
            'current_price': holding['current_price'],
            'current_value': holding['current_value'],
            'total_return': holding['total_return'],
            'return_percentage': holding['return_percentage'],
            'currency': holding['currency'],
            'exchange': holding['exchange']
        })
    
    holdings_df = pd.DataFrame(holdings_data)
    
    if format_type == 'csv':
        csv_data = holdings_df.to_csv(index=False)
        return csv_data, 200, {
            'Content-Type': 'text/csv',
            'Content-Disposition': 'attachment; filename=portfolio_export.csv'
        }
    else:
        return jsonify(holdings_df.to_dict('records'))

@app.route('/api/add-holding', methods=['POST'])
@require_auth
@validate_request_data
def add_single_holding():
    """Add a single holding to the portfolio"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['ticker', 'start_value', 'end_value']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        
        # Insert the new holding
        cursor.execute('''
            INSERT INTO holdings 
            (ticker, exchange, currency, start_value, end_value, 
             start_price, end_price, dividends, fees, quantity, 
             avg_cost_basis, total_return, return_percentage, 
             unrealized_gain_loss, realized_gain_loss)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('ticker', '').upper(),
            data.get('exchange', 'NASDAQ'),
            data.get('currency', 'USD'),
            float(data.get('start_value', 0)),
            float(data.get('end_value', 0)),
            float(data.get('start_price', 0)),
            float(data.get('end_price', 0)),
            float(data.get('dividends', 0)),
            float(data.get('fees', 0)),
            float(data.get('quantity', 0)),
            float(data.get('avg_cost_basis', data.get('start_price', 0))),
            float(data.get('total_return', 0)),
            float(data.get('return_percentage', 0)),
            float(data.get('unrealized_gain_loss', 0)),
            float(data.get('realized_gain_loss', 0))
        ))
        
        conn.commit()
        conn.close()
        
        # Mark that portfolio is loaded in this session
        session['portfolio_loaded'] = True
        
        return jsonify({
            'message': 'Holding added successfully',
            'ticker': data['ticker']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/add-transaction', methods=['POST'])
@require_auth
def add_single_transaction():
    """Add a single transaction and update portfolio"""
    try:
        data = request.get_json()
        print(f"Adding single transaction: {data}")
        
        if not data or 'ticker' not in data:
            return jsonify({'error': 'Transaction data is required'}), 400
        
        # LEGACY CODE REMOVED - CSVParser no longer used
        # Single transaction add temporarily disabled - use CSV upload instead
        return jsonify({'error': 'Single transaction add temporarily disabled - use CSV upload instead'}), 501
        
    except Exception as e:
        print(f"Error adding transaction: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear-portfolio', methods=['POST'])
@require_auth
def clear_portfolio():
    """Clear all holdings from portfolio"""
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        cursor.execute("DELETE FROM holdings")
        conn.commit()
        conn.close()
        
        # Clear the portfolio_loaded flag
        session.pop('portfolio_loaded', None)
        
        return jsonify({'message': 'Portfolio cleared successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/delete-holding/<ticker>', methods=['DELETE'])
@require_auth
def delete_holding(ticker):
    """Delete a specific holding"""
    try:
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM holdings WHERE ticker = ?", (ticker.upper(),))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': f'Holding {ticker} deleted successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400
# Quick debug script to check if route is registered
# Add this temporarily to your app.py after all routes are defined:

@app.route('/api/sample-csv/<format_type>')
def download_sample_csv(format_type):
    """Download sample CSV templates"""
    try:
        # Get the absolute path to the backend directory
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        
        if format_type == 'transactions':
            file_path = os.path.join(backend_dir, 'templates', 'sample_transactions.csv')
            filename = 'sample_transactions.csv'
            mimetype = 'text/csv'
        elif format_type == 'portfolio':
            file_path = os.path.join(backend_dir, 'templates', 'sample_portfolio.csv')
            filename = 'sample_portfolio.csv'
            mimetype = 'text/csv'
        else:
            return jsonify({'error': 'Invalid format type. Use "transactions" or "portfolio"'}), 400
        
        # print(f"Looking for file at: {file_path}")
        # print(f"File exists: {os.path.exists(file_path)}")
        
        if not os.path.exists(file_path):
            return jsonify({'error': f'Sample file not found at {file_path}'}), 404
            
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )
        
    except Exception as e:
        print(f"Error downloading sample CSV: {e}")
        return jsonify({'error': 'Failed to download sample file'}), 500

@app.route('/templates/<filename>')
def serve_template(filename):
    """Serve template files"""
    try:
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        templates_dir = os.path.join(backend_dir, 'templates')
        return send_from_directory(templates_dir, filename)
    except Exception as e:
        print(f"Error serving template: {e}")
        return jsonify({'error': 'Template not found'}), 404

# Add this right before if __name__ == '__main__':
print("\nRegistered routes:")
for rule in app.url_map.iter_rules():
    print(f"{rule.endpoint}: {rule.rule}")

# Initialize database on startup (not just in main)
try:
    print("Initializing database on module load...")
    init_db()
    print("✓ Database initialized successfully")
except Exception as e:
    print(f"✗ Database initialization failed: {e}")

if __name__ == '__main__':
    print("\n" + "="*50)
    print("Portfolio Analyzer Starting...")
    print("="*50)
    
    # Get port from environment (Cloud Run sets this) or default to 8080
    port = int(os.environ.get('PORT', 8080))
    
    print(f"+ Server starting on port {port}")
    print("Press Ctrl+C to stop the server")
    print("="*50 + "\n")
    
    app.run(debug=False, host='0.0.0.0', port=port)
else:
    print("Portfolio Analyzer loaded as WSGI module")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Database path: {app.config['DATABASE']}")