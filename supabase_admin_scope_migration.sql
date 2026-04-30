-- =============================================================================
-- Admin scoped read/write (for_user_id) — database alignment
--
-- Behavior is enforced in FastAPI via resolve_documents_owner() + owner quotas.
-- No NEW tables or columns are required for impersonation.
--
-- Prerequisites (existing schema):
--   - users.access_level IN ('full', 'limited', 'admin')
--   - users.quota_remaining (target user's quota when admin uses for_user_id)
--   - lesson_plans.user_id, lesson_series.user_id, annotations.user_id → users(id)
--   - annotations.user_id may be the admin id when an admin creates a note (audit).
--
-- On Supabase: SQL Editor → New query → paste and Run.
-- Safe to run multiple times (idempotent checks only).
-- =============================================================================

-- 1) RBAC column (greenfield may already have this from supabase_schema.sql)
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS access_level VARCHAR(20) NOT NULL DEFAULT 'full';

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_access_level_check;
ALTER TABLE users ADD CONSTRAINT users_access_level_check
  CHECK (access_level IN ('full', 'limited', 'admin'));

CREATE INDEX IF NOT EXISTS idx_users_access_level ON users (access_level);

-- 2) Verification (read-only diagnostics)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'access_level'
  ) THEN
    RAISE EXCEPTION 'users.access_level missing — check migration';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'quota_remaining'
  ) THEN
    RAISE EXCEPTION 'users.quota_remaining missing';
  END IF;
END $$;

-- Optional: list current admins (adjust usernames as needed)
-- SELECT id, username, email, access_level, quota_remaining FROM users WHERE access_level = 'admin';

-- =============================================================================
-- If you use Supabase Row Level Security (RLS) on these tables together with
-- PostgREST: policies that only allow user_id = auth.uid() will BLOCK admin
-- cross-user access from the Supabase API. This app’s backend uses SQLAlchemy
-- with a direct DB connection (service role / pooler), so RLS often does not
-- apply to the FastAPI path. If you expose tables via anon/authenticated
-- clients, add separate admin policies or use only the backend API for admin.
-- =============================================================================
