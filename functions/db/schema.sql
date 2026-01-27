-- ============================================================================
-- Option Chain Dashboard Database Schema
-- ============================================================================
-- This schema defines the complete data model for the option chain dashboard
-- including scan metadata, feature tracking, chain history, alerts, and trades.
-- ============================================================================

-- ============================================================================
-- SCHEMA VERSION TRACKING
-- ============================================================================
-- Tracks database migrations and schema versions
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description TEXT NOT NULL
);

-- ============================================================================
-- SCAN METADATA
-- ============================================================================
-- Stores metadata about each scan operation
CREATE SEQUENCE IF NOT EXISTS scans_id_seq START 1;

CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY DEFAULT nextval('scans_id_seq'),
    scan_ts TIMESTAMP WITH TIME ZONE NOT NULL,
    config_hash VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed', 'partial')),
    tickers_scanned INTEGER,
    alerts_generated INTEGER DEFAULT 0,
    chains_collected INTEGER DEFAULT 0,
    runtime_seconds DECIMAL(10, 2),
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_scans_scan_ts ON scans(scan_ts DESC);
CREATE INDEX IF NOT EXISTS idx_scans_status ON scans(status);
CREATE INDEX IF NOT EXISTS idx_scans_created_at ON scans(created_at DESC);

-- ============================================================================
-- FEATURE SNAPSHOTS
-- ============================================================================
-- Stores computed features for each ticker in each scan
CREATE SEQUENCE IF NOT EXISTS feature_snapshots_id_seq START 1;

CREATE TABLE IF NOT EXISTS feature_snapshots (
    id INTEGER PRIMARY KEY DEFAULT nextval('feature_snapshots_id_seq'),
    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    features JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feature_snapshots_scan_id ON feature_snapshots(scan_id);
CREATE INDEX IF NOT EXISTS idx_feature_snapshots_ticker ON feature_snapshots(ticker);
CREATE INDEX IF NOT EXISTS idx_feature_snapshots_scan_ticker ON feature_snapshots(scan_id, ticker);
CREATE INDEX IF NOT EXISTS idx_feature_snapshots_created_at ON feature_snapshots(created_at DESC);

-- ============================================================================
-- CHAIN SNAPSHOTS
-- ============================================================================
-- Stores complete option chain snapshots with full option data
CREATE SEQUENCE IF NOT EXISTS chain_snapshots_id_seq START 1;

CREATE TABLE IF NOT EXISTS chain_snapshots (
    id INTEGER PRIMARY KEY DEFAULT nextval('chain_snapshots_id_seq'),
    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    snapshot_date DATE NOT NULL,
    expiration DATE NOT NULL,
    dte INTEGER NOT NULL,
    underlying_price DECIMAL(12, 4) NOT NULL,
    chain_json JSONB NOT NULL,
    num_calls INTEGER,
    num_puts INTEGER,
    atm_iv DECIMAL(8, 4),
    total_volume BIGINT,
    total_oi BIGINT,
    file_path TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, snapshot_date, expiration)
);

CREATE INDEX IF NOT EXISTS idx_chain_snapshots_scan_id ON chain_snapshots(scan_id);
CREATE INDEX IF NOT EXISTS idx_chain_snapshots_ticker ON chain_snapshots(ticker);
CREATE INDEX IF NOT EXISTS idx_chain_snapshots_snapshot_date ON chain_snapshots(snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_chain_snapshots_expiration ON chain_snapshots(expiration);
CREATE INDEX IF NOT EXISTS idx_chain_snapshots_ticker_expiration ON chain_snapshots(ticker, expiration);
CREATE INDEX IF NOT EXISTS idx_chain_snapshots_created_at ON chain_snapshots(created_at DESC);

-- ============================================================================
-- ALERTS
-- ============================================================================
-- Stores generated alerts from various detection strategies
CREATE SEQUENCE IF NOT EXISTS alerts_id_seq START 1;

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY DEFAULT nextval('alerts_id_seq'),
    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    detector_name VARCHAR(100) NOT NULL,
    score DECIMAL(8, 4) NOT NULL,
    strategies JSONB,
    alert_json JSONB NOT NULL,
    sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alerts_scan_id ON alerts(scan_id);
CREATE INDEX IF NOT EXISTS idx_alerts_ticker ON alerts(ticker);
CREATE INDEX IF NOT EXISTS idx_alerts_detector_name ON alerts(detector_name);
CREATE INDEX IF NOT EXISTS idx_alerts_score ON alerts(score DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_sent ON alerts(sent);
CREATE INDEX IF NOT EXISTS idx_alerts_ticker_detector ON alerts(ticker, detector_name);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at DESC);

-- ============================================================================
-- IV HISTORY
-- ============================================================================
-- Tracks daily implied volatility and historical volatility metrics
CREATE SEQUENCE IF NOT EXISTS iv_history_id_seq START 1;

CREATE TABLE IF NOT EXISTS iv_history (
    id INTEGER PRIMARY KEY DEFAULT nextval('iv_history_id_seq'),
    ticker VARCHAR(20) NOT NULL,
    record_date DATE NOT NULL,
    atm_iv_front DECIMAL(8, 4),
    atm_iv_back DECIMAL(8, 4),
    hv_20 DECIMAL(8, 4),
    hv_60 DECIMAL(8, 4),
    iv_percentile DECIMAL(5, 2),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, record_date)
);

CREATE INDEX IF NOT EXISTS idx_iv_history_ticker ON iv_history(ticker);
CREATE INDEX IF NOT EXISTS idx_iv_history_record_date ON iv_history(record_date DESC);
CREATE INDEX IF NOT EXISTS idx_iv_history_ticker_date ON iv_history(ticker, record_date DESC);
CREATE INDEX IF NOT EXISTS idx_iv_history_created_at ON iv_history(created_at DESC);

-- ============================================================================
-- ALERT COOLDOWNS
-- ============================================================================
-- Per-ticker alert throttling to prevent alert spam
CREATE TABLE IF NOT EXISTS alert_cooldowns (
    ticker VARCHAR(20) PRIMARY KEY,
    last_alert_ts TIMESTAMP WITH TIME ZONE,
    last_score DECIMAL(8, 4)
);

CREATE INDEX IF NOT EXISTS idx_alert_cooldowns_last_alert_ts ON alert_cooldowns(last_alert_ts);

-- ============================================================================
-- DAILY ALERT COUNTS
-- ============================================================================
-- Tracks daily alert generation for rate limiting
CREATE TABLE IF NOT EXISTS daily_alert_counts (
    count_date DATE PRIMARY KEY,
    alert_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_daily_alert_counts_date ON daily_alert_counts(count_date DESC);

-- ============================================================================
-- TRANSACTIONS
-- ============================================================================
-- Stores trade transactions from broker exports
CREATE SEQUENCE IF NOT EXISTS transactions_id_seq START 1;

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY DEFAULT nextval('transactions_id_seq'),
    tx_date DATE NOT NULL,
    account VARCHAR(100),
    description TEXT,
    transaction_type VARCHAR(50),
    symbol VARCHAR(20),
    quantity DECIMAL(12, 4),
    price DECIMAL(12, 4),
    gross_amount DECIMAL(14, 2),
    commission DECIMAL(14, 2),
    net_amount DECIMAL(14, 2),
    multiplier INTEGER,
    sub_type VARCHAR(50),
    exchange_rate DECIMAL(10, 4),
    transaction_fees DECIMAL(14, 2),
    currency VARCHAR(3),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transactions_tx_date ON transactions(tx_date DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_symbol ON transactions(symbol);
CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions(account);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(transaction_type);
CREATE INDEX IF NOT EXISTS idx_transactions_tx_date_symbol ON transactions(tx_date DESC, symbol);
CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at DESC);

-- ============================================================================
-- SCHEDULER STATE
-- ============================================================================
-- Maintains scheduler state machine and API rate limiting
CREATE TABLE IF NOT EXISTS scheduler_state (
    id INTEGER PRIMARY KEY DEFAULT 1,
    current_state VARCHAR(50) NOT NULL DEFAULT 'idle' CHECK (current_state IN ('idle', 'collecting', 'processing', 'waiting', 'error')),
    last_collection_ts TIMESTAMP WITH TIME ZONE,
    next_collection_ts TIMESTAMP WITH TIME ZONE,
    api_calls_today INTEGER DEFAULT 0,
    api_calls_this_hour INTEGER DEFAULT 0,
    hour_window_start TIMESTAMP WITH TIME ZONE,
    consecutive_failures INTEGER DEFAULT 0,
    backoff_until TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Ensure only one row exists
CREATE UNIQUE INDEX IF NOT EXISTS idx_scheduler_state_singleton ON scheduler_state(id);

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Latest scan summary
CREATE OR REPLACE VIEW v_latest_scan AS
SELECT
    id,
    scan_ts,
    status,
    tickers_scanned,
    alerts_generated,
    chains_collected,
    runtime_seconds,
    error_message,
    created_at
FROM scans
ORDER BY scan_ts DESC
LIMIT 1;

-- Recent alerts with scan context
CREATE OR REPLACE VIEW v_recent_alerts AS
SELECT
    a.id,
    a.scan_id,
    s.scan_ts,
    a.ticker,
    a.detector_name,
    a.score,
    a.sent,
    a.created_at
FROM alerts a
INNER JOIN scans s ON a.scan_id = s.id
ORDER BY a.created_at DESC
LIMIT 100;

-- Scan statistics
CREATE OR REPLACE VIEW v_scan_statistics AS
SELECT
    DATE_TRUNC('day', scan_ts)::DATE as scan_day,
    COUNT(*) as total_scans,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_scans,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_scans,
    AVG(runtime_seconds) as avg_runtime_seconds,
    AVG(tickers_scanned) as avg_tickers_scanned,
    AVG(alerts_generated) as avg_alerts_generated
FROM scans
GROUP BY DATE_TRUNC('day', scan_ts)
ORDER BY scan_day DESC;

-- IV percentile by ticker (latest)
CREATE OR REPLACE VIEW v_latest_iv AS
SELECT DISTINCT ON (ticker)
    ticker,
    record_date,
    atm_iv_front,
    atm_iv_back,
    hv_20,
    hv_60,
    iv_percentile
FROM iv_history
ORDER BY ticker, record_date DESC;

-- Daily transaction summary
CREATE OR REPLACE VIEW v_daily_transactions AS
SELECT
    tx_date,
    symbol,
    SUM(CASE WHEN transaction_type = 'BUY' THEN quantity ELSE -quantity END) as net_quantity,
    COUNT(*) as transaction_count,
    SUM(net_amount) as total_net_amount
FROM transactions
GROUP BY tx_date, symbol
ORDER BY tx_date DESC, symbol;

-- ============================================================================
-- INITIALIZATION
-- ============================================================================
-- Insert initial schema version
INSERT INTO schema_version (version, description)
VALUES (1, 'Initial schema creation with all core tables')
ON CONFLICT (version) DO NOTHING;

-- Initialize scheduler state if not exists
INSERT INTO scheduler_state (id, current_state)
VALUES (1, 'idle')
ON CONFLICT (id) DO NOTHING;
