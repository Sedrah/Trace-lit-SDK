-- User accounts and session-based auth for the dashboard.
-- API keys remain for SDK/pipeline use; sessions are for dashboard users.

CREATE TABLE IF NOT EXISTS users (
    id         SERIAL PRIMARY KEY,
    email      TEXT UNIQUE NOT NULL,
    org_id     TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS magic_links (
    id         SERIAL PRIMARY KEY,
    email      TEXT        NOT NULL,
    token      TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '15 minutes',
    used_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS magic_links_token_idx ON magic_links (token);

CREATE TABLE IF NOT EXISTS sessions (
    id         SERIAL PRIMARY KEY,
    user_id    INT         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id     TEXT        NOT NULL,
    token_hash TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '30 days'
);

CREATE INDEX IF NOT EXISTS sessions_token_idx ON sessions (token_hash);

-- Clean up old tables from the previous (abandoned) approach
DROP TABLE IF EXISTS pending_signups;
