"""
Multi-User Portfolio Analyzer - Clean Implementation
"""
from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import os
from datetime import datetime
from functools import wraps

# Import multi-user services
from services.database_service import DatabaseService
from services.csv_upload_service import CSVUploadService
from services.batch_job_service import BatchJobService
from services.statistical_analysis import StatisticalAnalysisService

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv('SECRET_KEY', 'temp-secret-key')

# Initialize multi-user services
db_service = DatabaseService('/app/data/portfolio_multiuser.db')
csv_service = CSVUploadService(db_service)
batch_service = BatchJobService(db_service)

def init_db():
    """Initialize multi-user database - handled by DatabaseService"""
    print("✅ Multi-user database initialized by DatabaseService")
    
    # Create default test user if none exists (for demo purposes)
    try:
        existing_user = db_service.authenticate_user('testuser', 'password123')
        if not existing_user:
            user_id = db_service.create_user('testuser', 'test@example.com', 'password123', 'Test', 'User')
            if user_id:
                print(f"✅ Created demo user: testuser (ID: {user_id})")
            else:
                print("ℹ️ Could not create demo user (may already exist with different password)")
        else:
            print(f"ℹ️ Demo user 'testuser' already exists")
    except Exception as e:
        print(f"ℹ️ Demo user setup: {e}")

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

def get_current_user_id():
    """Get current user ID from session"""
    return session.get('user_id')

# =========================================================================
# FRONTEND ROUTES
# =========================================================================

@app.route('/')
def serve_frontend():
    return send_from_directory('../frontend', 'index.html')

@app.route('/<path:filename>')  
def serve_static(filename):
    return send_from_directory('../frontend', filename)

# =========================================================================
# HEALTH & DEBUG ROUTES
# =========================================================================

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'database': 'connected',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/check-auth')
def check_auth():
    user_id = session.get('user_id')
    if user_id:
        user = db_service.get_user_by_id(user_id)
        if user:
            return jsonify({
                'authenticated': True,
                'username': user['username'],
                'user_id': user_id,
                'full_name': user.get('full_name', user['username'])
            })
    return jsonify({
        'authenticated': False,
        'user': None
    })

# =========================================================================
# USER AUTHENTICATION ROUTES
# =========================================================================

@app.route('/api/auth/register', methods=['POST'])
def register_user():
    """Register a new user"""
    try:
        data = request.get_json()
        username = data.get('username')
        email = data.get('email') 
        password = data.get('password')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        
        if not all([username, email, password]):
            return jsonify({'error': 'Username, email, and password are required'}), 400
        
        user_id = db_service.create_user(username, email, password, first_name, last_name)
        
        if user_id:
            # Set session
            session['user_id'] = user_id
            session['username'] = username
            
            return jsonify({
                'success': True,
                'message': 'User registered successfully',
                'user': {
                    'id': user_id,
                    'username': username,
                    'email': email,
                    'full_name': f"{first_name} {last_name}".strip()
                }
            })
        else:
            return jsonify({'error': 'Username or email already exists'}), 409
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login_user():
    """Authenticate and login user"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not all([username, password]):
            return jsonify({'error': 'Username and password are required'}), 400
        
        user = db_service.authenticate_user(username, password)
        
        if user:
            # Set session
            session['user_id'] = user['id']
            session['username'] = user['username']
            
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'user': user
            })
        else:
            return jsonify({'error': 'Invalid username or password'}), 401
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout_user():
    """Logout current user"""
    try:
        session.clear()
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/user')
@require_auth
def get_current_user():
    """Get current user information"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user = db_service.get_user_by_id(user_id)
        if user:
            return jsonify({
                'success': True,
                'user': user
            })
        else:
            return jsonify({'error': 'User not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =========================================================================
# PORTFOLIO MANAGEMENT ROUTES
# =========================================================================

@app.route('/api/upload', methods=['POST'])
@require_auth
def upload_portfolio():
    """Upload portfolio CSV using multi-user service"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        csv_content = file.read().decode('utf-8')
        
        # Use multi-user CSV upload service
        result = csv_service.process_transaction_csv(user_id, csv_content)
        
        if result['success']:
            # Get portfolio data for frontend
            portfolio_data = csv_service.get_user_portfolio_data(user_id)
            
            return jsonify({
                'message': result['message'],
                'holdings_created': result['holdings_created'],
                'errors': result.get('errors', []),
                'debug_info': result.get('debug_info', {}),
                'workflow_complete': True,
                'steps_completed': ['upload'],
                'summary': {
                    'transactions_processed': result['debug_info'].get('csv_rows', 0),
                    'unique_tickers': result['holdings_created'],
                    'total_cost_basis': result['total_investment']
                },
                'portfolio_data': portfolio_data
            })
        else:
            return jsonify({
                'error': result['error'],
                'holdings_created': 0
            }), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/portfolio')
@require_auth
def get_portfolio():
    """Get portfolio holdings using multi-user service"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Use multi-user CSV service to get portfolio data
        portfolio_data = csv_service.get_user_portfolio_data(user_id)
        
        return jsonify(portfolio_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/latest-prices')
@require_auth
def get_latest_prices():
    """Get latest prices using multi-user service"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Use multi-user CSV service to get portfolio data with current prices
        portfolio_data = csv_service.get_user_portfolio_data(user_id)
        
        return jsonify(portfolio_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =========================================================================
# BATCH JOB ROUTES
# =========================================================================

@app.route('/api/trigger-batch-job', methods=['POST'])
@require_auth
def trigger_batch_job():
    """Manually trigger a batch job using multi-user service"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        import threading
        def run_batch_job():
            try:
                result = batch_service.run_price_sync_job(created_by_user_id=user_id)
                print(f"🎉 Batch job completed: {result}")
            except Exception as e:
                print(f"❌ Batch job failed: {e}")
        
        thread = threading.Thread(target=run_batch_job)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'message': 'Multi-user batch job started successfully',
            'status': 'running',
            'note': 'Check /api/batch-job-status for progress',
            'user_id': user_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/batch-job-status')
@require_auth 
def batch_job_status():
    """Get status of recent batch jobs using multi-user service"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Use multi-user batch service to get status
        status_data = batch_service.get_batch_job_status(limit=5)
        
        return jsonify(status_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =========================================================================
# ANALYSIS ROUTES
# =========================================================================

@app.route('/api/statistical-analysis')
@require_auth
def statistical_analysis():
    """Get statistical analysis for user's portfolio"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Get user portfolio data
        portfolio_data = csv_service.get_user_portfolio_data(user_id)
        
        if not portfolio_data.get('success') or not portfolio_data.get('holdings'):
            return jsonify({
                'error': 'No portfolio data available for analysis',
                'recommendations': []
            })
        
        # Initialize statistical analyzer
        analyzer = StatisticalAnalysisService()
        analysis = analyzer.analyze_portfolio(portfolio_data['holdings'])
        
        return jsonify({
            'success': True,
            'analysis': analysis,
            'portfolio_summary': portfolio_data.get('summary', {})
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =========================================================================
# APPLICATION STARTUP
# =========================================================================

if __name__ == '__main__':
    init_db()
    
    # Set environment variables for API keys
    os.environ.setdefault('ALPHA_VANTAGE_API_KEY', '8TC1QT08BL9F04B1')
    os.environ.setdefault('FINNHUB_API_KEY', 'd2kfr9hr01qs23a239vgd2kfr9hr01qs23a23a00')
    
    print("🚀 Starting Multi-User Portfolio Analyzer...")
    print(f"📊 Database: {db_service.db_path}")
    print(f"🌐 Access: http://localhost:8080")
    
    app.run(host='0.0.0.0', port=8080, debug=True)