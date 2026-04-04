-- AMO ClickHouse initialisation — runs automatically on first container start.
-- The entrypoint script runs as the default user before ClickHouse starts
-- accepting connections, so we use the native SQL init mechanism.

CREATE DATABASE IF NOT EXISTS amo;

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
    metadata        String
)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/amo/spans', '{replica}')
PARTITION BY toYYYYMM(timestamp)
ORDER BY (org_id, trace_id, timestamp)
TTL timestamp + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS amo.trace_summary
(
    org_id              LowCardinality(String),
    trace_id            UUID,
    agent_name          LowCardinality(String),
    framework           LowCardinality(String),
    started_at          DateTime64(3, 'UTC'),
    finished_at         DateTime64(3, 'UTC'),
    total_spans         UInt32,
    error_spans         UInt32,
    total_cost_usd      Float64,
    total_duration_ms   UInt64,
    status              LowCardinality(String)
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
    any(agent_name)                                         AS agent_name,
    any(framework)                                          AS framework,
    min(timestamp)                                          AS started_at,
    max(timestamp)                                          AS finished_at,
    count()                                                 AS total_spans,
    countIf(status = 'error')                               AS error_spans,
    sum(cost_usd)                                           AS total_cost_usd,
    sum(duration_ms)                                        AS total_duration_ms,
    if(countIf(status = 'error') > 0, 'error', 'success')  AS status
FROM amo.spans
GROUP BY org_id, trace_id;
