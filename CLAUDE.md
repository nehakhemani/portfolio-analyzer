# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Running the Application
- **Main server**: `cd backend && python app.py` (runs on http://localhost:5000)
- **Alternative server**: `cd backend && python run_server.py`
- **Setup**: `python setup.py` (creates directories, installs dependencies, creates .env)

### Dependencies
- **Install Python requirements**: `pip install -r backend/requirements.txt`
- **Main dependencies**: Flask 2.3.2, Flask-CORS, pandas, numpy, yfinance, sqlite3

### Database
- SQLite database located at `backend/data/portfolio.db`
- Database initialized automatically on first run
- Contains `holdings` and `market_data` tables

## Architecture

### Project Structure
```
Portfolio-analyzer_app/
├── backend/           # Python Flask API server
│   ├── app.py        # Main Flask application with all routes
│   ├── run_server.py # Alternative server runner
│   ├── services/     # Business logic modules
│   ├── utils/        # Utility functions (CSV parsing)
│   └── data/         # SQLite database storage
├── frontend/         # Static web interface
│   ├── index.html    # Single-page application
│   ├── css/style.css # Styling
│   └── js/app.js     # Frontend JavaScript
└── uploads/          # CSV file upload directory
```

### Core Components

**Backend Services:**
- `MarketDataService` (market_data.py): Fetches stock data from Yahoo Finance with caching
- `PortfolioAnalyzer` (analysis.py): Calculates returns, risk metrics, concentration analysis
- `RecommendationEngine` (recommendations.py): Generates buy/hold/sell recommendations
- `MLRecommendationEngine` (ml_recommendations.py): ML-powered recommendations
- `CSVParser` (csv_parser.py): Parses portfolio CSV uploads with specific column mapping

**Frontend:**
- Single-page application using vanilla JavaScript, Chart.js for visualizations
- Communicates with backend via REST API calls using axios

### API Endpoints
- `GET /api/portfolio` - Retrieve portfolio holdings and summary
- `POST /api/upload` - Upload portfolio CSV file
- `GET /api/market-data` - Fetch current market data for holdings
- `GET /api/recommendations` - Generate stock recommendations
- `GET /api/ml-recommendations` - ML-enhanced recommendations
- `GET /api/analysis` - Detailed portfolio analysis with risk assessment
- `GET /api/export` - Export portfolio data (CSV/JSON)
- `POST /api/add-holding` - Add single holding
- `DELETE /api/delete-holding/<ticker>` - Remove holding

### Data Flow
1. User uploads CSV or adds holdings manually
2. Data stored in SQLite `holdings` table with standardized schema
3. Market data fetched from Yahoo Finance and cached (5min duration)
4. Analysis engine calculates metrics, risk assessment, and performance
5. Recommendation engines provide investment advice
6. Frontend displays results with charts and tables

### CSV Format Expected
The CSV parser expects columns:
- Investment ticker symbol → ticker
- Exchange → exchange  
- Currency → currency
- Starting investment dollar value → start_value
- Ending investment dollar value → end_value
- Starting share price → start_price
- Ending share price → end_price
- Dividends and distributions → dividends
- Transaction fees → fees