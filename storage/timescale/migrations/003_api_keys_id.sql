-- Add surrogate id to api_keys for use in admin API endpoints.
-- key_hash remains the PRIMARY KEY for auth lookups.

ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS id SERIAL UNIQUE;
