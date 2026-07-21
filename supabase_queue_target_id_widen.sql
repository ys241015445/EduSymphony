-- Widen queue_jobs.target_id for zhuke per-lesson jobs: "{uuid}::{lesson_idx}" (39+ chars).
-- Idempotent: safe to re-run.

ALTER TABLE queue_jobs
    ALTER COLUMN target_id TYPE VARCHAR(128);

ANALYZE queue_jobs;
