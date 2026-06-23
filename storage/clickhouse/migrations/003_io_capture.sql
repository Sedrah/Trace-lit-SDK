-- Migration 003: I/O capture columns
-- input_text / output_text are nullable; ingestion may redact before writing.
ALTER TABLE spans ADD COLUMN IF NOT EXISTS input_text  Nullable(String);
ALTER TABLE spans ADD COLUMN IF NOT EXISTS output_text Nullable(String);
