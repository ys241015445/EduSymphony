-- =============================================================================
-- Soft-delete migration
--
-- Adds `deleted_at TIMESTAMPTZ NULL` to lesson_plans / lesson_series /
-- document_versions / export_records and creates partial indexes so that
-- "live row" queries (WHERE deleted_at IS NULL) stay fast.
--
-- Application behavior:
--   - DELETE endpoints now perform soft delete (UPDATE deleted_at = NOW()).
--   - Regular users only ever see rows with deleted_at IS NULL.
--   - Admins may pass ?include_deleted=true to view soft-deleted rows
--     (handled in FastAPI; this migration only provides the storage).
--
-- Idempotent: safe to run multiple times on Supabase (SQL Editor → Run).
-- =============================================================================

ALTER TABLE lesson_plans      ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ NULL;
ALTER TABLE lesson_series     ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ NULL;
ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ NULL;
ALTER TABLE export_records    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ NULL;

-- "Live row" partial indexes per (user_id, created_at DESC) for common listing
-- queries. Existing full indexes remain untouched.

CREATE INDEX IF NOT EXISTS idx_lesson_plans_live
  ON lesson_plans (user_id, created_at DESC)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_lesson_series_live
  ON lesson_series (user_id, created_at DESC)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_document_versions_live
  ON document_versions (user_id, created_at DESC)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_export_records_live
  ON export_records (user_id, created_at DESC)
  WHERE deleted_at IS NULL;

-- Optional: indexes that admin "show deleted" views may use.
CREATE INDEX IF NOT EXISTS idx_lesson_plans_deleted
  ON lesson_plans (user_id, deleted_at DESC)
  WHERE deleted_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_lesson_series_deleted
  ON lesson_series (user_id, deleted_at DESC)
  WHERE deleted_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_document_versions_deleted
  ON document_versions (user_id, deleted_at DESC)
  WHERE deleted_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_export_records_deleted
  ON export_records (user_id, deleted_at DESC)
  WHERE deleted_at IS NOT NULL;
