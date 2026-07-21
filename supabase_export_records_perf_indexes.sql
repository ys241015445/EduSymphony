-- =============================================================================
-- Export records performance indexes
--
-- Speeds up admin "user exports" pages:
--   - Filter the detail table by source_kind  (course_tool / lesson / template_fill / styled_pdf / material / bundle)
--   - Filter the detail table by status       (done / queued / running / failed / expired)
--   - Order the live records by created_at desc within (user_id, source_kind|status)
--
-- Both indexes are partial (deleted_at IS NULL) — they cover the common path
-- where regular users only see live rows; admins can still SeqScan the small
-- "include_deleted=true" view without index pressure on writes.
--
-- Existing soft-delete partial indexes (`idx_export_records_live`,
-- `idx_export_records_deleted`) are NOT replaced; they remain useful for the
-- default time-ordered listing and admin "deleted only" filter.
--
-- Idempotent. Run in Supabase SQL Editor (or applied via MCP apply_migration).
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_export_records_user_kind_created_live
  ON export_records (user_id, source_kind, created_at DESC)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_export_records_user_status_created_live
  ON export_records (user_id, status, created_at DESC)
  WHERE deleted_at IS NULL;
