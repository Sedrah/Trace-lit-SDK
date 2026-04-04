-- AMO ClickHouse initialisation — runs automatically on first container start.

CREATE DATABASE IF NOT EXISTS amo;

-- ---------------------------------------------------------------------------
-- spans — core trace store
-- ReplicatedMergeTree used even on single node so scaling out later
-- requires only infra changes, no schema migrations.
-- macros.xml defines {shard}=1 and {replica}=1 for single-node mode.
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
    metadata        String
)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/amo/spans', '{replica}')
PARTITION BY toYYYYMM(timestamp)
ORDER BY (org_id, trace_id, timestamp)
-- toDateTime() cast required for DateTime64 TTL in ClickHouse 24.x
TTL toDateTime(timestamp) + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;
