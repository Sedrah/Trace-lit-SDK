-- Alert rules table — stores per-org alert configurations.
-- Run after 001_initial.sql.

CREATE TABLE IF NOT EXISTS alert_rules (
    id              SERIAL          PRIMARY KEY,
    org_id          TEXT            NOT NULL,
    name            TEXT            NOT NULL,
    agent_name      TEXT,                       -- NULL = applies to all agents
    metric          TEXT            NOT NULL,   -- "cost_usd" | "error_rate" | "duration_ms"
    threshold       DOUBLE PRECISION NOT NULL,
    window_minutes  INTEGER         NOT NULL DEFAULT 60,
    channel         TEXT            NOT NULL,   -- "slack" | "webhook"
    webhook_url     TEXT            NOT NULL,
    enabled         BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_rules_org_id ON alert_rules (org_id);
CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules (org_id, enabled) WHERE enabled = TRUE;
