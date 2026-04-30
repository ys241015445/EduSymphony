-- =============================================================================
-- RBAC: users.access_level (full | limited | admin)
-- Idempotent: safe to run multiple times on an existing Supabase (PostgreSQL) DB.
--
-- How to apply on Supabase:
--   1. Open Supabase Dashboard -> your Project -> SQL Editor -> New query.
--   2. Paste this entire file and click Run.
--   3. Verify: Table Editor -> public.users -> column access_level and sample rows.
--   4. For production, run during a maintenance window; fix any invalid
--      access_level values before ADD CONSTRAINT if CHECK fails.
--
-- New greenfield databases: prefer full supabase_schema.sql (includes this column).
-- =============================================================================

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS access_level VARCHAR(20) NOT NULL DEFAULT 'full';

COMMENT ON COLUMN users.access_level IS 'full | limited | admin';

-- Enforce valid values at DB level (optional; remove CHECK block if app-only validation).
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_access_level_check;
ALTER TABLE users ADD CONSTRAINT users_access_level_check
  CHECK (access_level IN ('full', 'limited', 'admin'));

CREATE INDEX IF NOT EXISTS idx_users_access_level ON users (access_level);

-- One-time alignment: edit usernames / regex to match your deployment.
-- Regex matches zhkj01 .. zhkj99 only; add separate UPDATE for e.g. username = 'zhkj'.
UPDATE users SET access_level = 'admin' WHERE username IN ('lzf', 'ys');
UPDATE users SET access_level = 'limited' WHERE username ~ '^zhkj[0-9]{2}$';
