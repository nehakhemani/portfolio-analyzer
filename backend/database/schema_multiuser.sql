-- Multi-User Portfolio Analyzer Database Schema
-- Designed for scalable multi-user architecture with shared ticker price data

-- Table 1: Users - User management and authentication
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    timezone VARCHAR(50) DEFAULT 'UTC',
    currency VARCHAR(3) DEFAULT 'USD'
);

-- Table 2: Tickers - Shared ticker data and prices (updated by batch jobs)
CREATE TABLE IF NOT EXISTS tickers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker_symbol VARCHAR(20) UNIQUE NOT NULL,
    company_name VARCHAR(200),
    exchange VARCHAR(20),
    currency VARCHAR(3) DEFAULT 'USD',
    current_price DECIMAL(15,4),
    price_updated_at TIMESTAMP,
    price_source VARCHAR(50),
    last_fetch_attempt TIMESTAMP,
    fetch_success BOOLEAN DEFAULT 0,
    market_cap DECIMAL(20,2),
    sector VARCHAR(100),
    industry VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);

-- Table 3: User Portfolios - User-specific portfolio holdings
CREATE TABLE IF NOT EXISTS user_portfolios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    ticker_id INTEGER NOT NULL,
    quantity DECIMAL(15,8) NOT NULL,
    average_cost DECIMAL(15,4) NOT NULL,
    total_cost DECIMAL(15,2) NOT NULL,
    purchase_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (ticker_id) REFERENCES tickers(id) ON DELETE CASCADE,
    UNIQUE(user_id, ticker_id)
);

-- Table 4: User Transactions - Detailed transaction history
CREATE TABLE IF NOT EXISTS user_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    ticker_id INTEGER NOT NULL,
    transaction_type VARCHAR(20) NOT NULL, -- 'BUY', 'SELL', 'DIVIDEND'
    quantity DECIMAL(15,8) NOT NULL,
    price DECIMAL(15,4) NOT NULL,
    total_amount DECIMAL(15,2) NOT NULL,
    fees DECIMAL(10,2) DEFAULT 0,
    transaction_date DATE NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (ticker_id) REFERENCES tickers(id) ON DELETE CASCADE
);

-- Table 5: Batch Jobs - Track batch job execution (system-wide)
CREATE TABLE IF NOT EXISTS batch_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type VARCHAR(50) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status VARCHAR(20) NOT NULL, -- 'running', 'completed', 'failed'
    tickers_processed INTEGER DEFAULT 0,
    tickers_successful INTEGER DEFAULT 0,
    success_rate DECIMAL(5,2) DEFAULT 0,
    error_log TEXT,
    created_by_user_id INTEGER,
    FOREIGN KEY (created_by_user_id) REFERENCES users(id)
);

-- Table 6: User Sessions - Track user login sessions
CREATE TABLE IF NOT EXISTS user_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_tickers_symbol ON tickers(ticker_symbol);
CREATE INDEX IF NOT EXISTS idx_tickers_price_updated ON tickers(price_updated_at);
CREATE INDEX IF NOT EXISTS idx_user_portfolios_user_id ON user_portfolios(user_id);
CREATE INDEX IF NOT EXISTS idx_user_portfolios_ticker_id ON user_portfolios(ticker_id);
CREATE INDEX IF NOT EXISTS idx_user_transactions_user_id ON user_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_transactions_date ON user_transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_status ON batch_jobs(status);
CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);

-- Views for common queries
CREATE VIEW IF NOT EXISTS user_portfolio_summary AS
SELECT 
    u.id as user_id,
    u.username,
    COUNT(up.id) as total_positions,
    SUM(up.total_cost) as total_investment,
    SUM(CASE 
        WHEN t.current_price IS NOT NULL 
        THEN up.quantity * t.current_price 
        ELSE up.total_cost 
    END) as current_value,
    SUM(CASE 
        WHEN t.current_price IS NOT NULL 
        THEN (up.quantity * t.current_price) - up.total_cost
        ELSE 0 
    END) as unrealized_pnl
FROM users u
LEFT JOIN user_portfolios up ON u.id = up.user_id AND up.is_active = 1
LEFT JOIN tickers t ON up.ticker_id = t.id
WHERE u.is_active = 1
GROUP BY u.id, u.username;

CREATE VIEW IF NOT EXISTS user_portfolio_details AS
SELECT 
    u.id as user_id,
    u.username,
    t.ticker_symbol,
    t.company_name,
    t.exchange,
    t.current_price,
    t.price_updated_at,
    t.price_source,
    up.quantity,
    up.average_cost,
    up.total_cost,
    CASE 
        WHEN t.current_price IS NOT NULL 
        THEN up.quantity * t.current_price 
        ELSE NULL 
    END as current_value,
    CASE 
        WHEN t.current_price IS NOT NULL 
        THEN ((up.quantity * t.current_price) - up.total_cost)
        ELSE NULL 
    END as unrealized_pnl,
    CASE 
        WHEN t.current_price IS NOT NULL AND up.total_cost > 0
        THEN (((up.quantity * t.current_price) - up.total_cost) / up.total_cost * 100)
        ELSE NULL 
    END as return_percentage,
    up.created_at as position_created_at
FROM users u
JOIN user_portfolios up ON u.id = up.user_id AND up.is_active = 1
JOIN tickers t ON up.ticker_id = t.id
WHERE u.is_active = 1 AND up.quantity > 0;