-- AMO ClickHouse schema — prompt versioning
-- Run against the 'trace_lit' database (after 001_initial.sql).
--
-- Design notes:
--   - Versioning is content-addressed: the ingestion pipeline hashes prompt
--     content (sha256, first 12 hex chars) and auto-assigns the next
--     sequential version number per (org_id, prompt_name) the first time a
--     hash is seen. No manual version tagging required from the SDK caller.
--   - spans carries only prompt_name/prompt_hash/prompt_version (lightweight,
--     denormalized for fast filtering) — the full prompt text lives once in
--     prompt_versions, never duplicated per span.

ALTER TABLE trace_lit.spans
    ADD COLUMN IF NOT EXISTS prompt_name    LowCardinality(String) DEFAULT '',
    ADD COLUMN IF NOT EXISTS prompt_hash    String DEFAULT '',
    ADD COLUMN IF NOT EXISTS prompt_version UInt32 DEFAULT 0;

CREATE TABLE IF NOT EXISTS trace_lit.prompt_versions
(
    org_id        LowCardinality(String),
    prompt_name   LowCardinality(String),
    prompt_hash   String,
    version       UInt32,
    content       String,
    first_seen_at DateTime64(3, 'UTC')
)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/amo/prompt_versions', '{replica}')
ORDER BY (org_id, prompt_name, version)
SETTINGS index_granularity = 8192;
