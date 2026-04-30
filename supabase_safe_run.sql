-- =============================================================================
-- Conservative Supabase SQL — safe to run multiple times (idempotent).
--
-- What it does:
--   - Ensures public.users.access_level exists with CHECK (full|limited|admin)
--   - Normalizes invalid values to 'full' so ADD CONSTRAINT cannot fail
--   - Creates idx_users_access_level if missing
-- Does NOT: delete/truncate; bulk-promote admins; create unrelated tables.
--
-- Paste in: Supabase Dashboard -> SQL Editor -> New query -> Run.
--
-- If public.users does not exist yet, run your full schema first (e.g.
-- supabase_schema.sql), then run this file.
-- =============================================================================

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS access_level VARCHAR(20) NOT NULL DEFAULT 'full';

-- Normalize before (re)applying CHECK so reruns stay safe on dirty data.
UPDATE users
SET access_level = 'full'
WHERE access_level NOT IN ('full', 'limited', 'admin');

COMMENT ON COLUMN users.access_level IS 'full | limited | admin';

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_access_level_check;
ALTER TABLE users ADD CONSTRAINT users_access_level_check
  CHECK (access_level IN ('full', 'limited', 'admin'));

CREATE INDEX IF NOT EXISTS idx_users_access_level ON users (access_level);

-- Informational only — never fails the script.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'users'
      AND column_name = 'quota_remaining'
  ) THEN
    RAISE NOTICE 'users.quota_remaining: present';
  ELSE
    RAISE NOTICE 'users.quota_remaining: missing — run remaining app migrations if needed';
  END IF;
END $$;
