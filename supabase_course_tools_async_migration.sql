-- Course-Tools Async Queue Migration
-- Run once in Supabase SQL editor to enable pending/running/failed status for
-- outline / ppt / exercises / practice async jobs.

ALTER TABLE course_tool_results
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'completed',
    ADD COLUMN IF NOT EXISTS error_message TEXT,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_ctr_user_status_created
    ON course_tool_results (user_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ctr_user_tool_type_created
    ON course_tool_results (user_id, tool_type, created_at DESC);

-- Auto-update updated_at on every update
CREATE OR REPLACE FUNCTION _trg_ctr_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ctr_touch_updated_at ON course_tool_results;
CREATE TRIGGER ctr_touch_updated_at
    BEFORE UPDATE ON course_tool_results
    FOR EACH ROW EXECUTE FUNCTION _trg_ctr_touch_updated_at();
