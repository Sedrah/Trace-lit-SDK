-- AMO TimescaleDB initialisation — runs automatically on first container start.
-- Combines all migrations into one file for Docker entrypoint.

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ---------------------------------------------------------------------------
-- agent_metrics — time-series metrics per agent (from 001_initial.sql)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_metrics (
    time         TIMESTAMPTZ        NOT NULL,
    org_id       TEXT               NOT NULL,
    agent_name   TEXT               NOT NULL,
    metric_name  TEXT               NOT NULL,
    value        DOUBLE PRECISION   NOT NULL,
    framework    TEXT               NOT NULL
);

SELECT create_hypertable(
    'agent_metrics',
    'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_agent_metrics_org_agent_time
    ON agent_metrics (org_id, agent_name, time DESC);

CREATE INDEX IF NOT EXISTS idx_agent_metrics_org_metric_time
    ON agent_metrics (org_id, metric_name, time DESC);

-- Hourly continuous aggregate — powers "last 24 hours" dashboard view

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
    start_offset      => INTERVAL '3 days',
    end_offset        => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists     => TRUE
);

-- Daily continuous aggregate — powers "last 30 days" dashboard view

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
    start_offset      => INTERVAL '90 days',
    end_offset        => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists     => TRUE
);

-- ---------------------------------------------------------------------------
-- api_keys — hashed key → org_id mapping (from 001_initial.sql)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS api_keys (
    key_hash     TEXT        PRIMARY KEY,
    org_id       TEXT        NOT NULL,
    name         TEXT        NOT NULL,
    scopes       TEXT[]      NOT NULL DEFAULT ARRAY['read', 'write'],
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_api_keys_org_id ON api_keys (org_id);

-- ---------------------------------------------------------------------------
-- alert_rules — per-org alert configurations (from 002_alert_rules.sql)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS alert_rules (
    id              SERIAL           PRIMARY KEY,
    org_id          TEXT             NOT NULL,
    name            TEXT             NOT NULL,
    agent_name      TEXT,
    metric          TEXT             NOT NULL,
    threshold       DOUBLE PRECISION NOT NULL,
    window_minutes  INTEGER          NOT NULL DEFAULT 60,
    channel         TEXT             NOT NULL,
    webhook_url     TEXT             NOT NULL,
    enabled         BOOLEAN          NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ      NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_rules_org_id ON alert_rules (org_id);
CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules (org_id, enabled) WHERE enabled = TRUE;
