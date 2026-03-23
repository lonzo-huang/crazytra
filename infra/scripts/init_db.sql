-- TimescaleDB initialization for trading system
-- Run once on first startup

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ── Market ticks (time-series) ──────────────────────────────
CREATE TABLE IF NOT EXISTS market_ticks (
    time         TIMESTAMPTZ     NOT NULL,
    symbol       TEXT            NOT NULL,
    exchange     TEXT            NOT NULL,
    bid          NUMERIC(20, 8)  NOT NULL,
    ask          NUMERIC(20, 8)  NOT NULL,
    last         NUMERIC(20, 8)  NOT NULL,
    bid_size     NUMERIC(20, 8)  DEFAULT 0,
    ask_size     NUMERIC(20, 8)  DEFAULT 0,
    volume_24h   NUMERIC(24, 4)  DEFAULT 0,
    latency_us   BIGINT          DEFAULT 0
);

SELECT create_hypertable('market_ticks', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_ticks_symbol_time
    ON market_ticks (symbol, time DESC);

-- Compression: keep raw data for 7 days, compress after
SELECT add_compression_policy('market_ticks',
    compress_after => INTERVAL '7 days',
    if_not_exists => TRUE);

-- Retention: drop chunks older than 90 days
SELECT add_retention_policy('market_ticks',
    drop_after => INTERVAL '90 days',
    if_not_exists => TRUE);

-- ── Strategy signals ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS strategy_signals (
    time         TIMESTAMPTZ  NOT NULL,
    signal_id    UUID         NOT NULL,
    strategy_id  TEXT         NOT NULL,
    symbol       TEXT         NOT NULL,
    direction    TEXT         NOT NULL,
    strength     FLOAT        NOT NULL,
    confidence   FLOAT        NOT NULL,
    reason       TEXT,
    ttl_ms       INT
);

SELECT create_hypertable('strategy_signals', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- ── Orders ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    time         TIMESTAMPTZ  NOT NULL,
    order_id     UUID         NOT NULL PRIMARY KEY,
    signal_id    UUID,
    symbol       TEXT         NOT NULL,
    direction    TEXT         NOT NULL,
    quantity     NUMERIC(20, 8),
    fill_price   NUMERIC(20, 8),
    fill_qty     NUMERIC(20, 8),
    fee          NUMERIC(20, 8) DEFAULT 0,
    status       TEXT         NOT NULL,
    mode         TEXT         NOT NULL DEFAULT 'paper'
);

SELECT create_hypertable('orders', 'time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE);

-- ── LLM weights ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS llm_weights (
    time         TIMESTAMPTZ  NOT NULL,
    symbol       TEXT         NOT NULL,
    llm_score    FLOAT        NOT NULL,
    confidence   FLOAT        NOT NULL,
    horizon      TEXT,
    key_drivers  TEXT[],
    model_used   TEXT
);

SELECT create_hypertable('llm_weights', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- ── Risk alerts ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS risk_alerts (
    time      TIMESTAMPTZ NOT NULL,
    alert_id  UUID        NOT NULL,
    kind      TEXT        NOT NULL,
    symbol    TEXT,
    message   TEXT,
    severity  TEXT        NOT NULL
);

SELECT create_hypertable('risk_alerts', 'time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE);

-- ── Continuous aggregates (1-min OHLCV) ─────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS ticks_1m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    symbol,
    FIRST(bid, time)             AS open,
    MAX(ask)                     AS high,
    MIN(bid)                     AS low,
    LAST(last, time)             AS close,
    SUM(volume_24h)              AS volume
FROM market_ticks
GROUP BY bucket, symbol
WITH NO DATA;

SELECT add_continuous_aggregate_policy('ticks_1m',
    start_offset => INTERVAL '2 hours',
    end_offset   => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO trader;
