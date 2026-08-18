-- =============================================================================
-- 珠科材料助手能力开关 + 项目表（增量迁移）
-- 幂等，可重复执行。
--
-- 【已有库必跑】缺 users.can_zhuke_materials 会导致后端 startup 查询 users
-- 失败（UndefinedColumnError）。新建库若已执行 supabase_schema.sql 可跳过。
-- =============================================================================

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS can_zhuke_materials BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE users SET can_zhuke_materials = FALSE WHERE can_zhuke_materials IS NULL;

COMMENT ON COLUMN users.can_zhuke_materials IS
  'Enable Zhuke Materials Assistant on workbench; default FALSE; admins bypass via require_capability';

CREATE TABLE IF NOT EXISTS zhuke_material_projects (
    id                    VARCHAR(36) PRIMARY KEY,
    user_id               VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_name           VARCHAR(200) NOT NULL DEFAULT '',
    mode                  VARCHAR(8) NOT NULL DEFAULT 'C',
    status                VARCHAR(32) NOT NULL DEFAULT 'created',
    error                 TEXT,
    context_json          TEXT,
    syllabus_json         TEXT,
    weeks_json            TEXT,
    lessons_json          TEXT,
    schedule_json         TEXT,
    syllabus_path         VARCHAR(512),
    calendar_theory_path  VARCHAR(512),
    calendar_lab_path     VARCHAR(512),
    lessons_path          VARCHAR(512),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_zhuke_mat_user ON zhuke_material_projects (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_zhuke_mat_status ON zhuke_material_projects (status);
