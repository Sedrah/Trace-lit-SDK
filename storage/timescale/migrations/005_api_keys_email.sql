-- Add email column to api_keys for self-service sign-up tracking.
ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS email TEXT;
