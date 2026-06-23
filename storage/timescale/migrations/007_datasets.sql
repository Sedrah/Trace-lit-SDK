-- Migration 007: Dataset builder
-- datasets — named collections of labeled spans
-- dataset_items — individual span examples with label + snapshot of span fields

CREATE TABLE IF NOT EXISTS datasets (
    id          UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    org_id      TEXT        NOT NULL,
    name        TEXT        NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, name)
);

CREATE INDEX IF NOT EXISTS idx_datasets_org_id ON datasets (org_id);

CREATE TABLE IF NOT EXISTS dataset_items (
    id          UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    dataset_id  UUID        NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    org_id      TEXT        NOT NULL,
    trace_id    TEXT        NOT NULL,
    span_id     TEXT        NOT NULL,
    label       TEXT        NOT NULL CHECK (label IN ('good', 'bad', 'neutral')),
    notes       TEXT,
    -- Snapshot of span fields at tagging time so export is self-contained
    agent_name  TEXT,
    action      TEXT,
    model       TEXT,
    input_text  TEXT,
    output_text TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (dataset_id, span_id)
);

CREATE INDEX IF NOT EXISTS idx_dataset_items_dataset_id ON dataset_items (dataset_id);
CREATE INDEX IF NOT EXISTS idx_dataset_items_org_id     ON dataset_items (org_id);
