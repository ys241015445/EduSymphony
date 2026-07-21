-- =============================================================================
-- Per-user capability: Semester Material Assistant
--
-- Unlike the 6 capability flags in supabase_user_feature_flags_migration.sql
-- (default TRUE), this one defaults FALSE so it is OFF for everyone initially.
-- Admins (access_level='admin') automatically bypass require_capability() in
-- backend/app/core/deps.py, so the two admin accounts (lzf, ys) can use it
-- without flipping the column. Regular users only see and can use the module
-- after an admin flips this flag in /admin/users -> Edit Permissions.
--
-- Idempotent. Run in Supabase SQL Editor (or apply via MCP apply_migration).
-- =============================================================================

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS can_semester_helper BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE users SET can_semester_helper = FALSE WHERE can_semester_helper IS NULL;

COMMENT ON COLUMN users.can_semester_helper IS
  'Enable Semester Material Assistant module; default FALSE; admins bypass via require_capability';
