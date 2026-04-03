-- AMO ClickHouse schema — initial migration
-- Run against the 'amo' database.

CREATE DATABASE IF NOT EXISTS amo;

-- ---------------------------------------------------------------------------
-- spans table — the core trace store
--
-- Design notes:
--   - org_id is the leading ORDER BY key so per-tenant queries skip irrelevant
--     granules without needing separate tables per tenant.
--   - ReplicatedMergeTree is used even in single-node MVP so scaling out later
--     requires only infrastructure changes, not schema migrations.
--   - TTL: raw spans deleted after 90 days (configurable via env). TimescaleDB
--     continuous aggregates preserve rolled-up metrics longer.
--   - parent_span_id is Nullable — root spans have no parent.
--   - model, error_type, error_msg use LowCardinality or plain String depending
--     on expected cardinality.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS amo.spans
(
    org_id          LowCardinality(String),
    trace_id        UUID,
    span_id         UUID,
    parent_span_id  Nullable(UUID),
    timestamp       DateTime64(3, 'UTC'),
    framework       LowCardinality(String),
    agent_name      LowCardinality(String),
    action          String,
    status          LowCardinality(String),
    duration_ms     UInt32,
    input_tokens    UInt32,
    output_tokens   UInt32,
    cost_usd        Float32,
    model           LowCardinality(String),
    error_type      LowCardinality(String),
    error_msg       String,
    metadata        String  -- JSON blob
)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/amo/spans', '{replica}')
PARTITION BY toYYYYMM(timestamp)
ORDER BY (org_id, trace_id, timestamp)
TTL timestamp + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;


-- ---------------------------------------------------------------------------
-- Materialized view: per-trace cost and duration summary
-- Used by the API to serve trace-list pages without full table scans.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS amo.trace_summary
(
    org_id        LowCardinality(String),
    trace_id      UUID,
    agent_name    LowCardinality(String),
    framework     LowCardinality(String),
    started_at    DateTime64(3, 'UTC'),
    finished_at   DateTime64(3, 'UTC'),
    total_spans   UInt32,
    error_spans   UInt32,
    total_cost_usd Float64,
    total_duration_ms UInt64,
    status        LowCardinality(String)   -- "success" | "error" | "partial"
)
ENGINE = ReplicatedAggregatingMergeTree('/clickhouse/tables/{shard}/amo/trace_summary', '{replica}')
PARTITION BY toYYYYMM(started_at)
ORDER BY (org_id, trace_id)
TTL started_at + INTERVAL 90 DAY;

CREATE MATERIALIZED VIEW IF NOT EXISTS amo.trace_summary_mv
TO amo.trace_summary
AS
SELECT
    org_id,
    trace_id,
    any(agent_name)                     AS agent_name,
    any(framework)                      AS framework,
    min(timestamp)                      AS started_at,
    max(timestamp)                      AS finished_at,
    count()                             AS total_spans,
    countIf(status = 'error')           AS error_spans,
    sum(cost_usd)                       AS total_cost_usd,
    sum(duration_ms)                    AS total_duration_ms,
    if(countIf(status = 'error') > 0, 'error', 'success') AS status
FROM amo.spans
GROUP BY org_id, trace_id;
