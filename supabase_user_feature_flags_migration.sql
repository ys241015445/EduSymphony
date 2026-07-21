-- =============================================================================
-- Per-user feature flags
--
-- Six BOOLEAN columns on `users`. All default TRUE so existing users keep full
-- access. Admins can flip individual switches via PATCH /api/v1/admin/users/{uid}.
--
-- Backend enforcement: deps.require_capability(flag) on each routed endpoint.
-- Frontend gating: <CapabilityRoute flag="..."> + entry card hide.
--
-- Idempotent. Run in Supabase SQL Editor.
-- =============================================================================

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS can_course_tools BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS can_template_fill BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS can_university   BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS can_series       BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS can_next_lesson  BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS can_export       BOOLEAN NOT NULL DEFAULT TRUE;

-- Defensive backfill in case columns existed as NULL from a partial earlier run.
UPDATE users SET can_course_tools  = TRUE WHERE can_course_tools  IS NULL;
UPDATE users SET can_template_fill = TRUE WHERE can_template_fill IS NULL;
UPDATE users SET can_university    = TRUE WHERE can_university    IS NULL;
UPDATE users SET can_series        = TRUE WHERE can_series        IS NULL;
UPDATE users SET can_next_lesson   = TRUE WHERE can_next_lesson   IS NULL;
UPDATE users SET can_export        = TRUE WHERE can_export        IS NULL;

COMMENT ON COLUMN users.can_course_tools  IS 'Enable course-tools (PPT/exercises/practice/outline) routes';
COMMENT ON COLUMN users.can_template_fill IS 'Enable AI template-fill routes';
COMMENT ON COLUMN users.can_university    IS 'Enable university series creation/dashboard';
COMMENT ON COLUMN users.can_series        IS 'Enable K12 series creation/dashboard';
COMMENT ON COLUMN users.can_next_lesson   IS 'Enable next-lesson / continuation generation';
COMMENT ON COLUMN users.can_export        IS 'Enable export endpoints (download docx/pdf/zip/...)';
