-- Pending email verifications for self-service sign-up.
-- Row is deleted once the user verifies their email and the API key is issued.
CREATE TABLE IF NOT EXISTS pending_signups (
    id         SERIAL PRIMARY KEY,
    email      TEXT        NOT NULL UNIQUE,
    org_id     TEXT        NOT NULL,
    token      TEXT        NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours'
);

CREATE INDEX IF NOT EXISTS pending_signups_token_idx ON pending_signups (token);
