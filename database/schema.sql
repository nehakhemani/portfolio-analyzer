-- PostgreSQL Database Schema for Portfolio Analyzer
-- Robust, scalable architecture with proper indexing and relationships

-- Users table for authentication and user management
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    last_login TIMESTAMP
);

-- Portfolio holdings table - core data structure
CREATE TABLE IF NOT EXISTS portfolio_holdings (
    holding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    exchange VARCHAR(10) DEFAULT 'NASDAQ',
    currency VARCHAR(5) DEFAULT 'USD',
    quantity DECIMAL(15, 6) NOT NULL CHECK (quantity >= 0),
    avg_cost_basis DECIMAL(15, 4) NOT NULL CHECK (avg_cost_basis >= 0),
    total_investment_value DECIMAL(15, 2) GENERATED ALWAYS AS (quantity * avg_cost_basis) STORED,
    current_price DECIMAL(15, 4), -- Updated by batch jobs and API calls
    current_value DECIMAL(15, 2) GENERATED ALWAYS AS (quantity * COALESCE(current_price, avg_cost_basis)) STORED,
    total_return DECIMAL(15, 2) GENERATED ALWAYS AS (current_value - total_investment_value) STORED,
    return_percentage DECIMAL(8, 4) GENERATED ALWAYS AS (
        CASE 
            WHEN total_investment_value > 0 THEN ((current_value - total_investment_value) / total_investment_value * 100)
            ELSE 0 
        END
    ) STORED,
    price_last_updated TIMESTAMP,
    price_source VARCHAR(20) DEFAULT 'manual', -- 'api', 'batch_job', 'manual', 'fallback'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    
    -- Indexes for performance
    UNIQUE(user_id, ticker), -- One holding per ticker per user
    INDEX idx_portfolio_user (user_id),
    INDEX idx_portfolio_ticker (ticker),
    INDEX idx_portfolio_price_updated (price_last_updated),
    INDEX idx_portfolio_active (user_id, is_active)
);

-- Transaction history table for detailed tracking
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    holding_id UUID REFERENCES portfolio_holdings(holding_id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    transaction_type VARCHAR(10) NOT NULL CHECK (transaction_type IN ('BUY', 'SELL', 'DIVIDEND', 'SPLIT', 'FEE')),
    quantity DECIMAL(15, 6) NOT NULL,
    price DECIMAL(15, 4) NOT NULL CHECK (price >= 0),
    total_amount DECIMAL(15, 2) GENERATED ALWAYS AS (ABS(quantity * price)) STORED,
    fees DECIMAL(15, 4) DEFAULT 0 CHECK (fees >= 0),
    currency VARCHAR(5) DEFAULT 'USD',
    trade_date DATE NOT NULL,
    settlement_date DATE,
    exchange VARCHAR(10),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes for performance
    INDEX idx_transactions_user (user_id),
    INDEX idx_transactions_ticker (ticker),
    INDEX idx_transactions_date (trade_date),
    INDEX idx_transactions_type (transaction_type),
    INDEX idx_transactions_holding (holding_id)
);

-- Price history table for tracking price movements and batch job results
CREATE TABLE IF NOT EXISTS price_history (
    price_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker VARCHAR(20) NOT NULL,
    price DECIMAL(15, 4) NOT NULL CHECK (price > 0),
    change_percent DECIMAL(8, 4),
    volume BIGINT,
    market_cap BIGINT,
    currency VARCHAR(5) DEFAULT 'USD',
    exchange VARCHAR(10),
    price_date DATE NOT NULL,
    price_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(20) NOT NULL DEFAULT 'batch_job', -- 'batch_job', 'api_call', 'manual', 'yahoo', 'alpha_vantage', 'finnhub'
    fetch_duration_ms INTEGER, -- Performance tracking
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure one price per ticker per date from each source
    UNIQUE(ticker, price_date, source),
    INDEX idx_price_history_ticker (ticker),
    INDEX idx_price_history_date (price_date),
    INDEX idx_price_history_ticker_date (ticker, price_date DESC),
    INDEX idx_price_history_source (source),
    INDEX idx_price_history_created (created_at DESC)
);

-- Manual price overrides table for user-set prices
CREATE TABLE IF NOT EXISTS manual_price_overrides (
    override_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    manual_price DECIMAL(15, 4) NOT NULL CHECK (manual_price > 0),
    currency VARCHAR(5) DEFAULT 'USD',
    set_date DATE DEFAULT CURRENT_DATE,
    expires_at TIMESTAMP, -- Optional expiration
    notes TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- One active manual override per user per ticker
    UNIQUE(user_id, ticker) WHERE is_active = true,
    INDEX idx_manual_overrides_user (user_id),
    INDEX idx_manual_overrides_ticker (ticker),
    INDEX idx_manual_overrides_active (user_id, is_active)
);

-- Batch job execution log for monitoring and debugging
CREATE TABLE IF NOT EXISTS batch_job_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_name VARCHAR(50) NOT NULL,
    job_type VARCHAR(20) NOT NULL, -- 'daily_prices', 'weekly_cleanup', 'monthly_analysis'
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'RUNNING', -- 'RUNNING', 'SUCCESS', 'FAILED', 'PARTIAL'
    tickers_processed INTEGER DEFAULT 0,
    tickers_succeeded INTEGER DEFAULT 0,
    tickers_failed INTEGER DEFAULT 0,
    error_message TEXT,
    execution_details JSONB, -- Store detailed logs, API responses, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_batch_logs_job_name (job_name),
    INDEX idx_batch_logs_start_time (start_time DESC),
    INDEX idx_batch_logs_status (status)
);

-- API usage tracking for rate limiting and monitoring
CREATE TABLE IF NOT EXISTS api_usage_tracking (
    usage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_source VARCHAR(20) NOT NULL, -- 'yahoo', 'alpha_vantage', 'finnhub'
    endpoint_type VARCHAR(30) NOT NULL, -- 'quote', 'batch_quote', 'historical'
    request_count INTEGER DEFAULT 1,
    response_status INTEGER, -- HTTP status code
    response_time_ms INTEGER,
    tickers_requested TEXT[], -- Array of tickers requested
    success_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    rate_limited BOOLEAN DEFAULT false,
    request_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_date DATE DEFAULT CURRENT_DATE,
    
    INDEX idx_api_usage_source (api_source),
    INDEX idx_api_usage_date (created_date),
    INDEX idx_api_usage_timestamp (request_timestamp DESC)
);

-- Create views for common queries
CREATE OR REPLACE VIEW portfolio_summary AS
SELECT 
    ph.user_id,
    COUNT(*) as total_holdings,
    SUM(ph.total_investment_value) as total_investment,
    SUM(ph.current_value) as total_current_value,
    SUM(ph.total_return) as total_return,
    AVG(ph.return_percentage) as avg_return_percentage,
    COUNT(*) FILTER (WHERE ph.current_price IS NOT NULL) as holdings_with_prices,
    COUNT(*) FILTER (WHERE ph.price_last_updated >= CURRENT_DATE) as holdings_updated_today
FROM portfolio_holdings ph
WHERE ph.is_active = true
GROUP BY ph.user_id;

CREATE OR REPLACE VIEW stale_prices AS
SELECT 
    ticker,
    COUNT(DISTINCT user_id) as users_affected,
    MAX(price_last_updated) as last_price_update,
    CURRENT_TIMESTAMP - MAX(price_last_updated) as staleness_duration
FROM portfolio_holdings
WHERE is_active = true 
  AND (price_last_updated < CURRENT_DATE - INTERVAL '1 day' OR price_last_updated IS NULL)
GROUP BY ticker
ORDER BY users_affected DESC, staleness_duration DESC;

-- Trigger to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_portfolio_updated_at BEFORE UPDATE ON portfolio_holdings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to get latest price for a ticker (considering manual overrides)
CREATE OR REPLACE FUNCTION get_latest_price(p_user_id UUID, p_ticker VARCHAR)
RETURNS TABLE(price DECIMAL, source VARCHAR, last_updated TIMESTAMP) AS $$
BEGIN
    -- First check for manual override
    RETURN QUERY
    SELECT 
        mpo.manual_price as price,
        'manual_override'::VARCHAR as source,
        mpo.created_at as last_updated
    FROM manual_price_overrides mpo
    WHERE mpo.user_id = p_user_id 
      AND mpo.ticker = p_ticker 
      AND mpo.is_active = true
      AND (mpo.expires_at IS NULL OR mpo.expires_at > CURRENT_TIMESTAMP)
    LIMIT 1;
    
    -- If no manual override, get from portfolio holdings
    IF NOT FOUND THEN
        RETURN QUERY
        SELECT 
            ph.current_price as price,
            ph.price_source::VARCHAR as source,
            ph.price_last_updated as last_updated
        FROM portfolio_holdings ph
        WHERE ph.user_id = p_user_id 
          AND ph.ticker = p_ticker 
          AND ph.is_active = true
          AND ph.current_price IS NOT NULL
        LIMIT 1;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to update portfolio holding price
CREATE OR REPLACE FUNCTION update_portfolio_price(
    p_user_id UUID, 
    p_ticker VARCHAR, 
    p_price DECIMAL, 
    p_source VARCHAR DEFAULT 'api'
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE portfolio_holdings 
    SET 
        current_price = p_price,
        price_last_updated = CURRENT_TIMESTAMP,
        price_source = p_source
    WHERE user_id = p_user_id 
      AND ticker = p_ticker 
      AND is_active = true;
    
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- Create indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_portfolio_return_percentage ON portfolio_holdings(return_percentage DESC) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_portfolio_current_value ON portfolio_holdings(current_value DESC) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_price_history_latest ON price_history(ticker, price_date DESC, created_at DESC);

-- Set up row-level security (optional, for multi-tenant security)
ALTER TABLE portfolio_holdings ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE manual_price_overrides ENABLE ROW LEVEL SECURITY;

-- Comment on tables and columns for documentation
COMMENT ON TABLE portfolio_holdings IS 'Core portfolio holdings with real-time calculated returns';
COMMENT ON TABLE transactions IS 'Complete transaction history for portfolio construction';
COMMENT ON TABLE price_history IS 'Historical price data from batch jobs and API calls';
COMMENT ON TABLE manual_price_overrides IS 'User-defined price overrides for manual pricing';
COMMENT ON TABLE batch_job_logs IS 'Execution logs for scheduled batch jobs';
COMMENT ON TABLE api_usage_tracking IS 'API usage monitoring and rate limiting data';

COMMENT ON COLUMN portfolio_holdings.total_investment_value IS 'Calculated: quantity * avg_cost_basis';
COMMENT ON COLUMN portfolio_holdings.current_value IS 'Calculated: quantity * current_price';
COMMENT ON COLUMN portfolio_holdings.total_return IS 'Calculated: current_value - total_investment_value';
COMMENT ON COLUMN portfolio_holdings.return_percentage IS 'Calculated: (total_return / total_investment_value) * 100';