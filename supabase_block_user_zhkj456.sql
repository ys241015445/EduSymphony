-- =============================================================================
-- Block user zhkj456: lock all permissions + invalidate password + cancel jobs
-- Idempotent: safe to run multiple times on Supabase (PostgreSQL).
--
-- How to apply:
--   Supabase Dashboard -> SQL Editor -> paste and Run
--   OR: backend/scripts/run_block_zhkj456.py (uses DATABASE_URL)
--
-- Login effect (SQL-only, no backend deploy):
--   Any password fails verify_password -> API returns "用户名或密码错误"
-- =============================================================================

-- 1) Confirm user exists
SELECT id, username, access_level, quota_remaining
FROM users
WHERE username = 'zhkj456';

-- 2) Lock permissions + block login (invalid bcrypt — no password will verify)
UPDATE users
SET
  access_level = 'limited',
  quota_remaining = 0,
  can_course_tools = false,
  can_template_fill = false,
  can_university = false,
  can_series = false,
  can_next_lesson = false,
  can_export = false,
  can_semester_helper = false,
  password_hash = '$2b$12$BLOCKED.ACCOUNT.NO.LOGIN.XXXXXXXXXXXXXX',
  updated_at = now()
WHERE username = 'zhkj456';

-- 3) Cancel in-flight queue jobs for this user
UPDATE queue_jobs
SET
  status = 'cancelled',
  finished_at = now(),
  worker_id = NULL,
  lease_until = NULL,
  error = coalesce(error, 'user_blocked')
WHERE user_id = (SELECT id FROM users WHERE username = 'zhkj456')
  AND status IN ('queued', 'running');

-- 4) Verify user row
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

-- 5) Verify queue_jobs for this user
SELECT status, count(*) AS cnt
FROM queue_jobs
WHERE user_id = (SELECT id FROM users WHERE username = 'zhkj456')
GROUP BY status
ORDER BY status;
