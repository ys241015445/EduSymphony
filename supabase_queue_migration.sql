-- ============================================================
-- EduSymphony — 持久化队列迁移 (Postgres-backed task queue)
-- 使用方法：在 Supabase SQL Editor 执行
-- 安全性：幂等，可重复运行
-- 生成时间：2026-04-08
-- ============================================================

-- ------------------------------------------------------------
-- 1. queue_jobs —— 队列主表
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS queue_jobs (
    id           BIGSERIAL PRIMARY KEY,
    target_id    VARCHAR(128) NOT NULL,              -- lesson_id / {uuid}::{idx} 等
    kind         VARCHAR(40) NOT NULL,               -- lesson / syllabus / continue / ...
    user_id      VARCHAR(36),                        -- 用户级公平依据（可为 NULL）
    status       VARCHAR(20) NOT NULL DEFAULT 'queued',
                                                     -- queued / running / done / failed
    priority     INT NOT NULL DEFAULT 0,
    attempts     INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 1,
    worker_id    VARCHAR(80),                        -- 认领者标识
    lease_until  TIMESTAMPTZ,                        -- 租约到期（sweeper 回收依据）
    error        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at   TIMESTAMPTZ,
    finished_at  TIMESTAMPTZ
);

-- ------------------------------------------------------------
-- 2. 索引
-- ------------------------------------------------------------

-- 同一 (kind, target_id) 只能有一个未完成 job，防重复入队
CREATE UNIQUE INDEX IF NOT EXISTS uq_queue_jobs_active
    ON queue_jobs (kind, target_id)
    WHERE status IN ('queued', 'running');

-- 认领热路径：status + priority + created_at
CREATE INDEX IF NOT EXISTS idx_queue_jobs_pick
    ON queue_jobs (status, priority DESC, created_at)
    WHERE status IN ('queued', 'running');

-- 用户级公平聚合
CREATE INDEX IF NOT EXISTS idx_queue_jobs_user_status
    ON queue_jobs (user_id, status);

-- Sweeper 扫超时 lease
CREATE INDEX IF NOT EXISTS idx_queue_jobs_lease
    ON queue_jobs (lease_until)
    WHERE status = 'running';

-- GC 旧完成记录
CREATE INDEX IF NOT EXISTS idx_queue_jobs_finished_at
    ON queue_jobs (finished_at)
    WHERE status IN ('done', 'failed');

-- ------------------------------------------------------------
-- 3. autovacuum 调优
--    队列高频 UPDATE，默认 20% 阈值太松，降低到 2%
-- ------------------------------------------------------------

ALTER TABLE queue_jobs SET (
    autovacuum_vacuum_scale_factor = 0.02,
    autovacuum_analyze_scale_factor = 0.02
);

-- ------------------------------------------------------------
-- 4. 顺带刷新长尾表的统计信息
-- ------------------------------------------------------------

ANALYZE discussions;
ANALYZE annotations;
ANALYZE queue_jobs;

-- ============================================================
-- Done
-- ============================================================
