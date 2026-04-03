-- AMO TimescaleDB schema — initial migration
-- Run against the 'amo' database as a superuser (or a user with CREATEDATABASE).

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ---------------------------------------------------------------------------
-- agent_metrics — time-series metrics per agent
--
-- Design notes:
--   - org_id is present on every row and indexed first for per-tenant queries.
--   - One row per span per metric type. TimescaleDB continuous aggregates
--     roll these up hourly and daily so dashboard queries stay fast.
--   - metric_name is a small fixed set: call_count, duration_ms, cost_usd,
--     error_count. This is intentionally narrow — detailed per-span data lives
--     in ClickHouse; this table is for time-series charting only.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_metrics (
    time         TIMESTAMPTZ        NOT NULL,
    org_id       TEXT               NOT NULL,
    agent_name   TEXT               NOT NULL,
    metric_name  TEXT               NOT NULL,   -- "call_count" | "duration_ms" | "cost_usd" | "error_count"
    value        DOUBLE PRECISION   NOT NULL,
    framework    TEXT               NOT NULL
);

SELECT create_hypertable(
    'agent_metrics',
    'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists       => TRUE
);

-- Index for fast per-tenant, per-agent time-range queries
CREATE INDEX IF NOT EXISTS idx_agent_metrics_org_agent_time
    ON agent_metrics (org_id, agent_name, time DESC);

CREATE INDEX IF NOT EXISTS idx_agent_metrics_org_metric_time
    ON agent_metrics (org_id, metric_name, time DESC);


-- ---------------------------------------------------------------------------
-- Continuous aggregate: hourly rollup
-- Powers the "last 24 hours" view in the dashboard.
-- ---------------------------------------------------------------------------

CREATE MATERIALIZED VIEW IF NOT EXISTS agent_metrics_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time)  AS bucket,
    org_id,
    agent_name,
    metric_name,
    framework,
    sum(value)                   AS total,
    count(*)                     AS sample_count,
    avg(value)                   AS avg_value,
    max(value)                   AS max_value
FROM agent_metrics
GROUP BY bucket, org_id, agent_name, metric_name, framework
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
    'agent_metrics_hourly',
    start_offset  => INTERVAL '3 days',
    end_offset    => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);


-- ---------------------------------------------------------------------------
-- Continuous aggregate: daily rollup
-- Powers the "last 30 days" view in the dashboard.
-- ---------------------------------------------------------------------------

CREATE MATERIALIZED VIEW IF NOT EXISTS agent_metrics_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time)   AS bucket,
    org_id,
    agent_name,
    metric_name,
    framework,
    sum(value)                   AS total,
    count(*)                     AS sample_count,
    avg(value)                   AS avg_value,
    max(value)                   AS max_value
FROM agent_metrics
GROUP BY bucket, org_id, agent_name, metric_name, framework
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
    'agent_metrics_daily',
    start_offset  => INTERVAL '90 days',
    end_offset    => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);


-- ---------------------------------------------------------------------------
-- api_keys table — stores hashed API keys with org_id mapping
-- Used by the REST API for auth and by the pipeline for org_id resolution
-- (in SaaS mode when AMO_API_KEYS env var is replaced by DB lookup).
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS api_keys (
    key_hash     TEXT        PRIMARY KEY,   -- bcrypt hash, never plaintext
    org_id       TEXT        NOT NULL,
    name         TEXT        NOT NULL,      -- human label, e.g. "production"
    scopes       TEXT[]      NOT NULL DEFAULT ARRAY['read', 'write'],
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at   TIMESTAMPTZ             -- NULL = never expires
);

CREATE INDEX IF NOT EXISTS idx_api_keys_org_id ON api_keys (org_id);
