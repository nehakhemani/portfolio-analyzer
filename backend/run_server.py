from flask import Flask, request, jsonify, render_template_string, send_from_directory
from flask_cors import CORS
import os
import sqlite3
import pandas as pd
from datetime import datetime

# Import your services
from services.market_data import MarketDataService
from services.analysis import PortfolioAnalyzer
from services.recommendations import RecommendationEngine
from utils.csv_parser import CSVParser

app = Flask(__name__)
CORS(app)

# Configuration
DATABASE = 'data/portfolio.db'

# Initialize services
market_service = MarketDataService()
analyzer = PortfolioAnalyzer()
recommendation_engine = RecommendationEngine()

# Read the HTML file
def get_html_content():
    html_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'index.html')
    with open(html_path, 'r') as f:
        return f.read()

# Read CSS file
def get_css_content():
    css_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'css', 'style.css')
    with open(css_path, 'r') as f:
        return f.read()

# Read JS file
def get_js_content():
    js_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'js', 'app.js')
    with open(js_path, 'r') as f:
        return f.read()

@app.route('/')
def index():
    """Serve the main HTML page"""
    return get_html_content()

@app.route('/css/style.css')
def serve_css():
    """Serve CSS file"""
    return get_css_content(), 200, {'Content-Type': 'text/css'}

@app.route('/js/app.js')
def serve_js():
    """Serve JavaScript file"""
    return get_js_content(), 200, {'Content-Type': 'application/javascript'}

# Initialize database
def init_db():
    """Initialize SQLite database with portfolio tables"""
    os.makedirs('data', exist_ok=True)
    
    conn = sqlite3.connect(DATABASE)
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

@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    """Get current portfolio data"""
    conn = sqlite3.connect(DATABASE)
    
    holdings_df = pd.read_sql_query(
        "SELECT * FROM holdings ORDER BY end_value DESC", 
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
            }
        })
    
    # Calculate portfolio metrics
    total_value = holdings_df['end_value'].sum()
    total_start_value = holdings_df['start_value'].sum()
    total_return = total_value - total_start_value
    return_pct = (total_return / total_start_value * 100) if total_start_value > 0 else 0
    total_dividends = holdings_df['dividends'].sum()
    
    return jsonify({
        'holdings': holdings_df.to_dict('records'),
        'summary': {
            'total_value': round(total_value, 2),
            'total_return': round(total_return, 2),
            'return_percentage': round(return_pct, 2),
            'total_dividends': round(total_dividends, 2),
            'holdings_count': len(holdings_df)
        }
    })

@app.route('/api/upload', methods=['POST'])
def upload_portfolio():
    """Upload new portfolio CSV"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and file.filename.endswith('.csv'):
        # Parse CSV
        parser = CSVParser()
        holdings_data = parser.parse_portfolio_csv(file)
        
        # Save to database
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Clear existing holdings
        cursor.execute("DELETE FROM holdings")
        
        # Insert new holdings
        for holding in holdings_data:
            cursor.execute('''
                INSERT INTO holdings 
                (ticker, exchange, currency, start_value, end_value, 
                 start_price, end_price, dividends, fees)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                holding['ticker'], holding['exchange'], holding['currency'],
                holding['start_value'], holding['end_value'],
                holding['start_price'], holding['end_price'],
                holding['dividends'], holding['fees']
            ))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'Portfolio uploaded successfully',
            'holdings_count': len(holdings_data)
        })
    
    return jsonify({'error': 'Invalid file format'}), 400

@app.route('/api/market-data', methods=['GET'])
def get_market_data():
    """Fetch latest market data for all holdings"""
    conn = sqlite3.connect(DATABASE)
    
    # Get unique tickers
    tickers_df = pd.read_sql_query(
        "SELECT DISTINCT ticker FROM holdings WHERE end_value > 0", 
        conn
    )
    
    if tickers_df.empty:
        conn.close()
        return jsonify({'market_data': {}, 'message': 'No holdings found'})
    
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
def get_recommendations():
    """Get buy/hold/sell recommendations for all holdings"""
    conn = sqlite3.connect(DATABASE)
    
    holdings_df = pd.read_sql_query("SELECT * FROM holdings", conn)
    conn.close()
    
    if holdings_df.empty:
        return jsonify({'recommendations': [], 'message': 'No holdings found'})
    
    # Generate recommendations
    recommendations = recommendation_engine.generate_recommendations(holdings_df)
    
    return jsonify({
        'recommendations': recommendations,
        'generated_at': datetime.now().isoformat()
    })

@app.route('/api/analysis', methods=['GET'])
def get_analysis():
    """Get detailed portfolio analysis"""
    conn = sqlite3.connect(DATABASE)
    holdings_df = pd.read_sql_query("SELECT * FROM holdings", conn)
    conn.close()
    
    if holdings_df.empty:
        return jsonify({'error': 'No holdings found'}), 404
    
    # Perform analysis
    analysis_results = analyzer.analyze_portfolio(holdings_df)
    
    return jsonify(analysis_results)

@app.route('/api/export', methods=['GET'])
def export_portfolio():
    """Export portfolio analysis as CSV/JSON"""
    format_type = request.args.get('format', 'json')
    
    conn = sqlite3.connect(DATABASE)
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

if __name__ == '__main__':
    print("\n" + "="*50)
    print("Portfolio Analyzer Starting...")
    print("="*50)
    
    # Initialize database
    init_db()
    print("+ Database initialized")
    
    print(f"+ Server starting on http://localhost:5000")
    print("\nOpen your browser to http://localhost:5000")
    print("\nIf you see 404 errors, make sure:")
    print("  - frontend/index.html exists")
    print("  - frontend/css/style.css exists")
    print("  - frontend/js/app.js exists")
    print("\nPress Ctrl+C to stop the server")
    print("="*50 + "\n")
    
    app.run(debug=True, port=5000, host='127.0.0.1')