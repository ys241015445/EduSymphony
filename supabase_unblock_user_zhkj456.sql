-- =============================================================================
-- Unblock user zhkj456: restore full permissions (password set by run script)
-- Idempotent: safe to run multiple times on Supabase (PostgreSQL).
--
-- How to apply:
--   backend/scripts/run_unblock_zhkj456.py (uses DATABASE_URL + get_password_hash)
--   OR: Supabase Dashboard -> SQL Editor (set password_hash manually)
-- =============================================================================

-- 1) Confirm user exists
SELECT id, username, access_level, quota_remaining
FROM users
WHERE username = 'zhkj456';

-- 2) Restore full access (password_hash updated by run_unblock_zhkj456.py)
UPDATE users
SET
  access_level = 'full',
  quota_remaining = 9999,
  can_course_tools = true,
  can_template_fill = true,
  can_university = true,
  can_series = true,
  can_next_lesson = true,
  can_export = true,
  can_semester_helper = false,
  updated_at = now()
WHERE username = 'zhkj456';

-- 3) Verify user row
SELECT
  username,
  access_level,
  quota_remaining,
  can_course_tools,
  can_template_fill,
  can_university,
  can_series,
  can_next_lesson,
  can_export,
  can_semester_helper,
  left(password_hash, 24) AS pwd_prefix
FROM users
WHERE username = 'zhkj456';
