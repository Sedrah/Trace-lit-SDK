-- Migration 008: Eval runs
-- Stores the result of each CI quality gate evaluation.

CREATE TABLE IF NOT EXISTS eval_runs (
    id               UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    org_id           TEXT        NOT NULL,
    dataset_id       UUID        REFERENCES datasets(id) ON DELETE SET NULL,
    prompt_name      TEXT        NOT NULL,
    prompt_version   INT         NOT NULL,
    baseline_version INT,                  -- NULL = used dataset good-label baseline
    status           TEXT        NOT NULL CHECK (status IN ('passed', 'failed', 'error')),
    score            FLOAT       NOT NULL, -- 0.0–1.0
    threshold        FLOAT       NOT NULL DEFAULT 0.8,
    new_spans        INT         NOT NULL DEFAULT 0,
    baseline_spans   INT         NOT NULL DEFAULT 0,
    error_rate_new   FLOAT,
    error_rate_base  FLOAT,
    cost_new         FLOAT,
    cost_base        FLOAT,
    duration_new     FLOAT,
    duration_base    FLOAT,
    message          TEXT,                 -- human-readable summary
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eval_runs_org_id    ON eval_runs (org_id);
CREATE INDEX IF NOT EXISTS idx_eval_runs_dataset   ON eval_runs (dataset_id);
CREATE INDEX IF NOT EXISTS idx_eval_runs_prompt    ON eval_runs (org_id, prompt_name, prompt_version);
