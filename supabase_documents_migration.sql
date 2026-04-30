-- ============================================================
-- EduSymphony 文档系统迁移：document_versions + export_records
-- 用于在已部署的 Supabase / PostgreSQL 上增量执行
-- 生成时间：2026-04-08
-- ============================================================

-- 1. document_versions：教案/课程产物可编辑文档版本快照
CREATE TABLE IF NOT EXISTS document_versions (
    id                VARCHAR(36)  PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    user_id           VARCHAR(36)  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_plan_id    VARCHAR(36)  REFERENCES lesson_plans(id) ON DELETE CASCADE,
    source_kind       VARCHAR(30)  NOT NULL DEFAULT 'lesson_optimized',
    source_ref_id     VARCHAR(36),
    title             VARCHAR(200) NOT NULL DEFAULT '未命名文档',
    content_markdown  TEXT         NOT NULL DEFAULT '',
    version_number    INTEGER      NOT NULL DEFAULT 1,
    parent_version_id VARCHAR(36),
    change_summary    TEXT,
    change_source     VARCHAR(20)  NOT NULL DEFAULT 'user_edit',
    ai_prompt         TEXT,
    is_current        BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_doc_versions_user_created
    ON document_versions (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_doc_versions_lesson
    ON document_versions (lesson_plan_id, version_number DESC);
CREATE INDEX IF NOT EXISTS idx_doc_versions_source_ref
    ON document_versions (source_kind, source_ref_id);

-- 2. export_records：用户导出/下载历史 + 异步导出临时缓存索引
CREATE TABLE IF NOT EXISTS export_records (
    id              VARCHAR(36)  PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    user_id         VARCHAR(36)  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_plan_id  VARCHAR(36)  REFERENCES lesson_plans(id) ON DELETE CASCADE,
    version_id      VARCHAR(36)  REFERENCES document_versions(id) ON DELETE SET NULL,
    source_kind     VARCHAR(30)  NOT NULL DEFAULT 'lesson',
    format          VARCHAR(20)  NOT NULL,
    file_name       VARCHAR(255) NOT NULL,
    file_size       BIGINT,
    file_path       VARCHAR(500),
    job_id          VARCHAR(36),
    status          VARCHAR(20)  NOT NULL DEFAULT 'done',
    params          JSONB,
    error_message   TEXT,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 兼容已有 export_records 的增量列（IF NOT EXISTS 防重复）
ALTER TABLE export_records ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'done';
ALTER TABLE export_records ADD COLUMN IF NOT EXISTS params JSONB;
ALTER TABLE export_records ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE export_records ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_export_records_user_created
    ON export_records (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_export_records_lesson
    ON export_records (lesson_plan_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_export_records_expires
    ON export_records (expires_at);

-- 3. （可选）清理过期 export_records 的存储过程
-- 由后端 APScheduler 定时任务调用 / 也可手动 SELECT cleanup_expired_exports();
CREATE OR REPLACE FUNCTION cleanup_expired_exports()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM export_records
    WHERE expires_at IS NOT NULL AND expires_at < now()
    RETURNING 1 INTO deleted_count;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 完成。请验证：
--   SELECT count(*) FROM document_versions;
--   SELECT count(*) FROM export_records;
-- ============================================================
