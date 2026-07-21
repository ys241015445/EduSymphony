-- =============================================================================
-- GC stale cancelled queue_jobs (zhuke batches leave many cancelled rows).
-- Safe to re-run. Keeps cancelled jobs from the last 24h for debugging.
-- =============================================================================

DELETE FROM queue_jobs
WHERE status = 'cancelled'
  AND finished_at IS NOT NULL
  AND finished_at < now() - interval '1 day';

DELETE FROM queue_jobs
WHERE status = 'cancelled'
  AND finished_at IS NULL
  AND created_at < now() - interval '1 day';

ANALYZE queue_jobs;
ANALYZE lesson_plans;
