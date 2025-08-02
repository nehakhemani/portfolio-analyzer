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
from utils.csv_parser import CSVParser
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
    # Create data directory if it doesn't exist
    os.makedirs('data', exist_ok=True)
    
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
    """Get current portfolio data"""
    conn = sqlite3.connect(app.config['DATABASE'])
    
    holdings_df = pd.read_sql_query(
        "SELECT * FROM holdings WHERE end_value > 0 ORDER BY end_value DESC", 
        conn
    )
    
    conn.close()
    
    if holdings_df.empty:
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
    
    # Convert holdings to list and add USD conversions
    holdings_list = holdings_df.to_dict('records')
    total_value_usd = 0
    total_start_value_usd = 0
    total_dividends_usd = 0
    currency_conversions = {}
    
    for holding in holdings_list:
        currency = holding.get('currency', 'USD')
        
        # Convert to USD for consistent analysis
        if currency != 'USD':
            start_value_usd = currency_converter.convert_to_usd(holding['start_value'], currency)
            end_value_usd = currency_converter.convert_to_usd(holding['end_value'], currency)
            dividends_usd = currency_converter.convert_to_usd(holding.get('dividends', 0), currency)
            
            holding['start_value_usd'] = round(start_value_usd, 2)
            holding['end_value_usd'] = round(end_value_usd, 2)
            holding['dividends_usd'] = round(dividends_usd, 2)
            
            # Track conversion rates for display
            if currency not in currency_conversions:
                conversion = currency_converter.convert(1, currency, 'USD')
                currency_conversions[currency] = {
                    'rate': round(conversion['exchange_rate'], 4),
                    'last_updated': conversion['conversion_time']
                }
        else:
            holding['start_value_usd'] = holding['start_value']
            holding['end_value_usd'] = holding['end_value']
            holding['dividends_usd'] = holding.get('dividends', 0)
        
        total_value_usd += holding['end_value_usd']
        total_start_value_usd += holding['start_value_usd']
        total_dividends_usd += holding['dividends_usd']
    
    # Calculate portfolio metrics in USD
    total_return_usd = total_value_usd - total_start_value_usd
    return_pct = (total_return_usd / total_start_value_usd * 100) if total_start_value_usd > 0 else 0
    
    # Debug logging for return calculation
    print(f"Return Calculation Debug:")
    print(f"  Total Start Value (USD): ${total_start_value_usd:,.2f}")
    print(f"  Total Current Value (USD): ${total_value_usd:,.2f}")
    print(f"  Total Return (USD): ${total_return_usd:,.2f}")
    print(f"  Return Percentage: {return_pct:.2f}%")
    print(f"  Number of holdings: {len(holdings_list)}")
    for i, holding in enumerate(holdings_list):
        print(f"    [{i+1}] {holding['ticker']}: {holding.get('currency', 'USD')}{holding['start_value']} -> {holding.get('currency', 'USD')}{holding['end_value']} (USD: ${holding['start_value_usd']} -> ${holding['end_value_usd']})")
    
    return jsonify({
        'holdings': holdings_list,
        'summary': {
            'total_value': round(total_value_usd, 2),
            'total_return': round(total_return_usd, 2),
            'return_percentage': round(return_pct, 2),
            'total_dividends': round(total_dividends_usd, 2),
            'holdings_count': len(holdings_df)
        },
        'currency_info': {
            'base_currency': 'USD',
            'conversion_note': 'All analysis performed in USD equivalent',
            'conversions': currency_conversions
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
                # Parse CSV - detect format and use appropriate parser
                parser = CSVParser()
                holdings_data = parser.detect_and_parse_csv(file)
                print(f"Successfully parsed CSV, got {len(holdings_data)} holdings")
                
                if not holdings_data:
                    return jsonify({'error': 'No valid holdings found in CSV file'}), 400
                
                # Save to database
                conn = sqlite3.connect(app.config['DATABASE'])
                cursor = conn.cursor()
                
                # Clear existing holdings
                cursor.execute("DELETE FROM holdings")
                print("Cleared existing holdings")
                
                # Insert new holdings
                for i, holding in enumerate(holdings_data):
                    print(f"Inserting holding {i+1}: {holding.get('ticker', 'Unknown')}")
                    try:
                        cursor.execute('''
                            INSERT INTO holdings 
                            (ticker, exchange, currency, start_value, end_value, 
                             start_price, end_price, dividends, fees, quantity, 
                             avg_cost_basis, total_return, return_percentage, 
                             unrealized_gain_loss, realized_gain_loss)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            holding.get('ticker', ''),
                            holding.get('exchange', 'NASDAQ'),
                            holding.get('currency', 'USD'),
                            float(holding.get('start_value', 0)),
                            float(holding.get('end_value', 0)),
                            float(holding.get('start_price', 0)),
                            float(holding.get('end_price', 0)),
                            float(holding.get('dividends', 0)),
                            float(holding.get('fees', 0)),
                            float(holding.get('quantity', 0)),
                            float(holding.get('avg_cost_basis', holding.get('start_price', 0))),
                            float(holding.get('total_return', 0)),
                            float(holding.get('return_percentage', 0)),
                            float(holding.get('unrealized_gain_loss', 0)),
                            float(holding.get('realized_gain_loss', 0))
                        ))
                    except Exception as db_error:
                        print(f"Error inserting holding {holding.get('ticker', 'Unknown')}: {db_error}")
                        conn.close()
                        return jsonify({'error': f'Database error inserting {holding.get("ticker", "holding")}: {str(db_error)}'}), 500
                
                conn.commit()
                conn.close()
                print(f"Successfully inserted {len(holdings_data)} holdings")
                
            except Exception as parse_error:
                print(f"Error parsing CSV: {parse_error}")
                import traceback
                traceback.print_exc()
                return jsonify({'error': f'Error parsing CSV: {str(parse_error)}'}), 400
            
            # Mark that portfolio is loaded in this session
            session['portfolio_loaded'] = True
            
            print(f"Successfully uploaded {len(holdings_data)} holdings")
            return jsonify({
                'message': 'Portfolio uploaded successfully',
                'holdings_count': len(holdings_data)
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
    """Fetch latest market data for all holdings"""
    conn = sqlite3.connect(app.config['DATABASE'])
    
    # Get unique tickers
    tickers_df = pd.read_sql_query(
        "SELECT DISTINCT ticker FROM holdings WHERE end_value > 0", 
        conn
    )
    tickers = tickers_df['ticker'].tolist()
    
    # Fetch market data
    market_data = market_service.fetch_batch_quotes(tickers)
    
    # Update database
    cursor = conn.cursor()
    cursor.execute("DELETE FROM market_data")  # Clear old data
    
    for ticker, data in market_data.items():
        cursor.execute('''
            INSERT INTO market_data 
            (ticker, current_price, day_change, volume, market_cap)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            ticker, data['price'], data['change'], 
            data['volume'], data['market_cap']
        ))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'market_data': market_data,
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
    """Get enhanced ML-powered recommendations"""
    try:
        print("Enhanced ML route called")
        conn = sqlite3.connect(app.config['DATABASE'])
        holdings_df = pd.read_sql_query("SELECT * FROM holdings WHERE end_value > 0", conn)
        conn.close()
        
        if holdings_df.empty:
            return jsonify({'recommendations': [], 'message': 'No holdings found'})
        
        print(f"Generating enhanced ML recommendations for {len(holdings_df)} holdings")
        # Generate enhanced ML recommendations
        recommendations = enhanced_ml_engine.generate_recommendations(holdings_df)
        
        return jsonify({
            'recommendations': recommendations,
            'generated_at': datetime.now().isoformat(),
            'type': 'enhanced_ml',
            'features': [
                'Real-Time News Sentiment Analysis',
                'Social Media Sentiment & Trending Analysis',
                'Market Fear/Greed Index (VIX Analysis)',
                'Analyst Recommendations & Price Targets',
                'Technical Analysis (RSI, SMA, Bollinger Bands)',
                'Fundamental Analysis (P/E, Market Cap, Beta)',
                'Market Regime Detection (Bull/Bear/Crisis)',
                'Volume Analysis & Price Momentum',
                'Custom ML Scoring with Sentiment Weighting (17%)'
            ]
        })
    except Exception as e:
        print(f"Error in enhanced ML route: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Enhanced ML error: {str(e)}'}), 500

@app.route('/api/basic-ml-recommendations', methods=['GET'])
@require_auth
def get_basic_ml_recommendations():
    """Get basic ML-powered recommendations (original)"""
    conn = sqlite3.connect(app.config['DATABASE'])
    holdings_df = pd.read_sql_query("SELECT * FROM holdings", conn)
    conn.close()
    
    if holdings_df.empty:
        return jsonify({'recommendations': [], 'message': 'No holdings found'})
    
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
    conn = sqlite3.connect(app.config['DATABASE'])
    holdings_df = pd.read_sql_query("SELECT * FROM holdings", conn)
    conn.close()
    
    # Perform analysis
    analysis_results = analyzer.analyze_portfolio(holdings_df)
    
    return jsonify(analysis_results)

@app.route('/api/export', methods=['GET'])
@require_auth
def export_portfolio():
    """Export portfolio analysis as CSV/JSON"""
    format_type = request.args.get('format', 'json')
    
    conn = sqlite3.connect(app.config['DATABASE'])
    holdings_df = pd.read_sql_query("SELECT * FROM holdings", conn)
    conn.close()
    
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
        
        # Create a mini CSV with just this transaction
        transaction_csv = f"""Trade date,Instrument code,Market code,Quantity,Price,Transaction type,Currency,Amount,Transaction fee,Transaction method
{data.get('trade_date')},{data.get('ticker')},{data.get('exchange', 'NASDAQ')},{data.get('quantity', 0)},{data.get('price', 0)},{data.get('transaction_type')},{data.get('currency', 'USD')},{data.get('amount')},{data.get('fees', 0)},{data.get('transaction_method', data.get('transaction_type'))}"""
        
        # Use CSV parser to process this single transaction
        from utils.csv_parser import CSVParser
        import io
        
        parser = CSVParser()
        file_like = io.BytesIO(transaction_csv.encode('utf-8'))
        new_holdings = parser.parse_transaction_csv(file_like)
        
        if not new_holdings:
            return jsonify({'error': 'No valid holding created from transaction'}), 400
        
        # Get existing holdings for this ticker
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        
        existing_holding = cursor.execute(
            "SELECT * FROM holdings WHERE ticker = ? AND currency = ?", 
            (data.get('ticker').upper(), data.get('currency', 'USD'))
        ).fetchone()
        
        new_holding = new_holdings[0]  # Should only be one holding from single transaction
        
        if existing_holding:
            # Update existing holding by re-processing all transactions
            # For simplicity, we'll just update the values for now
            print(f"Updating existing holding for {new_holding['ticker']}")
            
            cursor.execute('''
                UPDATE holdings SET
                    exchange = ?, start_value = ?, end_value = ?, 
                    start_price = ?, end_price = ?, dividends = dividends + ?, 
                    fees = fees + ?, quantity = ?, avg_cost_basis = ?,
                    total_return = ?, return_percentage = ?, 
                    unrealized_gain_loss = ?, realized_gain_loss = ?
                WHERE ticker = ? AND currency = ?
            ''', (
                new_holding.get('exchange'),
                new_holding.get('start_value'),
                new_holding.get('end_value'),
                new_holding.get('start_price'),
                new_holding.get('end_price'),
                new_holding.get('dividends', 0),
                new_holding.get('fees', 0),
                new_holding.get('quantity', 0),
                new_holding.get('avg_cost_basis', 0),
                new_holding.get('total_return', 0),
                new_holding.get('return_percentage', 0),
                new_holding.get('unrealized_gain_loss', 0),
                new_holding.get('realized_gain_loss', 0),
                new_holding['ticker'],
                new_holding['currency']
            ))
        else:
            # Create new holding
            print(f"Creating new holding for {new_holding['ticker']}")
            cursor.execute('''
                INSERT INTO holdings 
                (ticker, exchange, currency, start_value, end_value, 
                 start_price, end_price, dividends, fees, quantity, 
                 avg_cost_basis, total_return, return_percentage, 
                 unrealized_gain_loss, realized_gain_loss)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                new_holding['ticker'], new_holding['exchange'], new_holding['currency'],
                new_holding['start_value'], new_holding['end_value'],
                new_holding['start_price'], new_holding['end_price'],
                new_holding['dividends'], new_holding['fees'],
                new_holding.get('quantity', 0),
                new_holding.get('avg_cost_basis', new_holding.get('start_price', 0)),
                new_holding.get('total_return', 0),
                new_holding.get('return_percentage', 0),
                new_holding.get('unrealized_gain_loss', 0),
                new_holding.get('realized_gain_loss', 0)
            ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': f'Transaction added successfully for {new_holding["ticker"]}'})
        
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

if __name__ == '__main__':
    print("\n" + "="*50)
    print("Portfolio Analyzer Starting...")
    print("="*50)
    
    # Initialize database
    init_db()
    print("+ Database initialized")
    
    # Get port from environment (Replit sets this) or default to 5001
    port = int(os.environ.get('PORT', 8080))
    
    print(f"+ Server starting on port {port}")
    print("Press Ctrl+C to stop the server")
    print("="*50 + "\n")
    
    app.run(debug=False, host='0.0.0.0', port=port)